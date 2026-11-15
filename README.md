# TextLink — Connect, Text & Send Gifts

A production-ready messaging platform where people create accounts, send connection requests, chat in real time, and buy digital gifts with real money via Stripe.

## Features

- Profiles (photo, bio, interests)
- Connection requests (send / accept / decline)
- Real-time chat (Socket.IO) + image sharing
- **Buy & send gifts** with Stripe Checkout (real card payments)
- Custom cards, likes, follows, block/report
- Notifications, analytics, admin dashboard
- Email notifications (optional SMTP)

## Quick start (local)

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

Open http://localhost:5000

Without Stripe keys, gift checkout runs in **demo mode** (no charge; gift is delivered instantly) so you can test the flow.

## Stripe (real money gifts)

1. Create a [Stripe](https://dashboard.stripe.com) account.
2. Copy **Secret key** and **Publishable key** into `.env` / your host env:
   - `STRIPE_SECRET_KEY=sk_test_…`
   - `STRIPE_PUBLISHABLE_KEY=pk_test_…`
3. Set `APP_URL` to your public URL (required for Checkout redirects), e.g. `https://your-app.up.railway.app`
4. Add a webhook endpoint: `https://your-domain/api/stripe/webhook`  
   Event: `checkout.session.completed`  
   Set `STRIPE_WEBHOOK_SECRET=whsec_…`
5. Use test cards (`4242 4242 4242 4242`) until you switch to live keys (`sk_live_…` / `pk_live_…`).

### Gift purchase flow

1. User opens **Buy Gifts**, picks a gift, enters recipient + optional note.
2. App creates a Stripe Checkout Session (`POST /api/gifts/checkout`).
3. User pays on Stripe’s hosted page.
4. Stripe webhook (and/or `/gifts/success`) marks the order paid and delivers the gift to chat + notifications.

## Production env vars

| Variable | Required | Notes |
|----------|----------|--------|
| `SECRET_KEY` | Yes | Long random string |
| `FLASK_ENV` | Yes | `production` |
| `APP_URL` | Yes (with Stripe) | Public https URL, no trailing slash |
| `STRIPE_SECRET_KEY` | For live gifts | `sk_live_…` or `sk_test_…` |
| `STRIPE_PUBLISHABLE_KEY` | For live gifts | Matching publishable key |
| `STRIPE_WEBHOOK_SECRET` | Recommended | Webhook signing secret |
| `STRIPE_CURRENCY` | No | Default `usd` |
| `MAIL_*` | No | Optional email |

## Deploy

`Procfile` uses gunicorn + eventlet:

```
web: gunicorn --worker-class eventlet -w 1 app:app
```

Works on Railway, Render, Heroku, and similar platforms. Set the env vars above, deploy, then configure the Stripe webhook to your live URL.

## Health check

`GET /api/health` → `{ status, app, stripe, env }`

## Project layout

- `app.py` — Flask + Socket.IO + Stripe
- `templates/` — login, dashboard, admin
- `data/` — JSON storage (users, messages, orders, gifts, …)
- `.env.example` — env template

## Security notes

- Passwords hashed with Werkzeug
- Secure cookies when `FLASK_ENV=production`
- ProxyFix for reverse proxies
- Stripe webhook signature verification when `STRIPE_WEBHOOK_SECRET` is set
- Atomic JSON writes with file locks
