import os
import asyncio
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker
from prometheus_fastapi_instrumentator import Instrumentator
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
import aio_pika

structlog.configure(
    processors=[structlog.processors.JSONRenderer()],
    logger_factory=structlog.PrintLoggerFactory(),
)
log = structlog.get_logger()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@post-db:5432/postdb")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq/")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True, index=True)
    content = Column(String, nullable=False)


Base.metadata.create_all(bind=engine)

provider = TracerProvider()
otlp_endpoint = os.getenv("OTLP_ENDPOINT", "http://jaeger:4317")
processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True))
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("post-service")

_rabbitmq_connection = None
_rabbitmq_channel = None


async def get_rabbitmq_channel():
    global _rabbitmq_connection, _rabbitmq_channel
    if _rabbitmq_channel is None or _rabbitmq_channel.is_closed:
        _rabbitmq_connection = await aio_pika.connect_robust(RABBITMQ_URL)
        _rabbitmq_channel = await _rabbitmq_connection.channel()
    return _rabbitmq_channel


@asynccontextmanager
async def lifespan(app: FastAPI):
    for attempt in range(10):
        try:
            await get_rabbitmq_channel()
            log.info("rabbitmq_connected")
            break
        except Exception as e:
            log.warning("rabbitmq_connecting", attempt=attempt, error=str(e))
            await asyncio.sleep(3)
    yield
    if _rabbitmq_connection:
        await _rabbitmq_connection.close()


app = FastAPI(title="Post Service", lifespan=lifespan)
FastAPIInstrumentor.instrument_app(app)
Instrumentator().instrument(app).expose(app)


class PostCreate(BaseModel):
    content: str


@app.get("/health")
def health():
    return {"status": "ok", "service": "post-service"}


@app.get("/posts")
def list_posts():
    with tracer.start_as_current_span("list_posts"):
        db = SessionLocal()
        try:
            posts = db.query(Post).all()
            log.info("list_posts", count=len(posts))
            return [{"id": p.id, "content": p.content} for p in posts]
        finally:
            db.close()


@app.post("/posts", status_code=201)
async def create_post(body: PostCreate):
    with tracer.start_as_current_span("create_post"):
        db = SessionLocal()
        try:
            post = Post(content=body.content)
            db.add(post)
            db.commit()
            db.refresh(post)
            log.info("create_post", id=post.id)

            try:
                channel = await get_rabbitmq_channel()
                await channel.default_exchange.publish(
                    aio_pika.Message(
                        body=f"New post created: {body.content[:50]}".encode(),
                        content_type="text/plain",
                    ),
                    routing_key="post.created",
                )
                log.info("post_event_published", post_id=post.id)
            except Exception as e:
                log.warning("rabbitmq_publish_failed", error=str(e))

            return {"id": post.id, "content": post.content}
        finally:
            db.close()
