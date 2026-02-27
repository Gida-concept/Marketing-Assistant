from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from .database import database
from .scheduler import scheduler

templates = Jinja2Templates(directory="backend/templates")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.init_db()
    await scheduler.start()
    logger.info("Application startup complete.")
    yield
    await scheduler.shutdown()

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="backend/static"), name="static")

from .routers.settings_router import router as settings_router
from .routers.targets_router import router as targets_router
from .routers.campaign_router import router as campaign_router
from .routers.leads_router import router as leads_router
from .routers.stats_router import router as stats_router

app.include_router(settings_router)
app.include_router(targets_router)
app.include_router(campaign_router)
app.include_router(leads_router)
app.include_router(stats_router)

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    engine_state = await database.get_engine_state()
    settings = await database.get_settings()
    config = await database.get_config()
    stats = await database.get_stats()
    
    current_target = None
    targets = await database.get_all_targets()
    if targets:
        current_target = await database.get_target_by_indices(
            config.industry_idx, config.location_idx
        )
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "engine_state": engine_state,
        "settings": settings,
        "config": config,
        "stats": stats,
        "current_target": current_target
    })

@app.post("/engine/control")
async def control_engine(action: str = Form(...)):
    if action == "start":
        await database.update_engine_state(is_enabled=True)
        return JSONResponse({"success": True, "message": "Engine started"})
    elif action == "stop":
        await database.update_engine_state(is_enabled=False)
        return JSONResponse({"success": True, "message": "Engine stopped"})
    return JSONResponse({"success": False, "message": "Invalid action"}, status_code=400)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
