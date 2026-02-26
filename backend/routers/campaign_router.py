from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

# Local imports
from ..database import database

# Template setup
templates = Jinja2Templates(directory="backend/templates")

router = APIRouter(tags=["campaign"])

@router.get("/campaign", response_class=HTMLResponse)
async def campaign_page(request: Request):
    engine_state = await database.get_engine_state()
    config = await database.get_config()
    stats = await database.get_stats()
    return templates.TemplateResponse("campaign.html", {
        "request": request,
        "engine_state": engine_state,
        "config": config,
        "stats": stats
    })

@router.get("/campaign/api/state")
async def get_engine_state_api():
    return {
        "engine_state": await database.get_engine_state(),
        "config": await database.get_config(),
        "stats": await database.get_stats()
    }

@router.post("/campaign/api/control")
async def control_engine_api(action: str = Form(...)):
    if action == "start":
        await database.update_engine_state(is_enabled=True)
        return JSONResponse({"success": True, "message": "Engine started"})
    elif action == "stop":
        await database.update_engine_state(is_enabled=False)
        return JSONResponse({"success": True, "message": "Engine stopped"})
    return JSONResponse(status_code=400, content={"detail": "Invalid action"})
