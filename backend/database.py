import asyncio
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text, Float, select
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from datetime import datetime
import aiosqlite
import os

# Database configuration
DATABASE_URL = "sqlite+aiosqlite:///./backend/agency.db"
Base = declarative_base()


class Settings(Base):
    __tablename__ = 'settings'

    id = Column(Integer, primary_key=True)
    serp_api_key = Column(String(255), nullable=True)
    groq_api_key = Column(String(255), nullable=True)

    # SMTP Configuration
    smtp_host = Column(String(255), nullable=True)
    smtp_port = Column(Integer, default=587)
    smtp_username = Column(String(255), nullable=True)
    smtp_password = Column(String(255), nullable=True)
    smtp_encryption = Column(String(10), default='TLS')  # SSL, TLS, NONE

    from_name = Column(String(255), nullable=True)
    from_email = Column(String(255), nullable=True)

    # Telegram Configuration
    telegram_bot_token = Column(String(255), nullable=True)
    telegram_chat_id = Column(String(50), nullable=True)

    # System Limits
    daily_email_limit = Column(Integer, default=50)
    daily_serp_limit = Column(Integer, default=100)
    inventory_threshold = Column(Integer, default=200)


class Targets(Base):
    __tablename__ = 'targets'

    id = Column(Integer, primary_key=True)
    industry = Column(String(100), nullable=False)
    country = Column(String(100), nullable=False)
    state = Column(String(100), nullable=True)


class Leads(Base):
    __tablename__ = 'leads'

    id = Column(Integer, primary_key=True)
    business_name = Column(String(255), nullable=False)
    industry = Column(String(100), nullable=False)
    country = Column(String(100), nullable=False)
    state = Column(String(100), nullable=True)
    website = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    load_time = Column(Float, nullable=True)
    ssl_status = Column(Boolean, nullable=True)
    h1_count = Column(Integer, nullable=True)
    priority_score = Column(Integer, default=0)
    audit_notes = Column(Text, nullable=True)
    status = Column(String(20), default='SCRAPED')  # SCRAPED | AUDITED | EMAILED
    created_at = Column(DateTime, default=datetime.utcnow)


class Config(Base):
    __tablename__ = 'config'

    id = Column(Integer, primary_key=True)
    industry_idx = Column(Integer, default=0)
    location_idx = Column(Integer, default=0)
    state_idx = Column(Integer, default=0)
    pagination_start = Column(Integer, default=0)
    last_emailed_lead_id = Column(Integer, default=0)


class EngineState(Base):
    __tablename__ = 'engine_state'

    id = Column(Integer, primary_key=True)
    is_enabled = Column(Boolean, default=False)
    is_running = Column(Boolean, default=False)
    last_run_date = Column(DateTime, nullable=True)


class Stats(Base):
    __tablename__ = 'stats'

    id = Column(Integer, primary_key=True)
    emails_sent_today = Column(Integer, default=0)
    last_email_date = Column(DateTime, nullable=True)


class Database:
    def __init__(self):
        self.engine = create_async_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})
        self.async_session = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def init_db(self):
        """Initialize database and create tables if they don't exist"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Initialize default settings if not exists
        await self.init_default_settings()

    async def init_default_settings(self):
        """Initialize default settings record"""
        async with self.async_session() as session:
            result = await session.execute(select(Settings))
            settings = result.scalars().first()

            if not settings:
                default_settings = Settings(
                    smtp_port=587,
                    smtp_encryption='TLS',
                    daily_email_limit=50,
                    daily_serp_limit=100,
                    inventory_threshold=200
                )
                session.add(default_settings)
                await session.commit()

            # Initialize engine state if not exists
            result = await session.execute(select(EngineState))
            engine_state = result.scalars().first()

            if not engine_state:
                default_engine_state = EngineState(
                    is_enabled=False,
                    is_running=False
                )
                session.add(default_engine_state)
                await session.commit()

            # Initialize config if not exists
            result = await session.execute(select(Config))
            config = result.scalars().first()

            if not config:
                default_config = Config(
                    industry_idx=0,
                    location_idx=0,
                    state_idx=0,
                    pagination_start=0,
                    last_emailed_lead_id=0
                )
                session.add(default_config)
                await session.commit()

            # Initialize stats if not exists
            result = await session.execute(select(Stats))
            stats = result.scalars().first()

            if not stats:
                default_stats = Stats(
                    emails_sent_today=0
                )
                session.add(default_stats)
                await session.commit()

    async def get_session(self):
        """Get async database session"""
        async with self.async_session() as session:
            try:
                yield session
            except Exception as e:
                await session.rollback()
                raise e
            finally:
                await session.close()


# Global database instance
database = Database()