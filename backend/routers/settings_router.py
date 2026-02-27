from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import smtplib
from email.message import EmailMessage
import httpx

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
    fields = ['serp_api_key', 'groq_api_key', 'smtp_host', 'smtp_port',
              'smtp_username', 'smtp_password', 'smtp_encryption',
              'from_name', 'from_email', 'telegram_bot_token',
              'telegram_chat_id', 'daily_email_limit',
              'daily_serp_limit', 'inventory_threshold']
    for field in fields:
        value = locals().get(field)
        if value is not None:
            update_data[field] = value

    if 'smtp_encryption' in update_:
        if update_data['smtp_encryption'] not in ['SSL', 'TLS', 'NONE']:
            return JSONResponse(status_code=400, content={"detail": "Invalid SMTP encryption type"})

    async for session in database.get_session():
        await session.execute("UPDATE settings SET " + ", ".join([f"{k} = ?" for k in update_data.keys()]) + " WHERE id = 1", list(update_data.values()))
        await session.commit()

    return JSONResponse({"success": True, "message": "Settings updated successfully"})

@router.get("/settings/test/smtp")
async def test_smtp():
    settings = await database.get_settings()
    
    if not all([settings.smtp_host, settings.smtp_port, settings.smtp_username, settings.smtp_password, settings.from_email]):
        return JSONResponse(status_code=400, content={"success": False, "message": "Missing SMTP configuration"})
    
    try:
        msg = EmailMessage()
        msg.set_content("SMTP test from Agency Engine")
        msg["Subject"] = "✅ SMTP Test Successful"
        msg["From"] = f"{settings.from_name or 'Agency Engine'} <{settings.from_email}>"
        msg["To"] = settings.from_email  # Send to self
        
        if settings.smtp_encryption == "SSL":
            server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=10)
        else:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10)
            if settings.smtp_encryption == "TLS":
                server.starttls()
        
        server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(msg)
        server.quit()
        
        return JSONResponse({"success": True, "message": f"SMTP test email sent to {settings.from_email}"})
    
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "message": f"SMTP test failed: {str(e)}"})

@router.get("/settings/test/telegram")
async def test_telegram():
    settings = await database.get_settings()
    
    if not all([settings.telegram_bot_token, settings.telegram_chat_id]):
        return JSONResponse(status_code=400, content={"success": False, "message": "Missing Telegram configuration"})
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                json={
                    "chat_id": settings.telegram_chat_id,
                    "text": "✅ Telegram test from Agency Engine"
                }
            )
            if response.status_code == 200:
                return JSONResponse({"success": True, "message": "Telegram test message sent"})
            else:
                return JSONResponse(status_code=500, content={"success": False, "message": f"Telegram API error: {response.text}"})
    
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "message": f"Telegram test failed: {str(e)}"})
