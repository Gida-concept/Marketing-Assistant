import asyncio
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text, Float, select, update
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
    smtp_host = Column(String(255), nullable=True)
    smtp_port = Column(Integer, default=587)
    smtp_username = Column(String(255), nullable=True)
    smtp_password = Column(String(255), nullable=True)
    smtp_encryption = Column(String(10), default='TLS')
    from_name = Column(String(255), nullable=True)
    from_email = Column(String(255), nullable=True)
    telegram_bot_token = Column(String(255), nullable=True)
    telegram_chat_id = Column(String(50), nullable=True)
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
    status = Column(String(20), default='SCRAPED')
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
        self.async_session = sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)

    async def init_db(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await self.init_default_records()

    async def init_default_records(self):
        async for session in self.get_session():
            # Settings
            result = await session.execute(select(Settings))
            if not result.scalars().first():
                session.add(Settings())
                await session.commit()

            # EngineState
            result = await session.execute(select(EngineState))
            if not result.scalars().first():
                session.add(EngineState())
                await session.commit()

            # Config
            result = await session.execute(select(Config))
            if not result.scalars().first():
                session.add(Config())
                await session.commit()

            # Stats
            result = await session.execute(select(Stats))
            if not result.scalars().first():
                session.add(Stats())
                await session.commit()

    async def get_session(self):
        async with self.async_session() as session:
            try:
                yield session
            except Exception as e:
                await session.rollback()
                raise e
            finally:
                await session.close()

    # Getters
    async def get_settings(self):
        async for session in self.get_session():
            return (await session.execute(select(Settings).limit(1))).scalars().first()

    async def get_engine_state(self):
        async for session in self.get_session():
            return (await session.execute(select(EngineState).limit(1))).scalars().first()

    async def get_config(self):
        async for session in self.get_session():
            return (await session.execute(select(Config).limit(1))).scalars().first()

    async def get_stats(self):
        async for session in self.get_session():
            return (await session.execute(select(Stats).limit(1))).scalars().first()

    async def get_all_targets(self):
        async for session in self.get_session():
            return (await session.execute(select(Targets))).scalars().all()

    async def count_leads_by_status(self, status: str):
        async for session in self.get_session():
            result = await session.execute(select(Leads).where(Leads.status == status))
            return len(result.scalars().all())

    # Updaters
    async def update_settings(self, data: dict):
        async for session in self.get_session():
            await session.execute(update(Settings).values(**data))
            await session.commit()

    async def create_target(self, data: dict):
        async for session in self.get_session():
            target = Targets(**data)
            session.add(target)
            await session.commit()

# Global instance
database = Database()
