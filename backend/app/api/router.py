from fastapi import APIRouter

from app.api.routes.agents import router as agents_router
from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.api.routes.memory import router as memory_router
from app.api.routes.mcp import router as mcp_router
from app.api.routes.rbac import router as rbac_router
from app.api.routes.runs import router as runs_router
from app.api.routes.sandbox import router as sandbox_router
from app.api.routes.skills import router as skills_router
from app.api.routes.workspace import router as workspace_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(memory_router)
api_router.include_router(mcp_router)
api_router.include_router(auth_router)
api_router.include_router(rbac_router)
api_router.include_router(agents_router)
api_router.include_router(skills_router)
api_router.include_router(runs_router)
api_router.include_router(sandbox_router)
api_router.include_router(workspace_router)
