from fastapi import FastAPI, Request, Form, HTTPException, Depends, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging

# Local imports
from .database import database, lifespan
from .models import *
from .services.telegram_service import telegram_service

# Router imports
from .routers import settings_router, targets_router, campaign_router, leads_router, stats_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    """Override default lifespan to include our scheduler and database"""
    await lifespan(app)
    yield


# Create FastAPI app with lifespan handler
app = FastAPI(lifespan=app_lifespan)

# Mount static files
app.mount("/static", StaticFiles(directory="backend/static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="backend/templates")

# Include routers
app.include_router(settings_router.router, prefix="/settings", tags=["settings"])
app.include_router(targets_router.router, prefix="/targets", tags=["targets"])
app.include_router(campaign_router.router, prefix="/campaign", tags=["campaign"])
app.include_router(leads_router.router, prefix="/leads", tags=["leads"])
app.include_router(stats_router.router, prefix="/stats", tags=["stats"])


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Dashboard home page"""
    try:
        engine_state = await database.get_engine_state()
        settings = await database.get_settings()
        config = await database.get_config()
        stats = await database.get_stats()

        # Get current target
        current_target_data = None
        if config.industry_idx is not None and config.location_idx is not None:
            current_target = await database.get_target_by_indices(
                config.industry_idx,
                config.location_idx
            )
            if current_target:
                current_target_data = {
                    "industry": current_target.industry,
                    "country": current_target.country,
                    "state": current_target.state
                }

        return templates.TemplateResponse("index.html", {
            "request": request,
            "engine_state": engine_state,
            "settings": settings,
            "config": config,
            "stats": stats,
            "current_target": current_target_data
        })
    except Exception as e:
        logger.error(f"Error loading dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/settings", response_class=HTMLResponse)
async def get_settings_page(request: Request):
    """Settings configuration page"""
    try:
        settings = await database.get_settings()
        return templates.TemplateResponse("settings.html", {
            "request": request,
            "settings": settings
        })
    except Exception as e:
        logger.error(f"Error loading settings page: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/targets", response_class=HTMLResponse)
async def get_targets_page(request: Request):
    """Targets management page"""
    try:
        targets = await database.get_all_targets()
        return templates.TemplateResponse("targets.html", {
            "request": request,
            "targets": targets
        })
    except Exception as e:
        logger.error(f"Error loading targets page: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/campaign", response_class=HTMLResponse)
async def get_campaign_page(request: Request):
    """Campaign monitoring page"""
    try:
        engine_state = await database.get_engine_state()
        config = await database.get_config()
        stats = await database.get_stats()

        # Get current target
        current_target_data = None
        if config.industry_idx is not None and config.location_idx is not None:
            current_target = await database.get_target_by_indices(
                config.industry_idx,
                config.location_idx
            )
            if current_target:
                current_target_data = {
                    "industry": current_target.industry,
                    "country": current_target.country,
                    "state": current_target.state
                }

        return templates.TemplateResponse("campaign.html", {
            "request": request,
            "engine_state": engine_state,
            "config": config,
            "stats": stats,
            "current_target": current_target_data
        })
    except Exception as e:
        logger.error(f"Error loading campaign page: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/leads", response_class=HTMLResponse)
async def get_leads_page(request: Request):
    """Leads management page"""
    try:
        leads = await database.get_all_leads()
        return templates.TemplateResponse("leads.html", {
            "request": request,
            "leads": leads
        })
    except Exception as e:
        logger.error(f"Error loading leads page: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/stats", response_class=HTMLResponse)
async def get_stats_page(request: Request):
    """Statistics and reporting page"""
    try:
        stats = await database.get_stats()
        config = await database.get_config()
        settings = await database.get_settings()

        # Get lead counts by status
        scraped_count = await database.count_leads_by_status("SCRAPED")
        audited_count = await database.count_leads_by_status("AUDITED")
        emailed_count = await database.count_leads_by_status("EMAILED")

        # Calculate remaining inventory and quota
        remaining_inventory = max(0, audited_count)
        emails_remaining_quota = max(0, settings.daily_email_limit - stats.emails_sent_today)

        return templates.TemplateResponse("stats.html", {
            "request": request,
            "stats": stats,
            "scraped_count": scraped_count,
            "audited_count": audited_count,
            "emailed_count": emailed_count,
            "remaining_inventory": remaining_inventory,
            "emails_remaining_quota": emails_remaining_quota,
            "daily_email_limit": settings.daily_email_limit
        })
    except Exception as e:
        logger.error(f"Error loading stats page: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/engine/control")
async def control_engine(action: str = Form(...)):
    """Control engine state from frontend"""
    if action == "start":
        await database.update_engine_state(is_enabled=True)
        logger.info("Engine enabled via web interface")
        return JSONResponse({"success": True, "message": "Engine started"})
    elif action == "stop":
        await database.update_engine_state(is_enabled=False)
        logger.info("Engine disabled via web interface")
        return JSONResponse({"success": True, "message": "Engine stopped"})
    else:
        raise HTTPException(status_code=400, detail="Invalid action")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        await database.test_connection()
        return {"status": "healthy", "timestamp": datetime.utcnow()}
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Unhealthy")