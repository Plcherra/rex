from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from app.config import get_settings
from app.routes.chat import router as chat_router
from app.services import memory_service


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    get_settings()
    memory_service.init()
    yield


app = FastAPI(title="Rex Backend", lifespan=lifespan)


@app.get("/")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "rex-backend"}


app.include_router(chat_router)
