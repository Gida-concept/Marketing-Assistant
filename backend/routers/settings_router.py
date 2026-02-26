from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import update

# Local imports
from ..database import database, Settings

# Template setup
templates = Jinja2Templates(directory="backend/templates")

router = APIRouter(tags=["settings"])

@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    settings = await database.get_settings()
    return templates.TemplateResponse("settings.html", {"request": request, "settings": settings})

@router.get("/settings/api")
async def get_settings_api():
    settings = await database.get_settings()
    return settings

@router.post("/settings/api")
async def update_settings_api(
    serp_api_key: str = Form(None),
    groq_api_key: str = Form(None),
    smtp_host: str = Form(None),
    smtp_port: int = Form(None),
    smtp_username: str = Form(None),
    smtp_password: str = Form(None),
    smtp_encryption: str = Form(None),
    from_name: str = Form(None),
    from_email: str = Form(None),
    telegram_bot_token: str = Form(None),
    telegram_chat_id: str = Form(None),
    daily_email_limit: int = Form(None),
    daily_serp_limit: int = Form(None),
    inventory_threshold: int = Form(None)
):
    update_data = {}
    fields = [
        'serp_api_key', 'groq_api_key', 'smtp_host', 'smtp_port',
        'smtp_username', 'smtp_password', 'smtp_encryption',
        'from_name', 'from_email', 'telegram_bot_token',
        'telegram_chat_id', 'daily_email_limit',
        'daily_serp_limit', 'inventory_threshold'
    ]
    for field in fields:
        value = locals().get(field)
        if value is not None:
            update_data[field] = value

    if 'smtp_encryption' in update_data:
        if update_data['smtp_encryption'] not in ['SSL', 'TLS', 'NONE']:
            return JSONResponse(status_code=400, content={"detail": "Invalid SMTP encryption"})

    async for session in database.get_session():
        await session.execute(update(Settings).where(Settings.id == 1).values(**update_data))
        await session.commit()

    return JSONResponse({"success": True, "message": "Settings updated"})

@router.get("/settings/test/telegram")
async def test_telegram():
    return JSONResponse({"success": True, "message": "Telegram test endpoint"})

@router.get("/settings/test/smtp")
async def test_smtp():
    return JSONResponse({"success": True, "message": "SMTP test endpoint"})
