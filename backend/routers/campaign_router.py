from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from ..database import database
from ..engine import engine

templates = Jinja2Templates(directory="backend/templates")

router = APIRouter(tags=["campaign"])

@router.get("/campaign", response_class=HTMLResponse)
async def campaign_page(request: Request):
    engine_state = await database.get_engine_state()
    config = await database.get_config()
    stats = await database.get_stats()
    
    current_target = None
    targets = await database.get_all_targets()
    if targets:
        current_target = await database.get_target_by_indices(
            config.industry_idx, config.location_idx
        )
    
    return templates.TemplateResponse("campaign.html", {
        "request": request,
        "engine_state": engine_state,
        "config": config,
        "stats": stats,
        "current_target": current_target
    })

@router.get("/campaign/api/state")
async def get_engine_state_api():
    engine_state = await database.get_engine_state()
    config = await database.get_config()
    stats = await database.get_stats()
    
    current_target = None
    targets = await database.get_all_targets()
    if targets:
        current_target = await database.get_target_by_indices(
            config.industry_idx, config.location_idx
        )
    
    return {
        "engine_state": engine_state,
        "config": config,
        "stats": stats,
        "current_target": {
            "industry": current_target.industry,
            "country": current_target.country,
            "state": current_target.state
        } if current_target else None
    }

@router.post("/campaign/api/control")
async def control_engine_api(action: str = Form(...)):
    if action == "start":
        result = await engine.start()
        return JSONResponse(result)
    elif action == "stop":
        result = await engine.stop()
        return JSONResponse(result)
    return JSONResponse(status_code=400, content={"detail": "Invalid action"})

@router.post("/campaign/api/run")
async def manual_run_api():
    result = await engine.run()
    return JSONResponse(result)
