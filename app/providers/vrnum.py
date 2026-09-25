from typing import Any, Dict

import httpx

from .base import Provider, CatalogItem, Activation

BASE = "https://vrnum.com/api/v1"


def _data(payload: Any) -> Any:
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    return payload


def _items(payload: Any):
    data = _data(payload)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("items", "catalog", "services", "countries", "results"):
            if isinstance(data.get(key), list):
                return data[key]
    return []


def _obj(payload: Any) -> Dict[str, Any]:
    data = _data(payload)
    if isinstance(data, dict):
        for key in ("order", "activation", "number", "result", "item"):
            if isinstance(data.get(key), dict):
                return data[key]
        return data
    return {}


class VRNUMProvider(Provider):
    name = "vrnum"

    def __init__(self, key: str):
        self.key = key.strip()

    def _headers(self, idempotency_key: str | None = None) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    @staticmethod
    def _service_candidates(service: str):
        aliases = {
            "wa": {"wa", "whatsapp"},
            "tg": {"tg", "telegram"},
        }
        return aliases.get(service.lower(), {service.lower()})

    @staticmethod
    def _provider_service(service: str) -> str:
        return {"wa": "whatsapp", "tg": "telegram"}.get(service.lower(), service)

    async def catalog(self, service: str):
        wanted = self._service_candidates(service)
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                f"{BASE}/otp-catalog",
                headers={"Authorization": f"Bearer {self.key}", "Accept": "application/json"},
            )
            response.raise_for_status()
            rows = _items(response.json())

        out = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            service_value = str(
                item.get("service")
                or item.get("serviceCode")
                or item.get("service_code")
                or ""
            )
            if service_value.lower() not in wanted:
                continue
            country = str(
                item.get("countryCode")
                or item.get("country_code")
                or item.get("country")
                or ""
            )
            country_name = str(
                item.get("countryName")
                or item.get("country_name")
                or item.get("name")
                or country
            )
            cost = item.get("price")
            if cost is None:
                cost = item.get("cost")
            available = item.get("available")
            if available is None:
                available = item.get("count", 0)
            if not country or cost is None:
                continue
            out.append(
                CatalogItem(
                    self.name,
                    service,
                    country,
                    country_name,
                    float(cost),
                    int(available or 0),
                )
            )
        return out

    async def buy(self, service: str, country: str, client_ref: str):
        # VRNUM explicitly supports Idempotency-Key + clientReference.
        payload = {
            "service": self._provider_service(service),
            "countryCode": str(country),
            "clientReference": client_ref,
        }
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{BASE}/otp-numbers",
                headers=self._headers(client_ref),
                json=payload,
            )
            response.raise_for_status()
            data = _obj(response.json())

        order_id = str(data.get("id") or data.get("orderId") or data.get("order_id") or "")
        phone = data.get("phone") or data.get("phoneNumber") or data.get("phone_number") or ""
        cost = data.get("price")
        if cost is None:
            cost = data.get("cost", 0)

        if not order_id or not phone:
            raise RuntimeError("VRNUM returned an incomplete OTP order response")

        return Activation(
            self.name,
            order_id,
            str(phone),
            float(cost or 0),
        )

    async def get(self, order_id: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                f"{BASE}/otp-numbers/{order_id}",
                headers={"Authorization": f"Bearer {self.key}", "Accept": "application/json"},
            )
            response.raise_for_status()
            return _obj(response.json())

    async def resend(self, order_id: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                f"{BASE}/otp-numbers/{order_id}/resend",
                headers=self._headers(),
            )
            response.raise_for_status()
            return _obj(response.json())

    async def cancel(self, order_id: str) -> bool:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                f"{BASE}/otp-numbers/{order_id}/cancel",
                headers=self._headers(),
            )
            return response.is_success
