# backend/main.py
from fastapi import FastAPI, Request, Form, HTTPException, Depends, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging

# Local imports
from .database import database
from .scheduler import scheduler

# Router imports (we'll define them properly later)
try:
    from .routers import settings_router, targets_router, campaign_router, leads_router, stats_router
except ImportError:
    pass  # Handle dynamically

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan handler for startup and shutdown"""
    # Startup
    await database.init_db()
    await scheduler.start()
    logger.info("Application startup complete.")
    
    yield  # App runs here
    
    # Shutdown
    await scheduler.shutdown()
    logger.info("Application shutdown complete.")

# Create FastAPI app with lifespan
app = FastAPI(lifespan=lifespan)

# Mount static files
app.mount("/static", StaticFiles(directory="backend/static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="backend/templates")

# Include routers (basic fallback if not found)
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return HTMLResponse("Agency Engine Dashboard — API Running")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
