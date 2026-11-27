"""A self-contained product walkthrough with no database or external integrations."""

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route


def create_showcase(templates):
    async def page(request):
        path = request.path_params.get("path", "").strip("/")
        allowed = {"", "login", "compare", "events", "trends", "alerts", "history",
                   "assistant", "admin/sources", "admin/config", "integrations"}
        if path not in allowed and not (path.startswith("events/") and path[7:].isdigit()):
            return JSONResponse({"detail": "Demo route not found"}, status_code=404)
        return templates.TemplateResponse(request=request, name="showcase.html", context={})

    return Starlette(routes=[Route("/{path:path}", page)])
