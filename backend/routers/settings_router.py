from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import JSONResponse, RedirectResponse
from typing import Optional

# Local imports
from ..database import database
from ..models import SettingsUpdateModel, SettingsModel

router = APIRouter()


@router.get("/api")
async def get_settings_api():
    """Get current settings as JSON"""
    try:
        settings = await database.get_settings()
        return settings
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"detail": str(e)}
        )


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
        # Build update data dictionary
        update_data = {}
        fields = [
            'serp_api_key', 'groq_api_key', 'smtp_host', 'smtp_port',
            'smtp_username', 'smtp_password', 'smtp_encryption',
            'from_name', 'from_email', 'telegram_bot_token',
            'telegram_chat_id', 'daily_email_limit', 'daily_serp_limit',
            'inventory_threshold'
        ]

        for field in fields:
            value = locals().get(field)
            if value is not None:
                update_data[field] = value

        # Validate encryption type
        if 'smtp_encryption' in update_data:
            if update_data['smtp_encryption'] not in ['SSL', 'TLS', 'NONE']:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid SMTP encryption type"}
                )

        # Update settings in database
        await database.update_settings(update_data)

        return JSONResponse({
            "success": True,
            "message": "Settings updated successfully"
        })

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"detail": f"Failed to update settings: {str(e)}"}
        )


@router.get("/test/telegram")
async def test_telegram():
    """Test Telegram connection"""
    try:
        from ..services.telegram_service import telegram_service

        if await telegram_service.is_configured():
            success = await telegram_service.send_message("✅ Telegram test message from Agency Engine")
            if success:
                return JSONResponse({
                    "success": True,
                    "message": "Test message sent successfully"
                })
            else:
                return JSONResponse({
                    "success": False,
                    "message": "Failed to send test message"
                })
        else:
            return JSONResponse({
                "success": False,
                "message": "Telegram not configured"
            })

    except Exception as e:
        return JSONResponse({
            "success": False,
            "message": f"Error testing Telegram: {str(e)}"
        })


@router.get("/test/smtp")
async def test_smtp():
    """Test SMTP configuration"""
    try:
        from ..services.email_service import email_service
        from ..database import database
        from ..models import LeadModel

        if not await email_service.is_configured():
            return JSONResponse({
                "success": False,
                "message": "SMTP not configured"
            })

        # Get first audited lead or create test recipient
        settings = await database.get_settings()
        if not settings.from_email:
            return JSONResponse({
                "success": False,
                "message": "From email not configured"
            })

        # Use the settings email as test recipient
        test_lead = LeadModel(
            id=0,
            business_name="Test",
            industry="Testing",
            country="Global",
            state=None,
            website=None,
            email=settings.from_email,
            load_time=None,
            ssl_status=None,
            h1_count=None,
            priority_score=0,
            audit_notes="Test email from Agency Engine",
            status="AUDITED",
            created_at=datetime.utcnow()
        )

        result = await email_service.send_outreach_email(
            lead=test_lead,
            opening_line="This is a test email from your Agency Engine."
        )

        return JSONResponse({
            "success": result.success,
            "message": result.message
        })

    except Exception as e:
        return JSONResponse({
            "success": False,
            "message": f"Error testing SMTP: {str(e)}"
        })