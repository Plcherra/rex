from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routes.chat import router as chat_router
from app.routes.conversations import router as conversations_router
from app.routes.memory import router as memory_router
from app.routes.voice import router as voice_router
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


@app.get("/ready")
def readiness_check() -> dict:
    checks = {
        "grok": {
            "configured": bool(settings.grok_api_key and settings.grok_model),
            "required": ["GROK_API_KEY", "GROK_MODEL"],
        },
        "supabase": {
            "configured": bool(
                settings.supabase_url and settings.supabase_service_role_key
            ),
            "required": ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"],
        },
        "deepgram": {
            "configured": bool(settings.deepgram_api_key),
            "required": ["DEEPGRAM_API_KEY"],
            "model": settings.deepgram_model,
            "language": settings.deepgram_language,
        },
        "google_tts": {
            "configured": settings.google_tts_is_configured,
            "required": [
                "GOOGLE_TTS_PROJECT_ID",
                "GOOGLE_TTS_CREDENTIALS_JSON or GOOGLE_APPLICATION_CREDENTIALS",
            ],
            "voice_name": settings.google_tts_voice_name,
            "language_code": settings.google_tts_language_code,
            "audio_encoding": settings.google_tts_audio_encoding,
        },
    }
    return {
        "status": "ready" if all(check["configured"] for check in checks.values()) else "degraded",
        "service": "rex-backend",
        "checks": checks,
    }


app.include_router(chat_router)
app.include_router(conversations_router)
app.include_router(memory_router)
app.include_router(voice_router)
