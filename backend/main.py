from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging

# Local imports
from .database import database
from .scheduler import scheduler

# Routers will be added later
from .routers.settings_router import router as settings_router
from .routers.targets_router import router as targets_router
from .routers.campaign_router import router as campaign_router
from .routers.leads_router import router as leads_router
from .routers.stats_router import router as stats_router

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.init_db()
    await scheduler.start()
    logger.info("Startup complete")
    yield
    await scheduler.shutdown()

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="backend/static"), name="static")
templates = Jinja2Templates(directory="backend/templates")

# Include routers
app.include_router(settings_router, prefix="/settings", tags=["settings"])
app.include_router(targets_router, prefix="/targets", tags=["targets"])
app.include_router(campaign_router, prefix="/campaign", tags=["campaign"])
app.include_router(leads_router, prefix="/leads", tags=["leads"])
app.include_router(stats_router, prefix="/stats", tags=["stats"])

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    engine_state = await database.get_engine_state()
    config = await database.get_config()
    stats = await database.get_stats()
    settings = await database.get_settings()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "engine_state": engine_state,
        "config": config,
        "stats": stats,
        "settings": settings,
        "current_target": None
    })

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
