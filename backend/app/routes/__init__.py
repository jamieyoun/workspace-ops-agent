from app.routes.health import router as health_router
from app.routes.metrics import router as metrics_router
from app.routes.workspaces import router as workspaces_router
from app.routes.recommendations import router as recommendations_router
from app.routes.pages import router as pages_router

__all__ = ["health_router", "metrics_router", "workspaces_router", "recommendations_router", "pages_router"]
