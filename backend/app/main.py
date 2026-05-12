from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routes.chat import router as chat_router
from app.routes.conversations import router as conversations_router
from app.routes.memory import router as memory_router
from app.services.http_client import shutdown_http_client, startup_http_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    await startup_http_client()
    try:
        yield
    finally:
        await shutdown_http_client()


app = FastAPI(title="Rex Backend", lifespan=lifespan)
settings = get_settings()

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.get("/")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "rex-backend"}


app.include_router(chat_router)
app.include_router(conversations_router)
app.include_router(memory_router)
