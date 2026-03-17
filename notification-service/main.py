import os
import asyncio
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker
from prometheus_fastapi_instrumentator import Instrumentator
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
import aio_pika
from rx import create
from rx.scheduler.eventloop import AsyncIOScheduler

structlog.configure(
    processors=[structlog.processors.JSONRenderer()],
    logger_factory=structlog.PrintLoggerFactory(),
)
log = structlog.get_logger()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@notification-db:5432/notificationdb")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq/")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    message = Column(String, nullable=False)


Base.metadata.create_all(bind=engine)

provider = TracerProvider()
otlp_endpoint = os.getenv("OTLP_ENDPOINT", "http://jaeger:4317")
processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True))
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


def process_message_stream(messages: list[str]):
    """Use RxPY to process a stream of messages reactively."""
    def subscribe(observer, scheduler=None):
        for msg in messages:
            observer.on_next(msg)
        observer.on_completed()

    source = create(subscribe)
    source.pipe().subscribe(
        on_next=lambda msg: log.info("rx_processing", message=msg[:50]),
        on_error=lambda e: log.error("rx_error", error=str(e)),
        on_completed=lambda: log.info("rx_stream_completed"),
    )


async def consume_rabbitmq():
    for attempt in range(10):
        try:
            connection = await aio_pika.connect_robust(RABBITMQ_URL)
            break
        except Exception as e:
            log.warning("rabbitmq_connecting", attempt=attempt, error=str(e))
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(consume_rabbitmq())
    yield


app = FastAPI(title="Notification Service", lifespan=lifespan)
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
