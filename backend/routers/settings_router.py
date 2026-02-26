from fastapi import APIRouter, Request, Form
from fastapi.responses import JSONResponse

# Local imports
from ..database import database

router = APIRouter()

@router.get("/api")
async def get_settings_api():
    settings = await database.get_settings()
    return settings

@router.post("/api")
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
    # Build update data
    update_data = {}
    for field in ['serp_api_key', 'groq_api_key', 'smtp_host', 'smtp_port',
                  'smtp_username', 'smtp_password', 'smtp_encryption',
                  'from_name', 'from_email', 'telegram_bot_token',
                  'telegram_chat_id', 'daily_email_limit',
                  'daily_serp_limit', 'inventory_threshold']:
        value = locals().get(field)
        if value is not None:
            update_data[field] = value

    # Validate encryption type
    if 'smtp_encryption' in update_data:
        if update_data['smtp_encryption'] not in ['SSL', 'TLS', 'NONE']:
            return JSONResponse(status_code=400, content={"detail": "Invalid SMTP encryption"})

    # Update database
    async for session in database.get_session():
        await session.execute(
            update(database.Settings).where(database.Settings.id == 1).values(**update_data)
        )
        await session.commit()

    return JSONResponse({"success": True, "message": "Settings saved"})
