# backend/main.py
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import database and scheduler after app setup to avoid circular imports
from .database import database
from .scheduler import scheduler

# Create templates instance
templates = Jinja2Templates(directory="backend/templates")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events."""
    try:
        await database.init_db()
        await scheduler.start()
        logger.info("Application startup complete.")
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise
    yield
    try:
        await scheduler.shutdown()
        logger.info("Application shutdown complete.")
    except Exception as e:
        logger.error(f"Shutdown failed: {e}")

# Create FastAPI app
app = FastAPI(lifespan=lifespan)

# Mount static files
app.mount("/static", StaticFiles(directory="backend/static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    try:
        engine_state = await database.get_engine_state()
        settings = await database.get_settings()
        config = await database.get_config()
        stats = await database.get_stats()

        return templates.TemplateResponse("index.html", {
            "request": request,
            "engine_state": engine_state,
            "settings": settings,
            "config": config,
            "stats": stats,
            "current_target": None
        })
    except Exception as e:
        logger.error(f"Error loading dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/engine/control")
async def control_engine(action: str = Form(...)):
    if action == "start":
        await database.update_engine_state(is_enabled=True)
        return JSONResponse({"success": True, "message": "Engine started"})
    elif action == "stop":
        await database.update_engine_state(is_enabled=False)
        return JSONResponse({"success": True, "message": "Engine stopped"})
    else:
        return JSONResponse({"success": False, "message": "Invalid action"}, status_code=400)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
