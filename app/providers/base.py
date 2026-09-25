from dataclasses import dataclass
from abc import ABC, abstractmethod
from typing import Any, Dict


@dataclass
class CatalogItem:
    provider: str
    service: str
    country: str
    country_name: str
    cost_rupees: float
    available: int = 0


@dataclass
class Activation:
    provider: str
    order_id: str
    phone: str
    cost_rupees: float


class Provider(ABC):
    @abstractmethod
    async def catalog(self, service: str):
        ...

    @abstractmethod
    async def buy(self, service: str, country: str, client_ref: str):
        ...

    @abstractmethod
    async def cancel(self, order_id: str) -> bool:
        ...

    async def get(self, order_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    async def wait(self, order_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    async def resend(self, order_id: str) -> Dict[str, Any]:
        raise NotImplementedError
