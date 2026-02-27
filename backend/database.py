import logging
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text, Float, select, update, delete
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from datetime import datetime

logger = logging.getLogger(__name__)
DATABASE_URL = "sqlite+aiosqlite:///./backend/agency.db"
Base = declarative_base()

# ... [Keep all your existing model classes: Settings, Targets, Leads, Config, EngineState, Stats] ...

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
            for Model in [Settings, EngineState, Config, Stats]:
                result = await session.execute(select(Model))
                if not result.scalars().first():
                    session.add(Model())
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

    # ... [Keep all your existing getter methods] ...

    async def save_lead(self,  dict):
        async for session in self.get_session():
            lead = Leads(**data)
            session.add(lead)
            await session.commit()
            logger.info(f"Saved lead: {lead.business_name} | {lead.website}")

    async def update_config(self, **kwargs):
        async for session in self.get_session():
            await session.execute(update(Config).where(Config.id == 1).values(**kwargs))
            await session.commit()

    async def get_target_by_indices(self, industry_idx: int, location_idx: int):
        targets = await self.get_all_targets()
        if not targets:
            return None
        return targets[industry_idx % len(targets)]

database = Database()
