import os
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

structlog.configure(
    processors=[structlog.processors.JSONRenderer()],
    logger_factory=structlog.PrintLoggerFactory(),
)
log = structlog.get_logger()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@comment-db:5432/commentdb")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Comment(Base):
    __tablename__ = "comments"
    id = Column(Integer, primary_key=True, index=True)
    text = Column(String, nullable=False)


provider = TracerProvider()
otlp_endpoint = os.getenv("OTLP_ENDPOINT", "http://jaeger:4317")
processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True))
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("comment-service")


@asynccontextmanager
async def lifespan(application: FastAPI):
    Base.metadata.create_all(bind=engine)
    log.info("db_initialized", service="comment-service")
    yield


app = FastAPI(title="Comment Service", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
FastAPIInstrumentor.instrument_app(app)
Instrumentator().instrument(app).expose(app)


class CommentCreate(BaseModel):
    text: str


@app.get("/health")
def health():
    return {"status": "ok", "service": "comment-service"}


@app.get("/comments")
def list_comments():
    with tracer.start_as_current_span("list_comments"):
        db = SessionLocal()
        try:
            comments = db.query(Comment).all()
            log.info("list_comments", count=len(comments))
            return [{"id": c.id, "text": c.text} for c in comments]
        finally:
            db.close()


@app.post("/comments", status_code=201)
def create_comment(body: CommentCreate):
    with tracer.start_as_current_span("create_comment"):
        db = SessionLocal()
        try:
            comment = Comment(text=body.text)
            db.add(comment)
            db.commit()
            db.refresh(comment)
            log.info("create_comment", id=comment.id)
            return {"id": comment.id, "text": comment.text}
        finally:
            db.close()
