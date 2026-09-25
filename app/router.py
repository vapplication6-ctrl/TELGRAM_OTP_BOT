from .config import NUMBEROTP_API_KEY, VRNUM_API_KEY
from .providers.numberotp import NumberOTPProvider
from .providers.vrnum import VRNUMProvider

providers = []
if NUMBEROTP_API_KEY:
    providers.append(NumberOTPProvider(NUMBEROTP_API_KEY))
if VRNUM_API_KEY:
    providers.append(VRNUMProvider(VRNUM_API_KEY))


def get_provider(name: str):
    return next((p for p in providers if p.name == name), None)


async def catalog(service):
    merged = []
    for p in providers:
        try:
            merged += await p.catalog(service)
        except Exception:
            pass
    best = {}
    for x in merged:
        if x.available > 0 and (x.country not in best or x.cost_rupees < best[x.country].cost_rupees):
            best[x.country] = x
    return sorted(best.values(), key=lambda x: x.country_name.lower())


async def buy_best(service, country, client_ref):
    candidates = []
    for p in providers:
        try:
            candidates += [(p, x) for x in await p.catalog(service) if x.country == country and x.available > 0]
        except Exception:
            pass
    candidates.sort(key=lambda z: z[1].cost_rupees)
    for p, _ in candidates:
        try:
            return p, await p.buy(service, country, client_ref)
        except Exception:
            pass
    raise RuntimeError("No provider could complete the activation")
