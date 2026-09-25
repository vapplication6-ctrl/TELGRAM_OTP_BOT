import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
UPI_ID = os.getenv("UPI_ID", "")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/otpbot.db")
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()}
if OWNER_ID:
    ADMIN_IDS.add(OWNER_ID)

NUMBEROTP_API_KEY = os.getenv("NUMBEROTP_API_KEY", "")
VRNUM_API_KEY = os.getenv("VRNUM_API_KEY", "")

DEFAULT_MARKUP_RUPEES = float(os.getenv("DEFAULT_MARKUP_RUPEES", "15"))
RARE_MARKUP_RUPEES = float(os.getenv("RARE_MARKUP_RUPEES", "30"))
RARE_COST_MAX_RUPEES = float(os.getenv("RARE_COST_MAX_RUPEES", "6"))
