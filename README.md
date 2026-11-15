# TextLink — Connect, Text & Send Gifts

Production messaging platform with email confirmation, SQL database, Stripe gifts, inbox, moderation, and account self-service.

## Features

- **Email confirmation** on register (+ resend)
- Password reset & change password
- SQLAlchemy DB (SQLite by default, Postgres via `DATABASE_URL`)
- Connection requests gate messaging/gifts/cards
- Conversation inbox + paginated chat
- File uploads for avatars/chat images (validated with Pillow)
- Stripe gift checkout, webhook fulfill, admin refunds
- **Admin monetization**: gifts + Premium + Profile Boosts pay into your Stripe account; pricing controls, revenue ledger, Stripe payouts
- Premium (gift discount + badge) and Profile Boost (Discover ranking)
- Admin: users, ban/unban, reports resolve, order ledger
- Block/report, analytics, cards, likes, follows
- Rate limiting on auth & payments
- Account export & delete

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env
python3 app.py
```

Open http://localhost:5000

Without SMTP configured in development, new accounts are auto-verified (or you get a `dev_verify_link`). In production, set `MAIL_*` and `REQUIRE_EMAIL_CONFIRM=true`.

## Important env vars

| Variable | Purpose |
|----------|---------|
| `SECRET_KEY` | Required in production |
| `FLASK_ENV=production` | Secure cookies, stricter payment rules |
| `APP_URL` | Public URL for email/Stripe links |
| `DATABASE_URL` | Optional Postgres URL |
| `MAIL_*` | SMTP for confirmation & notifications |
| `REQUIRE_EMAIL_CONFIRM` | Default `true` |
| `REQUIRE_CONNECTION_TO_MESSAGE` | Default `true` |
| `STRIPE_*` | Real gift payments |

## Deploy

`Procfile` → gunicorn + eventlet. Set env vars, add Stripe webhook to `/api/stripe/webhook`, configure SMTP for email confirmation.

## Health

`GET /api/health`
