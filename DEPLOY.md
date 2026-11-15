# Deploy TextLink

## 1. Push code & create a host project

Recommended: **Railway** (or Render / Heroku). Connect the GitHub repo; the `Procfile` starts gunicorn + eventlet automatically.

## 2. Set environment variables

**Required**

- `SECRET_KEY` — long random string  
- `FLASK_ENV=production`  
- `APP_URL` — your public HTTPS URL (no trailing slash), e.g. `https://textlink.up.railway.app`

**Stripe (real gift payments)**

- `STRIPE_SECRET_KEY`  
- `STRIPE_PUBLISHABLE_KEY`  
- `STRIPE_WEBHOOK_SECRET`  
- `STRIPE_CURRENCY=usd` (optional)

**Email (optional)**

- `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USE_TLS`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_DEFAULT_SENDER`

## 3. Stripe webhook

In Stripe Dashboard → Developers → Webhooks:

- Endpoint URL: `https://YOUR_DOMAIN/api/stripe/webhook`
- Event: `checkout.session.completed`
- Paste the signing secret into `STRIPE_WEBHOOK_SECRET`

Use **test** keys first (`sk_test_…` / `pk_test_…`), then switch to **live** keys when ready.

## 4. Verify

- Open the site → register → **Buy Gifts** → pay with test card `4242 4242 4242 4242`
- `GET /api/health` should show `"stripe": true` when keys are set

## Notes

- Without Stripe keys, gifts still work in **demo mode** locally (no charge). In production, Stripe keys are required for purchases.
- First registered user is automatically an admin.
- See `README.md` for the full feature list and gift flow.
