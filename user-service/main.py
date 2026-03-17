import os
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException
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

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@user-db:5432/userdb")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)


provider = TracerProvider()
otlp_endpoint = os.getenv("OTLP_ENDPOINT", "http://jaeger:4317")
processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True))
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("user-service")


@asynccontextmanager
async def lifespan(application: FastAPI):
    Base.metadata.create_all(bind=engine)
    log.info("db_initialized", service="user-service")
    yield


app = FastAPI(title="User Service", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
FastAPIInstrumentor.instrument_app(app)
Instrumentator().instrument(app).expose(app)


class UserCreate(BaseModel):
    username: str


@app.get("/health")
def health():
    return {"status": "ok", "service": "user-service"}


@app.get("/users")
def list_users():
    with tracer.start_as_current_span("list_users"):
        db = SessionLocal()
        try:
            users = db.query(User).all()
            log.info("list_users", count=len(users))
            return [{"id": u.id, "username": u.username} for u in users]
        finally:
            db.close()


@app.post("/users", status_code=201)
def create_user(body: UserCreate):
    with tracer.start_as_current_span("create_user"):
        db = SessionLocal()
        try:
            existing = db.query(User).filter(User.username == body.username).first()
            if existing:
                raise HTTPException(status_code=409, detail="Username already exists")
            user = User(username=body.username)
            db.add(user)
            db.commit()
            db.refresh(user)
            log.info("create_user", username=body.username, id=user.id)
            return {"id": user.id, "username": user.username}
        finally:
            db.close()
