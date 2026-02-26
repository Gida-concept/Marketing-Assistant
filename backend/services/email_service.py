import asyncio
import logging
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

# Local imports
from ..database import database
from ..models import LeadModel, EmailSendResponseModel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self):
        self.smtp_client = None

    async def is_configured(self) -> bool:
        """Check if SMTP service is properly configured"""
        try:
            settings = await database.get_settings()
            required_fields = [
                settings.smtp_host,
                settings.smtp_port,
                settings.smtp_username,
                settings.smtp_password,
                settings.from_email
            ]
            return all(field for field in required_fields)
        except Exception as e:
            logger.error(f"Error checking email configuration: {str(e)}")
            return False

    async def send_outreach_email(self, lead: LeadModel, opening_line: str) -> EmailSendResponseModel:
        """
        Send personalized outreach email using configured SMTP settings
        Implements the exact connection logic based on encryption type
        """
        if not await self.is_configured():
            error_msg = "SMTP not configured - missing required settings"
            logger.error(error_msg)
            return EmailSendResponseModel(
                success=False,
                message=error_msg,
                lead_id=lead.id
            )

        try:
            settings = await database.get_settings()

            # Create message
            message = MIMEMultipart("alternative")
            message["Subject"] = f"Quick question about {lead.business_name}"
            message["From"] = f"{settings.from_name or settings.from_email} <{settings.from_email}>"
            message["To"] = lead.email

            # Generate personalized body content
            body_text = self._generate_email_body_text(lead, opening_line)
            body_html = self._generate_email_body_html(lead, opening_line)

            # Add HTML/plain-text parts to MIMEMultipart message
            message.attach(MIMEText(body_text, "plain"))
            message.attach(MIMEText(body_html, "html"))

            # SMTP Connection Logic (as specified)
            server = None
            try:
                if settings.smtp_encryption == "SSL":
                    # Use SMTP_SSL
                    context = ssl.create_default_context()
                    server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=context)
                    server.login(settings.smtp_username, settings.smtp_password)
                    logger.info(f"Connected via SMTP_SSL to {settings.smtp_host}:{settings.smtp_port}")

                elif settings.smtp_encryption == "TLS":
                    # Connect then starttls()
                    server = smtplib.SMTP(settings.smtp_host, settings.smtp_port)
                    server.ehlo()
                    context = ssl.create_default_context()
                    server.starttls(context=context)
                    server.ehlo()
                    server.login(settings.smtp_username, settings.smtp_password)
                    logger.info(f"Connected via STARTTLS to {settings.smtp_host}:{settings.smtp_port}")

                elif settings.smtp_encryption == "NONE":
                    # Plain SMTP
                    server = smtplib.SMTP(settings.smtp_host, settings.smtp_port)
                    server.ehlo()
                    if settings.smtp_username and settings.smtp_password:
                        server.login(settings.smtp_username, settings.smtp_password)
                    logger.info(f"Connected via plain SMTP to {settings.smtp_host}:{settings.smtp_port}")

                else:
                    error_msg = f"Invalid encryption type: {settings.smtp_encryption}"
                    logger.error(error_msg)
                    return EmailSendResponseModel(
                        success=False,
                        message=error_msg,
                        lead_id=lead.id
                    )

                # Send email
                server.send_message(message)
                server.quit()

                logger.info(f"Email sent successfully to {lead.email} (Lead ID: {lead.id})")
                return EmailSendResponseModel(
                    success=True,
                    message="Email sent successfully",
                    lead_id=lead.id
                )

            except smtplib.SMTPAuthenticationError as e:
                error_msg = f"SMTP Authentication failed: {str(e)}"
                logger.error(error_msg)
                return EmailSendResponseModel(
                    success=False,
                    message=error_msg,
                    lead_id=lead.id
                )
            except smtplib.SMTPConnectError as e:
                error_msg = f"SMTP Connection failed: {str(e)}"
                logger.error(error_msg)
                return EmailSendResponseModel(
                    success=False,
                    message=error_msg,
                    lead_id=lead.id
                )
            except smtplib.SMTPRecipientsRefused as e:
                error_msg = f"Recipient refused: {str(e)}"
                logger.error(error_msg)
                return EmailSendResponseModel(
                    success=False,
                    message=error_msg,
                    lead_id=lead.id
                )
            except Exception as e:
                error_msg = f"Failed to send email: {str(e)}"
                logger.error(error_msg, exc_info=True)
                return EmailSendResponseModel(
                    success=False,
                    message=error_msg,
                    lead_id=lead.id
                )
            finally:
                if server:
                    try:
                        server.quit()
                    except:
                        pass

        except Exception as e:
            error_msg = f"Unexpected error preparing email: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return EmailSendResponseModel(
                success=False,
                message=error_msg,
                lead_id=lead.id
            )

    def _generate_email_body_text(self, lead: LeadModel, opening_line: str) -> str:
        """Generate plain text version of email body"""
        closing = """
I'd love to explore how we might collaborate.
Looking forward to your thoughts.

Best regards,

[Your Name]
[Your Company]
[Your Website]
"""
        return f"{opening_line}\n\n{closing}".strip()

    def _generate_email_body_html(self, lead: LeadModel, opening_line: str) -> str:
        """Generate HTML version of email body"""
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <p>{opening_line}</p>

    <p>I'd love to explore how we might collaborate.<br>
    Looking forward to your thoughts.</p>

    <p>Best regards,<br>
    <strong>[Your Name]</strong><br>
    [Your Company]<br>
    <a href="https://yourwebsite.com">https://yourwebsite.com</a></p>
</body>
</html>
        """.strip()


# Global email_service instance
email_service = EmailService()