from fastapi import APIRouter, Form
from fastapi.responses import JSONResponse
from typing import Optional

# Local imports
from ..database import database

router = APIRouter()

@router.get("/api")
async def get_targets_api():
    """Get all targets as JSON"""
    try:
        targets = await database.get_all_targets()
        return {"targets": targets}
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": str(e)})

@router.post("/api")
async def add_target_api(
    industry: str = Form(...),
    country: str = Form(...),
    state: Optional[str] = Form(None)
):
    """Add a new target"""
    try:
        if not industry.strip() or not country.strip():
            return JSONResponse(status_code=400, content={"detail": "Industry and country are required"})
        
        await database.create_target({
            "industry": industry.strip(),
            "country": country.strip(),
            "state": state.strip() if state else None
        })
        
        return JSONResponse({
            "success": True,
            "message": "Target added successfully"
        })
        
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": f"Failed to add target: {str(e)}"})
