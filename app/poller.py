import asyncio
import logging
import re
from typing import Any, Dict

from aiogram import Bot
from sqlalchemy import select

from .db import Order, Session, User
from .router import get_provider

LOG = logging.getLogger("otp.poller")
POLL_INTERVAL_SECONDS = 5


def _nested(payload: Any) -> Dict[str, Any]:
    """Find the useful activation object even when the provider nests it."""
    if not isinstance(payload, dict):
        return {}

    # Prefer the common wrapper keys, but also walk nested dictionaries so
    # provider response changes do not silently break OTP delivery.
    preferred = ("data", "result", "order", "activation", "number", "item")
    for key in preferred:
        value = payload.get(key)
        if isinstance(value, dict):
            nested = _nested(value)
            if nested:
                return nested

    return payload


def _extract_otp_from_text(text: str) -> str:
    """Extract a likely OTP from an SMS when the API omits a dedicated code field."""
    if not text:
        return ""
    # Prefer phrases such as code/otp/verification followed by 4-8 digits.
    patterns = (
        r"(?:otp|one[- ]time password|verification(?: code)?|security code|login code)[^0-9]{0,20}(\d{4,8})",
        r"(?:code|passcode)[^0-9]{0,20}(\d{4,8})",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return ""


def parse_status(payload: Dict[str, Any]) -> tuple[str, str, str]:
    obj = _nested(payload)
    otp = str(
        obj.get("otp")
        or obj.get("code")
        or obj.get("verificationCode")
        or obj.get("verification_code")
        or obj.get("otpCode")
        or obj.get("otp_code")
        or ""
    ).strip()
    status = str(
        obj.get("status")
        or obj.get("state")
        or obj.get("event")
        or obj.get("type")
        or ""
    ).strip().lower()
    sms = str(
        obj.get("full_sms")
        or obj.get("fullSms")
        or obj.get("sms")
        or obj.get("message")
        or obj.get("text")
        or ""
    ).strip()

    if not otp:
        otp = _extract_otp_from_text(sms)
    if otp:
        return "completed", otp, sms

    if status in {
        "received", "sms_received", "sms.received", "otp.received",
        "otp_received", "otp.completed", "completed", "success",
        "successful", "done",
    }:
        return "completed", "", sms
    if status in {
        "failed", "error", "expired", "cancelled", "canceled",
        "number.provisioning_failed", "provisioning_failed",
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

    if status == "failed":
        # Only refund after the provider has explicitly reported failure/expiry.
        # This prevents guessing an expiry time and protects the user's balance
        # from being refunded while an activation may still be usable.
        async with Session() as session:
            order = await session.get(Order, order_id)
            if not order or order.status != "waiting":
                return

            # Best-effort cancellation when the provider supports it. The
            # provider's failed/expired status remains the source of truth.
            try:
                await provider.cancel(provider_order_id)
            except Exception as exc:
                LOG.info("Cancel attempt for failed order %s was not available: %s", order_id, exc)

            user = await session.get(User, order.user_id)
            if user:
                user.balance += order.price
            order.status = "refunded"
            await session.commit()
            refund_amount = order.price

        try:
            await bot.send_message(
                chat_id,
                f"💸 <b>Order expired/failed</b>\n\n"
                f"Your ₹{refund_amount:.2f} has been automatically refunded to your bot balance.",
                parse_mode="HTML",
            )
        except Exception as exc:
            LOG.warning("Could not send refund notice for order %s: %s", order_id, exc)
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
