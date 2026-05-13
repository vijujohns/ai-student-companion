"""
API v1 versioning router factory.
This module creates a versioned router that includes all domain routers under /api/v1 prefix.
"""

from fastapi import APIRouter
from .auth_session import router as auth_session_router
from .health import router as health_router
from .ask import router as ask_router
from .knowledge import router as knowledge_router
from .lesson_plan import router as lesson_plan_router
from .quiz import router as quiz_router
from .assessment import router as assessment_router
from .admin import router as admin_router
from .progress import router as progress_router
from .collaboration import router as collaboration_router
from .subscription import router as subscription_router
from ..modules.flashcards import router as flashcards_router


def create_v1_router():
    """
    Create and return the /api/v1 versioned router.
    This router includes all domain routers with the /api/v1 prefix applied.
    """
    v1_router = APIRouter(prefix="/api/v1", tags=["v1"])

    # Include all domain routers under /api/v1
    v1_router.include_router(auth_session_router)
    v1_router.include_router(health_router)
    v1_router.include_router(ask_router)
    v1_router.include_router(knowledge_router)
    v1_router.include_router(lesson_plan_router)
    v1_router.include_router(quiz_router)
    v1_router.include_router(assessment_router)
    v1_router.include_router(admin_router)
    v1_router.include_router(progress_router)
    v1_router.include_router(collaboration_router)
    v1_router.include_router(subscription_router)
    try:
        v1_router.include_router(flashcards_router)
    except Exception:
        pass

    return v1_router
