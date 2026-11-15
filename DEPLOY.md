# Deploy TextLink

## Env vars

**Required**
- `SECRET_KEY`
- `FLASK_ENV=production`
- `APP_URL` (public HTTPS URL)

**Email confirmation (required in production)**
- `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USE_TLS`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_DEFAULT_SENDER`
- `REQUIRE_EMAIL_CONFIRM=true`

**Database**
- Default: SQLite at `data/textlink.db` (fine for single-instance)
- Recommended: `DATABASE_URL=postgresql://…` on Railway/Render

**Stripe gifts**
- `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`
- Webhook: `https://YOUR_DOMAIN/api/stripe/webhook` → `checkout.session.completed`

**Optional**
- `REQUIRE_CONNECTION_TO_MESSAGE=true`
- `CORS_ORIGINS=https://YOUR_DOMAIN`

## Procfile

```
web: gunicorn --worker-class eventlet -w 1 app:app
```

## After deploy

1. Register → confirm email from inbox  
2. Connect two users → message / buy gift  
3. `/api/health` should show `mail` / `stripe` as expected  

## How the admin makes money

With Stripe keys set, **all** of these pay into the **same Stripe account**:

1. **Gift purchases** (100% platform revenue)
2. **Premium memberships** (user Upgrade tab)
3. **Profile Boosts** (featured in Discover)

Then withdraw:

1. https://dashboard.stripe.com/balance/overview  
2. Add a bank account  
3. Payout  

Admin UI → **Platform Revenue** shows totals by type and lets you change Premium/Boost prices.
