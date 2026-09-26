from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from sqlalchemy import select, func
from .db import Session, User, Payment, Order
from .router import catalog, buy_best
from .pricing import sell_price
from .config import OWNER_ID, UPI_ID
from .country_display import format_country

r = Router()

def home_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Buy Account", callback_data="menu:buy"), InlineKeyboardButton(text="Add Balance", callback_data="menu:deposit")],
        [InlineKeyboardButton(text="History", callback_data="menu:history"), InlineKeyboardButton(text="Profile", callback_data="menu:profile")],
        [InlineKeyboardButton(text="How To Use", callback_data="menu:howto")],
    ])

def back_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Back", callback_data="menu:home")]])

async def get_user(tg):
    async with Session() as s:
        q = await s.execute(select(User).where(User.telegram_id == tg))
        u = q.scalar_one_or_none()
        if not u:
            u = User(telegram_id=tg)
            s.add(u)
            await s.commit()
            await s.refresh(u)
        return u

async def show_home(target, tg_id):
    u = await get_user(tg_id)
    text = f"👋 Welcome\n\n💰 Balance: ₹{u.balance:.2f}"
    await target.edit_text(text, reply_markup=home_keyboard())

@r.message(Command("start"))
async def start(m: Message):
    u = await get_user(m.from_user.id)
    await m.answer(f"👋 Welcome\n\n💰 Balance: ₹{u.balance:.2f}", reply_markup=home_keyboard())

@r.message(Command("balance"))
async def balance(m: Message):
    u = await get_user(m.from_user.id)
    await m.answer(f"💰 Balance: ₹{u.balance:.2f}")

async def deposit_text():
    return f"💳 Add Balance\n\nUPI ID: `{UPI_ID or 'SET_UPI_ID_IN_ENV'}`\n\nAfter paying, send: /paid AMOUNT UTR"

@r.message(Command("deposit"))
async def deposit(m: Message):
    await m.answer(await deposit_text(), parse_mode="Markdown", reply_markup=back_keyboard())

@r.message(Command("paid"))
async def paid(m: Message):
    p = m.text.split()
    if len(p) != 3:
        return await m.answer("Usage: /paid AMOUNT UTR")
    try:
        amount = float(p[1])
    except Exception:
        return await m.answer("Invalid amount")
    async with Session() as s:
        s.add(Payment(user_id=m.from_user.id, amount=amount, utr=p[2]))
        await s.commit()
    await m.answer("✅ Payment submitted for admin verification.")

@r.message(Command("buy"))
async def buy(m: Message):
    await m.answer("Select service:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Telegram", callback_data="svc:tg"),
        InlineKeyboardButton(text="WhatsApp", callback_data="svc:wa")
    ], [InlineKeyboardButton(text="◀️ Back", callback_data="menu:home")]]))

@r.callback_query(F.data == "menu:home")
async def menu_home(c: CallbackQuery):
    await show_home(c.message, c.from_user.id)
    await c.answer()

@r.callback_query(F.data == "menu:buy")
async def menu_buy(c: CallbackQuery):
    await c.message.edit_text("Select service:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Telegram", callback_data="svc:tg"),
        InlineKeyboardButton(text="WhatsApp", callback_data="svc:wa")
    ], [InlineKeyboardButton(text="◀️ Back", callback_data="menu:home")]]))
    await c.answer()

@r.callback_query(F.data == "menu:deposit")
async def menu_deposit(c: CallbackQuery):
    await c.message.edit_text(await deposit_text(), parse_mode="Markdown", reply_markup=back_keyboard())
    await c.answer()

@r.callback_query(F.data == "menu:profile")
async def menu_profile(c: CallbackQuery):
    async with Session() as s:
        u = (await s.execute(select(User).where(User.telegram_id == c.from_user.id))).scalar_one()
        total_orders = (await s.execute(select(func.count(Order.id)).where(Order.user_id == c.from_user.id))).scalar_one()
        completed = (await s.execute(select(func.count(Order.id)).where(Order.user_id == c.from_user.id, Order.status == "completed"))).scalar_one()
    text = (
        "👤 Profile\n\n"
        f"🆔 User ID: <code>{c.from_user.id}</code>\n"
        f"💰 Balance: ₹{u.balance:.2f}\n"
        f"📦 Total Orders: {total_orders}\n"
        f"✅ Completed: {completed}"
    )
    await c.message.edit_text(text, parse_mode="HTML", reply_markup=back_keyboard())
    await c.answer()

@r.callback_query(F.data == "menu:history")
async def menu_history(c: CallbackQuery):
    async with Session() as s:
        result = await s.execute(select(Order).where(Order.user_id == c.from_user.id).order_by(Order.created_at.desc()).limit(10))
        orders = list(result.scalars().all())
    if not orders:
        text = "📋 History\n\nNo orders yet."
    else:
        lines = ["📋 History\n"]
        for o in orders:
            status_icon = {"completed": "✅", "waiting": "⏳", "failed": "❌"}.get(o.status, "•")
            otp = f"\n🔐 OTP: <code>{o.otp}</code>" if o.otp else ""
            lines.append(f"<b>#{o.id}</b> • {o.service} • {o.country}\n📱 <code>{o.phone}</code>\n{status_icon} {o.status}{otp}\n")
        text = "\n".join(lines)
    await c.message.edit_text(text, parse_mode="HTML", reply_markup=back_keyboard())
    await c.answer()

@r.callback_query(F.data == "menu:howto")
async def menu_howto(c: CallbackQuery):
    text = (
        "📖 <b>How To Use</b>\n\n"
        "1️⃣ Add balance to your account.\n"
        "2️⃣ Tap <b>Buy Account</b> and choose a service.\n"
        "3️⃣ Select a country and purchase a number.\n"
        "4️⃣ Use the number where required and wait for the OTP.\n"
        "5️⃣ The OTP will be sent to this bot when received.\n\n"
        "🎥 Tutorial video will be added here later."
    )
    await c.message.edit_text(text, parse_mode="HTML", reply_markup=back_keyboard())
    await c.answer()

@r.callback_query(F.data.startswith("svc:"))
async def service(c: CallbackQuery):
    svc = c.data.split(":")[1]
    items = await catalog(svc)
    if not items:
        return await c.answer("No numbers available.", show_alert=True)
    rows = [[InlineKeyboardButton(text=f"{format_country(x.country, x.country_name)} • ₹{sell_price(x.cost_rupees):.0f}", callback_data=f"buy:{svc}:{x.country}")] for x in items[:80]]
    rows.append([InlineKeyboardButton(text="◀️ Back", callback_data="menu:buy")])
    await c.message.edit_text("🌍 Select country:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await c.answer()

@r.callback_query(F.data.startswith("buy:"))
async def purchase(c: CallbackQuery):
    _, svc, country = c.data.split(":", 2)
    u = await get_user(c.from_user.id)
    x = next((i for i in await catalog(svc) if i.country == country), None)
    if not x:
        return await c.answer("Unavailable", show_alert=True)
    price = sell_price(x.cost_rupees)
    if u.balance < price:
        return await c.answer(f"Need ₹{price:.0f}", show_alert=True)
    try:
        p, a = await buy_best(svc, country, f"tg-{c.from_user.id}-{c.id}")
    except Exception:
        return await c.answer("No provider could complete it.", show_alert=True)
    async with Session() as s:
        u2 = (await s.execute(select(User).where(User.telegram_id == c.from_user.id))).scalar_one()
        u2.balance -= price
        s.add(Order(user_id=u2.telegram_id, provider=p.name, provider_order_id=a.order_id, service=svc, country=country, phone=a.phone, cost=a.cost_rupees, price=price))
        await s.commit()
    await c.message.edit_text(f"✅ Number: `{a.phone}`\n💰 ₹{price:.0f}\n\n⏳ Waiting for OTP…", parse_mode="Markdown", reply_markup=back_keyboard())
    await c.answer()

@r.message(Command("admin"))
async def admin(m: Message):
    if m.from_user.id != OWNER_ID:
        return
    async with Session() as s:
        u = len((await s.execute(select(User))).scalars().all())
        p = len((await s.execute(select(Payment).where(Payment.status == "pending"))).scalars().all())
        o = len((await s.execute(select(Order))).scalars().all())
    await m.answer(f"👑 Admin\nUsers: {u}\nPending payments: {p}\nOrders: {o}\n/approve ID")

@r.message(Command("approve"))
async def approve(m: Message):
    if m.from_user.id != OWNER_ID:
        return
    parts = m.text.split()
    if len(parts) != 2:
        return await m.answer("Usage: /approve ID")
    async with Session() as s:
        p = await s.get(Payment, int(parts[1]))
        if not p or p.status != "pending":
            return await m.answer("Not found/pending")
        u = (await s.execute(select(User).where(User.telegram_id == p.user_id))).scalar_one()
        u.balance += p.amount
        p.status = "approved"
        await s.commit()
    await m.answer("✅ Payment approved.")
