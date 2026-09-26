OTP Reseller Bot V1.2 — Telegram-only + API polling
White-label Telegram bot for legitimate, user-authorized SMS verification-number resale.
Architecture
This build is Telegram-only. It does not include a website, Telegram Mini App, FastAPI server, public web endpoint, webhook URL, or webhook secret.
Telegram user
     ↓
Telegram bot
     ↓
Provider API
     ↓
NumberOTP / VRNUM
     ↓
API status polling
     ↓
OTP delivered back to Telegram
The bot polls active orders from the provider APIs every 10 seconds. NumberOTP documents both normal status polling and a long-poll endpoint; this build deliberately uses ordinary status polling so no public callback endpoint is needed. VRNUM documents GET /otp-numbers/:id for live OTP checks. citeturn1search0turn0search1
Recent fixes (build improvements)
Admin gets instant notification + Approve/Reject buttons when user submits payment
Duplicate UTR blocked
Atomic-style balance check after provider buy (reduces double-spend risk)
User can cancel waiting order → instant refund
Auto-expiry of waiting orders after ORDER_TIMEOUT_MINUTES (default 20) → auto refund
Better error messages for users
Admin panel shows pending payment list + buttons
/reject command + ADMIN_IDS properly used
Includes
Telegram + WhatsApp service buttons
NumberOTP + VRNUM provider adapters
Automatic provider fallback during purchase
Wallet and SQLite database
Configurable pricing/markup
Admin payment approval
UPI payment submission
Automatic API polling for OTP delivery
Provider identity hidden from customers
No website / Mini App / public webhook endpoint
Environment variables
Required:
BOT_TOKEN=
OWNER_ID=
UPI_ID=
NUMBEROTP_API_KEY=
VRNUM_API_KEY=
Optional:
DATABASE_URL=sqlite+aiosqlite:///./data/otpbot.db
ADMIN_IDS=
DEFAULT_MARKUP_RUPEES=15
RARE_MARKUP_RUPEES=30
RARE_COST_MAX_RUPEES=6
Do not add NUMBEROTP_WEBHOOK_SECRET, VRNUM_WEBHOOK_SECRET, WEBHOOK_HOST, WEBHOOK_PORT, or a public webhook URL. They are not used by this build.
Provider API details
NumberOTP
Base: https://api.numberotp.com/v1
Public catalog: /public/services, /public/countries, /public/prices
Provision: POST /activations
Poll: GET /activations/{id}
Optional provider long-poll exists at /activations/{id}/wait, but this build uses ordinary polling.
Auth: Authorization: Bearer notp_...
NumberOTP's current API documentation confirms that authenticated activation status can be polled without a documented rate limit at present. citeturn1search0
VRNUM
Base: https://vrnum.com/api/v1
Catalog: GET /otp-catalog
Provision: POST /otp-numbers
Poll: GET /otp-numbers/:id
Resend: POST /otp-numbers/:id/resend
Cancel: POST /otp-numbers/:id/cancel
Auth: Authorization: Bearer vrnum_live_...
Idempotency-Key is used for provisioning.
VRNUM's current OTP API documentation explicitly supports polling the order endpoint for the code instead of using webhooks. citeturn0search1
Compliance
Use provider capacity only for legitimate, authorized verification/testing workflows and follow each provider's current terms and acceptable-use rules. Do not use disposable numbers for fraud, phishing, spam, bulk fake-account creation, or bypassing platform verification/anti-abuse controls.
