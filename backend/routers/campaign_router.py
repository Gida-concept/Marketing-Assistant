from fastapi import APIRouter
from fastapi.responses import JSONResponse

# Local imports
from ..database import database

router = APIRouter()

@router.get("/api/state")
async def get_engine_state_api():
    engine_state = await database.get_engine_state()
    config = await database.get_config()
    stats = await database.get_stats()
    return {
        "engine_state": engine_state,
        "config": config,
        "stats": stats
    }
