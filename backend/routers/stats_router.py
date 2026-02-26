from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import JSONResponse
from datetime import datetime

# Local imports
from ..database import database
from ..services.inventory_service import inventory_service

router = APIRouter()


@router.get("/api")
async def get_stats_api():
    """Get comprehensive statistics for dashboard"""
    try:
        stats = await database.get_stats()
        config = await database.get_config()
        settings = await database.get_settings()

        # Get lead counts by status
        scraped_count = await database.count_leads_by_status("SCRAPED")
        audited_count = await database.count_leads_by_status("AUDITED")
        emailed_count = await database.count_leads_by_status("EMAILED")

        # Calculate remaining inventory and quota
        remaining_inventory = max(0, audited_count)
        emails_remaining_quota = max(0, settings.daily_email_limit - stats.emails_sent_today)

        # Get current target
        current_target = await inventory_service.get_current_target(
            config.industry_idx,
            config.location_idx,
            config.state_idx
        )

        return {
            "stats": stats,
            "scraped_count": scraped_count,
            "audited_count": audited_count,
            "emailed_count": emailed_count,
            "remaining_inventory": remaining_inventory,
            "emails_remaining_quota": emails_remaining_quota,
            "daily_email_limit": settings.daily_email_limit,
            "current_target": current_target,
            "last_emailed_lead_id": config.last_emailed_lead_id
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"detail": str(e)}
        )