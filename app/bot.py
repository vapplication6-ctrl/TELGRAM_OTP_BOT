from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from sqlalchemy import select, func
from .db import Session, User, Payment, Order
from .router import catalog, buy_best, get_provider
from .pricing import sell_price
from .config import OWNER_ID, UPI_ID, ADMIN_IDS
from .country_display import format_country

r = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


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
    return (
        f"💳 Add Balance\n\n"
        f"UPI ID: `{UPI_ID or 'SET_UPI_ID_IN_ENV'}`\n\n"
        f"After paying, send:\n"
        f"`/paid AMOUNT UTR`\n\n"
        f"Example: `/paid 100 123456789012`"
    )


@r.message(Command("deposit"))
async def deposit(m: Message):
    await m.answer(await deposit_text(), parse_mode="Markdown", reply_markup=back_keyboard())


@r.message(Command("paid"))
async def paid(m: Message):
    parts = m.text.split()
    if len(parts) != 3:
        return await m.answer("❌ Wrong format.\n\nUse: `/paid AMOUNT UTR`\nExample: `/paid 100 123456789012`", parse_mode="Markdown")
    try:
        amount = float(parts[1])
    except Exception:
        return await m.answer("❌ Invalid amount. Example: `/paid 100 123456789012`", parse_mode="Markdown")
    if amount <= 0:
        return await m.answer("❌ Amount must be greater than 0.")
    if amount > 50000:
        return await m.answer("❌ Amount too large. Contact admin.")

    utr = parts[2].strip()
    if len(utr) < 6:
        return await m.answer("❌ UTR looks too short. Please check and try again.")

    async with Session() as s:
        # Duplicate UTR check
        existing = await s.execute(
            select(Payment).where(Payment.utr == utr, Payment.status.in_(["pending", "approved"]))
        )
        if existing.scalar_one_or_none():
            return await m.answer("❌ This UTR is already used. Please use a new payment.")

        payment = Payment(user_id=m.from_user.id, amount=amount, utr=utr)
        s.add(payment)
        await s.commit()
        await s.refresh(payment)
        payment_id = payment.id

    await m.answer(
        f"✅ Payment submitted!\n\n"
        f"Amount: ₹{amount:.0f}\n"
        f"UTR: `{utr}`\n"
        f"Status: Waiting for admin approval.\n\n"
        f"You will get balance after admin verifies.",
        parse_mode="Markdown",
    )

    # Notify all admins
    admin_text = (
        f"💰 <b>New Payment Request</b>\n\n"
        f"User: <code>{m.from_user.id}</code>\n"
        f"Name: {m.from_user.full_name or '-'}\n"
        f"Amount: ₹{amount:.0f}\n"
        f"UTR: <code>{utr}</code>\n"
        f"Payment ID: <code>{payment_id}</code>"
    )
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Approve", callback_data=f"pay:approve:{payment_id}"),
            InlineKeyboardButton(text="❌ Reject", callback_data=f"pay:reject:{payment_id}"),
        ]
    ])
    for admin_id in ADMIN_IDS:
        try:
            await m.bot.send_message(admin_id, admin_text, parse_mode="HTML", reply_markup=admin_kb)
        except Exception:
            pass


@r.message(Command("buy"))
async def buy(m: Message):
    await m.answer(
        "Select service:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="Telegram", callback_data="svc:tg"),
                InlineKeyboardButton(text="WhatsApp", callback_data="svc:wa"),
            ],
            [InlineKeyboardButton(text="◀️ Back", callback_data="menu:home")],
        ]),
    )


@r.callback_query(F.data == "menu:home")
async def menu_home(c: CallbackQuery):
    await show_home(c.message, c.from_user.id)
    await c.answer()


@r.callback_query(F.data == "menu:buy")
async def menu_buy(c: CallbackQuery):
    await c.message.edit_text(
        "Select service:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="Telegram", callback_data="svc:tg"),
                InlineKeyboardButton(text="WhatsApp", callback_data="svc:wa"),
            ],
            [InlineKeyboardButton(text="◀️ Back", callback_data="menu:home")],
        ]),
    )
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
        completed = (await s.execute(
            select(func.count(Order.id)).where(Order.user_id == c.from_user.id, Order.status == "completed")
        )).scalar_one()
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
        result = await s.execute(
            select(Order).where(Order.user_id == c.from_user.id).order_by(Order.created_at.desc()).limit(10)
        )
        orders = list(result.scalars().all())
    if not orders:
        text = "📋 History\n\nNo orders yet."
    else:
        lines = ["📋 History\n"]
        for o in orders:
            status_icon = {"completed": "✅", "waiting": "⏳", "failed": "❌", "refunded": "💸", "cancelled": "🚫"}.get(o.status, "•")
            otp = f"\n🔐 OTP: <code>{o.otp}</code>" if o.otp else ""
            display_status = o.status
            lines.append(
                f"<b>#{o.id}</b> • {o.service} • {o.country}\n"
                f"📱 <code>{o.phone}</code>\n"
                f"{status_icon} {display_status}{otp}\n"
            )
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
        "⏱ If OTP does not arrive in time, the order auto-expires and money is refunded.\n"
        "You can also cancel a waiting order yourself."
    )
    await c.message.edit_text(text, parse_mode="HTML", reply_markup=back_keyboard())
    await c.answer()


@r.callback_query(F.data.startswith("svc:"))
async def service(c: CallbackQuery):
    svc = c.data.split(":")[1]
    try:
        items = await catalog(svc)
    except Exception:
        return await c.answer("Could not load countries. Please try again.", show_alert=True)
    if not items:
        return await c.answer("No numbers available right now. Try later.", show_alert=True)
    rows = [
        [InlineKeyboardButton(
            text=f"{format_country(x.country, x.country_name)} • ₹{sell_price(x.cost_rupees):.0f}",
            callback_data=f"country:{svc}:{x.country}",
        )]
        for x in items[:80]
    ]
    rows.append([InlineKeyboardButton(text="◀️ Back", callback_data="menu:buy")])
    await c.message.edit_text("🌍 Select country:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await c.answer()


@r.callback_query(F.data.startswith("country:"))
async def country_detail(c: CallbackQuery):
    _, svc, country = c.data.split(":", 2)
    try:
        items = await catalog(svc)
    except Exception:
        return await c.answer("Could not load details. Try again.", show_alert=True)
    x = next((i for i in items if i.country == country), None)
    if not x:
        return await c.answer("Country unavailable right now.", show_alert=True)

    price = sell_price(x.cost_rupees)
    formatted = format_country(x.country, x.country_name)
    if " • " in formatted:
        country_name, meta = formatted.split(" • ", 1)
        flag = meta[0] if meta else "🌍"
        country_display = f"{country_name} {flag}"
    else:
        country_display = formatted

    text = (
        "<b>Click Buy to purchase a number:</b>\n"
        "––––––––––––––––––•\n"
        f"• Country: {country_display}\n"
        f"• Price: ₹{price:.0f}\n"
        f"• Stock: {x.available} qty"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="◀️ Back", callback_data=f"svc:{svc}"),
            InlineKeyboardButton(text="🛒 Buy", callback_data=f"buy:{svc}:{country}"),
        ]
    ])
    await c.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await c.answer()


@r.callback_query(F.data.startswith("buy:"))
async def purchase(c: CallbackQuery):
    _, svc, country = c.data.split(":", 2)
    u = await get_user(c.from_user.id)

    try:
        items = await catalog(svc)
    except Exception:
        return await c.answer("Could not check stock. Try again.", show_alert=True)

    x = next((i for i in items if i.country == country), None)
    if not x or x.available <= 0:
        return await c.answer("This country is out of stock right now.", show_alert=True)

    price = sell_price(x.cost_rupees)
    if u.balance < price:
        return await c.answer(f"Insufficient balance. Need ₹{price:.0f}", show_alert=True)

    # Buy from provider first
    try:
        provider, activation = await buy_best(svc, country, f"tg-{c.from_user.id}-{c.id}")
    except Exception as e:
        msg = str(e).lower()
        if "no provider" in msg or "could complete" in msg:
            return await c.answer("No number available from any provider. Try another country.", show_alert=True)
        return await c.answer("Purchase failed. Please try again in a moment.", show_alert=True)

    # Atomic-ish: re-check balance and deduct inside transaction
    order_id = None
    async with Session() as s:
        u2 = (await s.execute(select(User).where(User.telegram_id == c.from_user.id))).scalar_one_or_none()
        if not u2 or u2.balance < price:
            # Balance changed (race) — try cancel the number we just bought
            try:
                await provider.cancel(activation.order_id)
            except Exception:
                pass
            return await c.answer("Balance changed. Please try again.", show_alert=True)

        u2.balance -= price
        order = Order(
            user_id=u2.telegram_id,
            provider=provider.name,
            provider_order_id=activation.order_id,
            service=svc,
            country=country,
            phone=activation.phone,
            cost=activation.cost_rupees,
            price=price,
            status="waiting",
        )
        s.add(order)
        await s.commit()
        await s.refresh(order)
        order_id = order.id

    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚫 Cancel Order (Refund)", callback_data=f"cancel:{order_id}")],
        [InlineKeyboardButton(text="◀️ Home", callback_data="menu:home")],
    ])
    await c.message.edit_text(
        f"✅ Number ready\n\n"
        f"📱 Number: `{activation.phone}`\n"
        f"💰 Charged: ₹{price:.0f}\n"
        f"🆔 Order: #{order_id}\n\n"
        f"⏳ Waiting for OTP…\n"
        f"You can cancel anytime before OTP arrives.",
        parse_mode="Markdown",
        reply_markup=cancel_kb,
    )
    await c.answer()


@r.callback_query(F.data.startswith("cancel:"))
async def cancel_order(c: CallbackQuery):
    try:
        order_id = int(c.data.split(":")[1])
    except Exception:
        return await c.answer("Invalid order.", show_alert=True)

    async with Session() as s:
        order = await s.get(Order, order_id)
        if not order:
            return await c.answer("Order not found.", show_alert=True)
        if order.user_id != c.from_user.id:
            return await c.answer("This is not your order.", show_alert=True)
        if order.status != "waiting":
            return await c.answer(f"Order already {order.status}. Cannot cancel.", show_alert=True)

        # Try provider cancel
        provider = get_provider(order.provider)
        if provider:
            try:
                await provider.cancel(order.provider_order_id)
            except Exception:
                pass

        # Refund
        user = (await s.execute(select(User).where(User.telegram_id == order.user_id))).scalar_one_or_none()
        refund_amount = order.price
        if user:
            user.balance += refund_amount
        order.status = "cancelled"
        await s.commit()

    await c.message.edit_text(
        f"🚫 Order #{order_id} cancelled.\n\n"
        f"💸 ₹{refund_amount:.2f} refunded to your balance.",
        reply_markup=back_keyboard(),
    )
    await c.answer("Cancelled & refunded.")


# ---------- Admin ----------

@r.message(Command("admin"))
async def admin(m: Message):
    if not is_admin(m.from_user.id):
        return
    async with Session() as s:
        users = len((await s.execute(select(User))).scalars().all())
        pending = list(
            (await s.execute(select(Payment).where(Payment.status == "pending").order_by(Payment.id.desc()).limit(20))).scalars().all()
        )
        total_orders = len((await s.execute(select(Order))).scalars().all())
        waiting = len((await s.execute(select(Order).where(Order.status == "waiting"))).scalars().all())

    text = (
        f"👑 <b>Admin Panel</b>\n\n"
        f"Users: {users}\n"
        f"Total orders: {total_orders}\n"
        f"Waiting OTP: {waiting}\n"
        f"Pending payments: {len(pending)}\n\n"
    )
    if pending:
        text += "<b>Recent pending:</b>\n"
        for p in pending[:10]:
            text += f"• ID {p.id} | User <code>{p.user_id}</code> | ₹{p.amount:.0f} | UTR <code>{p.utr}</code>\n"
        text += "\nUse buttons below or /approve ID /reject ID"
    else:
        text += "No pending payments."

    kb_rows = []
    for p in pending[:5]:
        kb_rows.append([
            InlineKeyboardButton(text=f"✅ #{p.id} ₹{p.amount:.0f}", callback_data=f"pay:approve:{p.id}"),
            InlineKeyboardButton(text=f"❌ #{p.id}", callback_data=f"pay:reject:{p.id}"),
        ])
    kb_rows.append([InlineKeyboardButton(text="🔄 Refresh", callback_data="admin:refresh")])
    await m.answer(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))


@r.callback_query(F.data == "admin:refresh")
async def admin_refresh(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Not allowed.", show_alert=True)
    # Re-use admin logic by editing
    async with Session() as s:
        users = len((await s.execute(select(User))).scalars().all())
        pending = list(
            (await s.execute(select(Payment).where(Payment.status == "pending").order_by(Payment.id.desc()).limit(20))).scalars().all()
        )
        total_orders = len((await s.execute(select(Order))).scalars().all())
        waiting = len((await s.execute(select(Order).where(Order.status == "waiting"))).scalars().all())

    text = (
        f"👑 <b>Admin Panel</b>\n\n"
        f"Users: {users}\n"
        f"Total orders: {total_orders}\n"
        f"Waiting OTP: {waiting}\n"
        f"Pending payments: {len(pending)}\n\n"
    )
    if pending:
        text += "<b>Recent pending:</b>\n"
        for p in pending[:10]:
            text += f"• ID {p.id} | User <code>{p.user_id}</code> | ₹{p.amount:.0f} | UTR <code>{p.utr}</code>\n"
    else:
        text += "No pending payments."

    kb_rows = []
    for p in pending[:5]:
        kb_rows.append([
            InlineKeyboardButton(text=f"✅ #{p.id} ₹{p.amount:.0f}", callback_data=f"pay:approve:{p.id}"),
            InlineKeyboardButton(text=f"❌ #{p.id}", callback_data=f"pay:reject:{p.id}"),
        ])
    kb_rows.append([InlineKeyboardButton(text="🔄 Refresh", callback_data="admin:refresh")])
    await c.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
    await c.answer()


@r.callback_query(F.data.startswith("pay:"))
async def payment_action(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Not allowed.", show_alert=True)
    parts = c.data.split(":")
    if len(parts) != 3:
        return await c.answer("Invalid.", show_alert=True)
    action, payment_id_str = parts[1], parts[2]
    try:
        payment_id = int(payment_id_str)
    except Exception:
        return await c.answer("Invalid ID.", show_alert=True)

    async with Session() as s:
        payment = await s.get(Payment, payment_id)
        if not payment or payment.status != "pending":
            return await c.answer("Already processed or not found.", show_alert=True)

        user = (await s.execute(select(User).where(User.telegram_id == payment.user_id))).scalar_one_or_none()
        if action == "approve":
            if user:
                user.balance += payment.amount
            payment.status = "approved"
            await s.commit()
            status_text = f"✅ Payment #{payment_id} approved. ₹{payment.amount:.0f} added."
            user_msg = f"✅ Your payment of ₹{payment.amount:.0f} (UTR: {payment.utr}) has been approved.\nBalance updated."
        elif action == "reject":
            payment.status = "rejected"
            await s.commit()
            status_text = f"❌ Payment #{payment_id} rejected."
            user_msg = f"❌ Your payment of ₹{payment.amount:.0f} (UTR: {payment.utr}) was rejected.\nContact admin if needed."
        else:
            return await c.answer("Unknown action.", show_alert=True)

    await c.answer(status_text)
    try:
        await c.message.edit_text(c.message.text + f"\n\n{status_text}", parse_mode="HTML")
    except Exception:
        pass

    # Notify user
    try:
        await c.bot.send_message(payment.user_id, user_msg)
    except Exception:
        pass


@r.message(Command("approve"))
async def approve_cmd(m: Message):
    if not is_admin(m.from_user.id):
        return
    parts = m.text.split()
    if len(parts) != 2:
        return await m.answer("Usage: /approve PAYMENT_ID")
    try:
        payment_id = int(parts[1])
    except Exception:
        return await m.answer("Invalid ID")
    async with Session() as s:
        payment = await s.get(Payment, payment_id)
        if not payment or payment.status != "pending":
            return await m.answer("Not found or already processed.")
        user = (await s.execute(select(User).where(User.telegram_id == payment.user_id))).scalar_one_or_none()
        if user:
            user.balance += payment.amount
        payment.status = "approved"
        await s.commit()
    await m.answer(f"✅ Payment #{payment_id} approved. ₹{payment.amount:.0f} added.")
    try:
        await m.bot.send_message(
            payment.user_id,
            f"✅ Your payment of ₹{payment.amount:.0f} (UTR: {payment.utr}) has been approved.\nBalance updated.",
        )
    except Exception:
        pass


@r.message(Command("reject"))
async def reject_cmd(m: Message):
    if not is_admin(m.from_user.id):
        return
    parts = m.text.split()
    if len(parts) != 2:
        return await m.answer("Usage: /reject PAYMENT_ID")
    try:
        payment_id = int(parts[1])
    except Exception:
        return await m.answer("Invalid ID")
    async with Session() as s:
        payment = await s.get(Payment, payment_id)
        if not payment or payment.status != "pending":
            return await m.answer("Not found or already processed.")
        payment.status = "rejected"
        await s.commit()
    await m.answer(f"❌ Payment #{payment_id} rejected.")
    try:
        await m.bot.send_message(
            payment.user_id,
            f"❌ Your payment of ₹{payment.amount:.0f} (UTR: {payment.utr}) was rejected.\nContact admin if needed.",
        )
    except Exception:
        pass
