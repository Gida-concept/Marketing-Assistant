from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import JSONResponse
from datetime import datetime

# Local imports
from ..database import database
from ..models import EngineStateModel, ConfigModel, StatsModel

router = APIRouter()


@router.get("/api/state")
async def get_engine_state_api():
    """Get current engine state"""
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

        return {
            "engine_state": engine_state,
            "config": config,
            "stats": stats,
            "current_target": current_target_data
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"detail": str(e)}
        )


@router.post("/api/control")
async def control_engine_api(action: str = Form(...)):
    """Control engine state"""
    try:
        if action == "start":
            await database.update_engine_state(is_enabled=True)
            return JSONResponse({
                "success": True,
                "message": "Engine started"
            })
        elif action == "stop":
            await database.update_engine_state(is_enabled=False)
            return JSONResponse({
                "success": True,
                "message": "Engine stopped"
            })
        else:
            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid action"}
            )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"detail": f"Failed to control engine: {str(e)}"}
        )


@router.post("/api/run")
async def manual_run_api():
    """Trigger manual engine run"""
    try:
        from ..engine import engine

        # Start engine manually
        asyncio.create_task(engine.run())

        return JSONResponse({
            "success": True,
            "message": "Manual execution triggered"
        })
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"detail": f"Failed to start manual run: {str(e)}"}
        )