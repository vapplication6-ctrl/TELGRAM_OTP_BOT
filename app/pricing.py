import asyncio
import logging
from typing import Any, Dict

from aiogram import Bot
from sqlalchemy import select

from .db import Order, Session
from .router import get_provider

LOG = logging.getLogger("otp.poller")
POLL_INTERVAL_SECONDS = 10


def _nested(payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    for key in ("data", "result", "order", "activation", "number", "item"):
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    return payload


def parse_status(payload: Dict[str, Any]) -> tuple[str, str, str]:
    obj = _nested(payload)
    otp = str(
        obj.get("otp")
        or obj.get("code")
        or obj.get("verificationCode")
        or obj.get("verification_code")
        or ""
    ).strip()
    status = str(
        obj.get("status")
        or obj.get("state")
        or obj.get("event")
        or obj.get("type")
        or ""
    ).strip().lower()
    sms = str(obj.get("full_sms") or obj.get("sms") or obj.get("message") or "").strip()

    if otp:
        return "completed", otp, sms

    if status in {
        "received", "otp.received", "otp.completed", "completed", "success", "successful",
    }:
        return "completed", "", sms
    if status in {
        "failed", "error", "expired", "cancelled", "canceled", "number.provisioning_failed",
    }:
        return "failed", "", sms
    return "waiting", "", sms


async def _poll_one(bot: Bot, order_id: int, provider_name: str, provider_order_id: str, phone: str, chat_id: int):
    provider = get_provider(provider_name)
    if not provider:
        return

    try:
        payload = await provider.get(provider_order_id)
        status, otp, sms = parse_status(payload)
    except Exception as exc:
        LOG.warning("Polling failed for order %s via %s: %s", order_id, provider_name, exc)
        return

    if status == "waiting":
        return

    async with Session() as session:
        order = await session.get(Order, order_id)
        if not order or order.status != "waiting":
            return
        if otp:
            order.otp = otp
        order.status = status
        await session.commit()

    if status == "completed":
        text = f"📩 <b>OTP received</b>\n\n📱 Number: <code>{phone}</code>\n🔐 Code: <code>{otp or 'received'}</code>"
        if sms and not otp:
            text += f"\n\n📝 <code>{sms}</code>"
        try:
            await bot.send_message(chat_id, text, parse_mode="HTML")
        except Exception as exc:
            LOG.warning("Could not send OTP for order %s: %s", order_id, exc)
    elif status == "failed":
        try:
            await bot.send_message(
                chat_id,
                "⚠️ <b>OTP order failed or expired.</b>\nPlease contact the bot owner for a refund/replacement if applicable.",
                parse_mode="HTML",
            )
        except Exception as exc:
            LOG.warning("Could not send failure notice for order %s: %s", order_id, exc)


async def poll_orders(bot: Bot):
    LOG.info("OTP API polling started; interval=%ss", POLL_INTERVAL_SECONDS)
    while True:
        try:
            async with Session() as session:
                result = await session.execute(
                    select(Order).where(Order.status == "waiting").limit(100)
                )
                orders = list(result.scalars().all())

            if orders:
                tasks = [
                    _poll_one(
                        bot,
                        order.id,
                        order.provider,
                        order.provider_order_id,
                        order.phone,
                        order.user_id,
                    )
                    for order in orders
                ]
                await asyncio.gather(*tasks, return_exceptions=True)
        except Exception:
            LOG.exception("OTP polling loop error")

        await asyncio.sleep(POLL_INTERVAL_SECONDS)

def sell_price(cost_rupees: float) -> float:
    markup = RARE_MARKUP_RUPEES if cost_rupees <= RARE_COST_MAX_RUPEES else DEFAULT_MARKUP_RUPEES
    return round(cost_rupees + markup, 2)
