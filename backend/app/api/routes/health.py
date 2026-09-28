from fastapi import APIRouter
from app.config import settings
from app.utils.semantic import active_backend

router = APIRouter()


@router.get("/health")
async def health_check():
    return {
        "status": "ok",
        "app": settings.app_name,
        "provider": "anthropic",
        "model": settings.anthropic_model,
        "api_key_set": bool(settings.anthropic_api_key),
        "semantic_backend": active_backend(),
    }
