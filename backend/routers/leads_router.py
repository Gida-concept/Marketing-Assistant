from fastapi import APIRouter
from fastapi.responses import JSONResponse

# Local imports
from ..database import database

router = APIRouter()

@router.get("/api")
async def get_leads_api():
    async for session in database.get_session():
        result = await session.execute("SELECT * FROM leads ORDER BY id DESC")
        rows = result.fetchall()
        keys = result.keys()
        leads = [dict(zip(keys, row)) for row in rows]
        return {"leads": leads}
