from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert

# Local imports
from ..database import database
from ..models import TargetModel

router = APIRouter()

@router.get("/api")
async def get_targets_api():
    targets = await database.get_all_targets()
    return {"targets": targets}

@router.post("/api")
async def add_target_api(
    industry: str,
    country: str,
    state: str = None
):
    if not industry or not country:
        return JSONResponse(status_code=400, content={"detail": "Industry and country required"})
    
    await database.create_target({
        "industry": industry.strip(),
        "country": country.strip(),
        "state": state.strip() if state else None
    })
    
    return JSONResponse({"success": True, "message": "Target added"})
