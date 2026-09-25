from aiogram import Router,F
from aiogram.types import Message,CallbackQuery,InlineKeyboardMarkup,InlineKeyboardButton
from aiogram.filters import Command
from sqlalchemy import select
from .db import Session,User,Payment,Order
from .router import catalog,buy_best
from .pricing import sell_price
from .config import OWNER_ID,UPI_ID
r=Router()
async def get_user(tg):
    async with Session() as s:
        q=await s.execute(select(User).where(User.telegram_id==tg)); u=q.scalar_one_or_none()
        if not u: u=User(telegram_id=tg); s.add(u); await s.commit(); await s.refresh(u)
        return u
@r.message(Command("start"))
async def start(m:Message):
    u=await get_user(m.from_user.id)
    await m.answer(f"👋 Welcome\n\n💰 Balance: ₹{u.balance:.2f}\n\n/buy — Buy a number\n/deposit — Add balance")
@r.message(Command("balance"))
async def balance(m:Message):
    u=await get_user(m.from_user.id); await m.answer(f"💰 Balance: ₹{u.balance:.2f}")
@r.message(Command("deposit"))
async def deposit(m:Message):
    await m.answer(f"💳 UPI deposit\n\nUPI ID: `{UPI_ID or 'SET_UPI_ID_IN_ENV'}`\n\nAfter paying: /paid AMOUNT UTR",parse_mode="Markdown")
@r.message(Command("paid"))
async def paid(m:Message):
    p=m.text.split()
    if len(p)!=3: return await m.answer("Usage: /paid AMOUNT UTR")
    try: amount=float(p[1])
    except: return await m.answer("Invalid amount")
    async with Session() as s: s.add(Payment(user_id=m.from_user.id,amount=amount,utr=p[2])); await s.commit()
    await m.answer("✅ Payment submitted for admin verification.")
@r.message(Command("buy"))
async def buy(m:Message):
    await m.answer("Select service:",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Telegram",callback_data="svc:tg"),InlineKeyboardButton(text="WhatsApp",callback_data="svc:wa")]]))
@r.callback_query(F.data.startswith("svc:"))
async def service(c:CallbackQuery):
    svc=c.data.split(":")[1]; items=await catalog(svc)
    if not items: return await c.message.edit_text("No numbers available.")
    rows=[[InlineKeyboardButton(text=f"{x.country_name} • ₹{sell_price(x.cost_rupees):.0f}",callback_data=f"buy:{svc}:{x.country}")] for x in items[:80]]
    await c.message.edit_text("🌍 Select country:",reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)); await c.answer()
@r.callback_query(F.data.startswith("buy:"))
async def purchase(c:CallbackQuery):
    _,svc,country=c.data.split(":",2); u=await get_user(c.from_user.id)
    x=next((i for i in await catalog(svc) if i.country==country),None)
    if not x: return await c.answer("Unavailable",show_alert=True)
    price=sell_price(x.cost_rupees)
    if u.balance<price: return await c.answer(f"Need ₹{price:.0f}",show_alert=True)
    try: p,a=await buy_best(svc,country,f"tg-{c.from_user.id}-{c.id}")
    except: return await c.answer("No provider could complete it.",show_alert=True)
    async with Session() as s:
        u2=(await s.execute(select(User).where(User.telegram_id==c.from_user.id))).scalar_one()
        u2.balance-=price
        s.add(Order(user_id=u2.telegram_id,provider=p.name,provider_order_id=a.order_id,service=svc,country=country,phone=a.phone,cost=a.cost_rupees,price=price))
        await s.commit()
    await c.message.edit_text(f"✅ Number: `{a.phone}`\n💰 ₹{price:.0f}\n\n⏳ Waiting for OTP…",parse_mode="Markdown"); await c.answer()
@r.message(Command("admin"))
async def admin(m:Message):
    if m.from_user.id!=OWNER_ID: return
    async with Session() as s:
        u=len((await s.execute(select(User))).scalars().all()); p=len((await s.execute(select(Payment).where(Payment.status=="pending"))).scalars().all()); o=len((await s.execute(select(Order))).scalars().all())
    await m.answer(f"👑 Admin\nUsers: {u}\nPending payments: {p}\nOrders: {o}\n/approve ID")
@r.message(Command("approve"))
async def approve(m:Message):
    if m.from_user.id!=OWNER_ID: return
    parts=m.text.split()
    if len(parts)!=2: return await m.answer("Usage: /approve ID")
    async with Session() as s:
        p=await s.get(Payment,int(parts[1]))
        if not p or p.status!="pending": return await m.answer("Not found/pending")
        u=(await s.execute(select(User).where(User.telegram_id==p.user_id))).scalar_one(); u.balance+=p.amount; p.status="approved"; await s.commit()
    await m.answer("✅ Payment approved.")
