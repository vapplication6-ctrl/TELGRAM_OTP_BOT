from typing import Any, Dict, Optional

import httpx

from .base import Provider, CatalogItem, Activation

BASE = "https://api.numberotp.com/v1"


def _data(payload: Any) -> Any:
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    return payload


def _unwrap_activation(payload: Any) -> Dict[str, Any]:
    data = _data(payload)
    if isinstance(data, dict):
        # Some API responses may wrap the activation object one level deeper.
        for key in ("activation", "result", "item"):
            if isinstance(data.get(key), dict):
                return data[key]
        return data
    return {}


class NumberOTPProvider(Provider):
    name = "numberotp"

    def __init__(self, key: str):
        self.key = key.strip()

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.key}",
            "Accept": "application/json",
        }

    async def catalog(self, service: str):
        # /public/* endpoints are intentionally unauthenticated.
        async with httpx.AsyncClient(timeout=15) as client:
            countries_r = await client.get(
                f"{BASE}/public/countries",
                params={"service": service},
            )
            countries_r.raise_for_status()
            prices_r = await client.get(
                f"{BASE}/public/prices",
                params={"service": service},
            )
            prices_r.raise_for_status()

        countries = _data(countries_r.json()) or {}
        prices = _data(prices_r.json()) or {}
        if not isinstance(countries, dict) or not isinstance(prices, dict):
            return []

        out = []
        for code, item in countries.items():
            if not isinstance(item, dict):
                continue
            country = str(item.get("code") or code)
            p = prices.get(country) or prices.get(str(code)) or {}
            if not isinstance(p, dict):
                continue
            service_price = p.get(service) or {}
            if not isinstance(service_price, dict):
                continue
            cost = service_price.get("cost")
            count = service_price.get("count", 0)
            if cost is None:
                continue
            out.append(
                CatalogItem(
                    self.name,
                    service,
                    country,
                    str(item.get("name") or country),
                    float(cost),
                    int(count or 0),
                )
            )
        return out

    async def buy(self, service: str, country: str, client_ref: str):
        # Current NumberOTP activation request is {service, country}.
        # client_ref is retained internally for reconciliation.
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{BASE}/activations",
                headers={**self._headers(), "Content-Type": "application/json"},
                json={"service": service, "country": str(country)},
            )
            response.raise_for_status()
            data = _unwrap_activation(response.json())

        order_id = (
            data.get("id")
            or data.get("activation_id")
            or data.get("activationId")
        )
        phone = data.get("phone_number") or data.get("phone") or data.get("number")
        cost = data.get("cost", 0)

        if not order_id or not phone:
            raise RuntimeError("NumberOTP returned an incomplete activation response")

        return Activation(
            self.name,
            str(order_id),
            str(phone),
            float(cost or 0),
        )

    async def get(self, order_id: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                f"{BASE}/activations/{order_id}",
                headers=self._headers(),
            )
            response.raise_for_status()
            return _unwrap_activation(response.json())

    async def wait(self, order_id: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(
                f"{BASE}/activations/{order_id}/wait",
                headers=self._headers(),
            )
            response.raise_for_status()
            return _unwrap_activation(response.json())

    async def cancel(self, order_id: str) -> bool:
        # The current public NumberOTP API reference documents activation
        # creation/status/wait, but does not document an activation-cancel
        # endpoint. Do not call an undocumented route.
        return False
