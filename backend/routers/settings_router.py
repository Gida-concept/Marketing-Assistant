from fastapi import APIRouter, Request, Form
from fastapi.responses import JSONResponse
from typing import Optional
import logging

# Local imports
from ..database import database

router = APIRouter()

@router.get("/api")
async def get_settings_api():
    """Get current settings as JSON"""
    try:
        settings = await database.get_settings()
        return settings
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": str(e)})

@router.post("/api")
async def update_settings_api(
    serp_api_key: Optional[str] = Form(None),
    groq_api_key: Optional[str] = Form(None),
    smtp_host: Optional[str] = Form(None),
    smtp_port: Optional[int] = Form(None),
    smtp_username: Optional[str] = Form(None),
    smtp_password: Optional[str] = Form(None),
    smtp_encryption: Optional[str] = Form(None),
    from_name: Optional[str] = Form(None),
    from_email: Optional[str] = Form(None),
    telegram_bot_token: Optional[str] = Form(None),
    telegram_chat_id: Optional[str] = Form(None),
    daily_email_limit: Optional[int] = Form(None),
    daily_serp_limit: Optional[int] = Form(None),
    inventory_threshold: Optional[int] = Form(None)
):
    """Update settings via form submission"""
    try:
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
                return JSONResponse(status_code=400, content={"detail": "Invalid SMTP encryption type"})

        await database.update_settings(update_data)
        
        return JSONResponse({
            "success": True,
            "message": "Settings updated successfully"
        })
        
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": f"Failed to update settings: {str(e)}"})
