from fastapi import FastAPI

from app.routes.chat import router as chat_router
from app.routes.conversations import router as conversations_router
from app.routes.memory import router as memory_router
from app.services.http_client import shutdown_http_client, startup_http_client

app = FastAPI(title="Rex Backend")


@app.on_event("startup")
async def startup() -> None:
    await startup_http_client()


@app.on_event("shutdown")
async def shutdown() -> None:
    await shutdown_http_client()


@app.get("/")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "rex-backend"}


app.include_router(chat_router)
app.include_router(conversations_router)
app.include_router(memory_router)
