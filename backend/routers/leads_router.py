from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import JSONResponse
from typing import Optional

# Local imports
from ..database import database
from ..models import LeadModel, LeadStatus

router = APIRouter()


@router.get("/api")
async def get_leads_api(
        status: Optional[str] = None,
        industry: Optional[str] = None,
        country: Optional[str] = None,
        min_priority: Optional[int] = None
):
    """Get leads with optional filtering"""
    try:
        # Build filter criteria
        filters = {}
        if status and status in ['SCRAPED', 'AUDITED', 'EMAILED']:
            filters['status'] = status
        if industry:
            filters['industry'] = industry.strip()
        if country:
            filters['country'] = country.strip()
        if min_priority is not None:
            filters['min_priority'] = max(0, min_priority)

        leads = await database.get_filtered_leads(filters)
        return {"leads": leads}

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"detail": str(e)}
        )


@router.get("/api/count")
async def get_leads_count_api():
    """Get count of leads by status"""
    try:
        scraped = await database.count_leads_by_status("SCRAPED")
        audited = await database.count_leads_by_status("AUDITED")
        emailed = await database.count_leads_by_status("EMAILED")

        return {
            "scraped": scraped,
            "audited": audited,
            "emailed": emailed,
            "total": scraped + audited + emailed
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"detail": str(e)}
        )