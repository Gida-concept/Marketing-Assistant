from fastapi import FastAPI, Request, Form, HTTPException, Depends, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging

# Local imports
from .database import database
from .scheduler import scheduler

# Router imports
from .routers import settings_router, targets_router, campaign_router, leads_router, stats_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Override default lifespan to include our scheduler and database"""
    await database.init_db()
    await scheduler.start()
    logger.info("Application startup complete.")
    
    yield
    
    await scheduler.shutdown()
    logger.info("Application shutdown complete.")

# Create FastAPI app with lifespan handler
app = FastAPI(lifespan=lifespan)

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
