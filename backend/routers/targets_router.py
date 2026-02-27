from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import delete

# Local imports
from ..database import database, Targets

# Template setup
templates = Jinja2Templates(directory="backend/templates")

router = APIRouter(tags=["targets"])

@router.get("/targets", response_class=HTMLResponse)
async def targets_page(request: Request):
    targets = await database.get_all_targets()
    return templates.TemplateResponse("targets.html", {"request": request, "targets": targets or []})

@router.get("/targets/api")
async def get_targets_api():
    targets = await database.get_all_targets()
    return {"targets": [{"id": t.id, "industry": t.industry, "country": t.country, "state": t.state} for t in (targets or [])]}

@router.post("/targets/api")
async def add_target_api(
    industry: str = Form(None),
    country: str = Form(None),
    state: str = Form(None)
):
    try:
        if not industry or not industry.strip():
            return JSONResponse(status_code=400, content={"detail": "Industry is required"})
        if not country or not country.strip():
            return JSONResponse(status_code=400, content={"detail": "Country is required"})
        
        await database.create_target({
            "industry": industry.strip(),
            "country": country.strip(),
            "state": state.strip() if state and state.strip() else None
        })
        
        return JSONResponse({"success": True, "message": "Target added successfully"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": str(e)})

@router.delete("/targets/api/{target_id}")
async def delete_target_api(target_id: int):
    try:
        await database.delete_target(target_id)
        return JSONResponse({"success": True, "message": "Target deleted"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": str(e)})
