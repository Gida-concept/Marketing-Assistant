# backend/routers/leads_router.py
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from ..database import database

router = APIRouter(tags=["leads"])

@router.get("/leads", response_class=HTMLResponse)
async def leads_page(request: Request):
    leads = await database.get_all_leads()
    return templates.TemplateResponse("leads.html", {"request": request, "leads": leads})

@router.get("/leads/api")
async def get_leads_api():
    leads = await database.get_all_leads()
    return {"leads": leads}
