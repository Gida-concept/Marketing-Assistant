from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

# Local imports
from ..database import database

# Template setup
templates = Jinja2Templates(directory="backend/templates")

router = APIRouter(tags=["stats"])

@router.get("/stats", response_class=HTMLResponse)
async def stats_page(request: Request):
    stats = await database.get_stats()
    settings = await database.get_settings()
    config = await database.get_config()
    scraped = await database.count_leads_by_status("SCRAPED")
    audited = await database.count_leads_by_status("AUDITED")
    emailed = await database.count_leads_by_status("EMAILED")
    return templates.TemplateResponse("stats.html", {
        "request": request,
        "stats": stats,
        "settings": settings,
        "config": config,
        "scraped_count": scraped,
        "audited_count": audited,
        "emailed_count": emailed
    })

@router.get("/stats/api")
async def get_stats_api():
    stats = await database.get_stats()
    settings = await database.get_settings()
    return {
        "stats": stats,
        "daily_email_limit": settings.daily_email_limit
    }
