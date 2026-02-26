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
    return templates.TemplateResponse("targets.html", {"request": request, "targets": targets})

@router.get("/targets/api")
async def get_targets_api():
    targets = await database.get_all_targets()
    return {"targets": targets}

@router.post("/targets/api")
async def add_target_api(
    industry: str = Form(...),
    country: str = Form(...),
    state: str = Form(None)
):
    if not industry or not country:
        return JSONResponse(status_code=400, content={"detail": "Industry and country required"})
    
    await database.create_target({
        "industry": industry.strip(),
        "country": country.strip(),
        "state": state.strip() if state else None
    })
    
    return JSONResponse({"success": True, "message": "Target added"})

@router.delete("/targets/api/{target_id}")
async def delete_target_api(target_id: int):
    await database.delete_target(target_id)
    return JSONResponse({"success": True, "message": "Target deleted"})
