from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Float, DateTime
from .config import DATABASE_URL

class Base(DeclarativeBase): pass
class User(Base):
    __tablename__="users"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    telegram_id:Mapped[int]=mapped_column(Integer,unique=True,index=True)
    balance:Mapped[float]=mapped_column(Float,default=0)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=lambda:datetime.now(timezone.utc))
class Order(Base):
    __tablename__="orders"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    user_id:Mapped[int]=mapped_column(Integer,index=True)
    provider:Mapped[str]=mapped_column(String(32))
    provider_order_id:Mapped[str]=mapped_column(String(128),index=True)
    service:Mapped[str]=mapped_column(String(32))
    country:Mapped[str]=mapped_column(String(64))
    phone:Mapped[str]=mapped_column(String(64),default="")
    cost:Mapped[float]=mapped_column(Float,default=0)
    price:Mapped[float]=mapped_column(Float,default=0)
    status:Mapped[str]=mapped_column(String(32),default="waiting")
    otp:Mapped[str]=mapped_column(String(64),default="")
    created_at:Mapped[datetime]=mapped_column(DateTime,default=lambda:datetime.now(timezone.utc))
class Payment(Base):
    __tablename__="payments"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    user_id:Mapped[int]=mapped_column(Integer,index=True)
    amount:Mapped[float]=mapped_column(Float)
    utr:Mapped[str]=mapped_column(String(128))
    status:Mapped[str]=mapped_column(String(32),default="pending")
    created_at:Mapped[datetime]=mapped_column(DateTime,default=lambda:datetime.now(timezone.utc))

engine=create_async_engine(DATABASE_URL)
Session=async_sessionmaker(engine,expire_on_commit=False)
async def init_db():
    async with engine.begin() as c: await c.run_sync(Base.metadata.create_all)
