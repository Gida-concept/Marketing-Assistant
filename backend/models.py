from pydantic import BaseModel, Field, validator, HttpUrl, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class SMPEncryption(str, Enum):
    SSL = "SSL"
    TLS = "TLS"
    NONE = "NONE"


class SettingsModel(BaseModel):
    # API Keys
    serp_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None

    # SMTP Configuration
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = Field(587, ge=1, le=65535)
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_encryption: SMPEncryption = SMPEncryption.TLS
    from_name: Optional[str] = None
    from_email: Optional[EmailStr] = None

    # Telegram Configuration
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None

    # System Limits
    daily_email_limit: Optional[int] = Field(50, ge=1, le=1000)
    daily_serp_limit: Optional[int] = Field(100, ge=1, le=1000)
    inventory_threshold: Optional[int] = Field(200, ge=1, le=10000)

    class Config:
        orm_mode = True
        schema_extra = {
            "example": {
                "serp_api_key": "your-serpapi-key",
                "groq_api_key": "your-groq-key",
                "smtp_host": "smtp.example.com",
                "smtp_port": 587,
                "smtp_username": "user@example.com",
                "smtp_password": "password",
                "smtp_encryption": "TLS",
                "from_name": "John Doe",
                "from_email": "john@example.com",
                "telegram_bot_token": "your-telegram-bot-token",
                "telegram_chat_id": "123456789",
                "daily_email_limit": 50,
                "daily_serp_limit": 100,
                "inventory_threshold": 200
            }
        }


class SettingsUpdateModel(BaseModel):
    # API Keys (all optional for partial updates)
    serp_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None

    # SMTP Configuration
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = Field(None, ge=1, le=65535)
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_encryption: Optional[SMPEncryption] = None
    from_name: Optional[str] = None
    from_email: Optional[EmailStr] = None

    # Telegram Configuration
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None

    # System Limits
    daily_email_limit: Optional[int] = Field(None, ge=1, le=1000)
    daily_serp_limit: Optional[int] = Field(None, ge=1, le=1000)
    inventory_threshold: Optional[int] = Field(None, ge=1, le=10000)

    @validator('smtp_port')
    def validate_smtp_port(cls, v):
        if v is not None and (v < 1 or v > 65535):
            raise ValueError('SMTP port must be between 1 and 65535')
        return v


class TargetModel(BaseModel):
    industry: str = Field(..., min_length=1, max_length=100)
    country: str = Field(..., min_length=1, max_length=100)
    state: Optional[str] = Field(None, max_length=100)


class LeadStatus(str, Enum):
    SCRAPED = "SCRAPED"
    AUDITED = "AUDITED"
    EMAILED = "EMAILED"


class LeadModel(BaseModel):
    id: int
    business_name: str
    industry: str
    country: str
    state: Optional[str]
    website: Optional[HttpUrl]
    email: Optional[EmailStr]
    load_time: Optional[float]
    ssl_status: Optional[bool]
    h1_count: Optional[int]
    priority_score: int = 0
    audit_notes: Optional[str]
    status: LeadStatus
    created_at: datetime

    class Config:
        orm_mode = True


class LeadCreateModel(BaseModel):
    business_name: str = Field(..., min_length=1, max_length=255)
    industry: str = Field(..., min_length=1, max_length=100)
    country: str = Field(..., min_length=1, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    website: Optional[HttpUrl] = None
    email: Optional[EmailStr] = None
    load_time: Optional[float] = None
    ssl_status: Optional[bool] = None
    h1_count: Optional[int] = None
    priority_score: int = 0
    audit_notes: Optional[str] = None
    status: LeadStatus = LeadStatus.SCRAPED


class LeadUpdateModel(BaseModel):
    website: Optional[HttpUrl] = None
    email: Optional[EmailStr] = None
    load_time: Optional[float] = None
    ssl_status: Optional[bool] = None
    h1_count: Optional[int] = None
    priority_score: Optional[int] = None
    audit_notes: Optional[str] = None
    status: Optional[LeadStatus] = None


class ConfigModel(BaseModel):
    industry_idx: int = Field(0, ge=0)
    location_idx: int = Field(0, ge=0)
    state_idx: int = Field(0, ge=0)
    pagination_start: int = Field(0, ge=0)
    last_emailed_lead_id: int = Field(0, ge=0)

    class Config:
        orm_mode = True


class EngineStateModel(BaseModel):
    is_enabled: bool = False
    is_running: bool = False
    last_run_date: Optional[datetime] = None

    class Config:
        orm_mode = True


class StatsModel(BaseModel):
    emails_sent_today: int = Field(0, ge=0)
    last_email_date: Optional[datetime] = None

    class Config:
        orm_mode = True


class AuditRequestModel(BaseModel):
    url: HttpUrl


class AuditResponseModel(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PersonalizationRequestModel(BaseModel):
    audit_notes: str = Field(..., min_length=1)


class PersonalizationResponseModel(BaseModel):
    success: bool
    opening_line: Optional[str] = None
    error: Optional[str] = None


class EmailSendResponseModel(BaseModel):
    success: bool
    message: str
    lead_id: int


class CampaignStatsModel(BaseModel):
    total_leads: int
    scraped_count: int
    audited_count: int
    emailed_count: int
    current_target: Optional[Dict[str, str]] = None
    remaining_inventory: int
    emails_remaining_quota: int


class TelegramReportModel(BaseModel):
    message: str
    bot_token: str
    chat_id: str


class ErrorResponseModel(BaseModel):
    detail: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class BulkOperationResponseModel(BaseModel):
    success: bool
    processed: int
    failed: int
    errors: List[str] = []