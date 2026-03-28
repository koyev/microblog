import asyncio
import json
import os
from contextlib import asynccontextmanager

import aio_pika
import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from opentelemetry import trace

from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_fastapi_instrumentator import Instrumentator
from rx import create
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

structlog.configure(
    processors=[structlog.processors.JSONRenderer()],
    logger_factory=structlog.PrintLoggerFactory(),
)
log = structlog.get_logger()

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://user:password@notification-db:5432/notificationdb"
)
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq/")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# SSE subscriber queues — one asyncio.Queue per connected client
_sse_subscribers: set[asyncio.Queue] = set()


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    message = Column(String, nullable=False)


provider = TracerProvider()
otlp_endpoint = os.getenv("OTLP_ENDPOINT", "http://jaeger:4318")
processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint))
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("notification-service")


def save_notification(message: str):
    db = SessionLocal()
    try:
        notif = Notification(message=message)
        db.add(notif)
        db.commit()
        log.info("notification_saved", message=message[:50])
    finally:
        db.close()


def process_message_stream(messages: list):
    """Process a batch of messages reactively using RxPY."""

    def subscribe(observer, scheduler=None):
        for msg in messages:
            observer.on_next(msg)
        observer.on_completed()

    source = create(subscribe)
    source.subscribe(
        on_next=lambda msg: log.info("rx_processing", message=msg[:50]),
        on_error=lambda e: log.error("rx_error", error=str(e)),
        on_completed=lambda: log.info("rx_stream_completed"),
    )


async def _broadcast_sse(message: str):
    """Push a message to all active SSE subscribers."""
    dead = set()
    for queue in _sse_subscribers:
        try:
            queue.put_nowait(message)
        except asyncio.QueueFull:
            dead.add(queue)
    _sse_subscribers.difference_update(dead)


async def consume_rabbitmq():
    for attempt in range(10):
        try:
            connection = await aio_pika.connect_robust(RABBITMQ_URL)
            break
        except Exception as exc:
            log.warning("rabbitmq_connecting", attempt=attempt, error=str(exc))
            await asyncio.sleep(3)
    else:
        log.error("rabbitmq_connection_failed")
        return

    async with connection:
        channel = await connection.channel()
        queue = await channel.declare_queue("post.created", durable=True)
        log.info("rabbitmq_consumer_started")

        async for message in queue:
            async with message.process():
                body = message.body.decode()
                log.info("rabbitmq_message_received", body=body[:50])
                process_message_stream([body])
                save_notification(body)
                await _broadcast_sse(body)


@asynccontextmanager
async def lifespan(application: FastAPI):
    Base.metadata.create_all(bind=engine)
    log.info("db_initialized", service="notification-service")
    task = asyncio.create_task(consume_rabbitmq())
    yield
    task.cancel()


app = FastAPI(title="Notification Service", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
FastAPIInstrumentor.instrument_app(app)
Instrumentator().instrument(app).expose(app)


@app.get("/health")
def health():
    return {"status": "ok", "service": "notification-service"}


@app.get("/notifications")
def list_notifications():
    with tracer.start_as_current_span("list_notifications"):
        db = SessionLocal()
        try:
            notifications = db.query(Notification).all()
            log.info("list_notifications", count=len(notifications))
            return [{"id": n.id, "message": n.message} for n in notifications]
        finally:
            db.close()


@app.get("/stream/notifications")
async def stream_notifications(request: Request):
    """SSE endpoint — clients receive real-time notifications as they arrive."""
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    _sse_subscribers.add(queue)
    log.info("sse_client_connected", total=len(_sse_subscribers))

    async def event_generator():
        try:
            yield 'data: {"connected": true}\n\n'
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=15.0)
                    payload = json.dumps({"message": message})
                    yield f"data: {payload}\n\n"
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        finally:
            _sse_subscribers.discard(queue)
            log.info("sse_client_disconnected", total=len(_sse_subscribers))

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
