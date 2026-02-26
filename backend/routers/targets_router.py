from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import JSONResponse
from typing import Optional

# Local imports
from ..database import database
from ..models import TargetModel

router = APIRouter()


@router.get("/api")
async def get_targets_api():
    """Get all targets as JSON"""
    try:
        targets = await database.get_all_targets()
        return {"targets": targets}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"detail": str(e)}
        )


@router.post("/api")
async def add_target_api(
        industry: str = Form(...),
        country: str = Form(...),
        state: Optional[str] = Form(None)
):
    """Add a new target"""
    try:
        # Validate required fields
        if not industry or not country:
            return JSONResponse(
                status_code=400,
                content={"detail": "Industry and country are required"}
            )

        # Create target
        target_data = {
            "industry": industry.strip(),
            "country": country.strip(),
            "state": state.strip() if state else None
        }

        await database.create_target(target_data)

        return JSONResponse({
            "success": True,
            "message": "Target added successfully"
        })

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"detail": f"Failed to add target: {str(e)}"}
        )


@router.delete("/api/{target_id}")
async def delete_target_api(target_id: int):
    """Delete a target by ID"""
    try:
        success = await database.delete_target(target_id)
        if success:
            return JSONResponse({
                "success": True,
                "message": "Target deleted successfully"
            })
        else:
            return JSONResponse(
                status_code=404,
                content={"detail": "Target not found"}
            )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"detail": f"Failed to delete target: {str(e)}"}
        )