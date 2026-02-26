from fastapi import APIRouter
from fastapi.responses import JSONResponse

# Local imports
from ..database import database

router = APIRouter()

@router.get("/api")
async def get_stats_api():
    stats = await database.get_stats()
    settings = await database.get_settings()
    config = await database.get_config()
    
    scraped = await database.count_leads_by_status("SCRAPED")
    audited = await database.count_leads_by_status("AUDITED")
    emailed = await database.count_leads_by_status("EMAILED")

    return {
        "stats": stats,
        "scraped_count": scraped,
        "audited_count": audited,
        "emailed_count": emailed,
        "remaining_inventory": max(0, audited),
        "emails_remaining_quota": max(0, settings.daily_email_limit - stats.emails_sent_today),
        "daily_email_limit": settings.daily_email_limit,
        "last_emailed_lead_id": config.last_emailed_lead_id
    }
