# TextLink — Pre-Hosting Checklist

The product is branded **TextLink** (not Valentine’s Love). Use this before you go live.

---

## Already built (ready to use)

| Area | Status |
|------|--------|
| Register / login / logout | Done |
| Email confirmation + resend | Done (needs SMTP in production) |
| Password reset & change password | Done |
| Profiles, bio, photo upload | Done |
| Connection requests → gate chat/gifts | Done |
| Inbox + messaging + image share | Done |
| Cards, likes, follows, block, report | Done |
| Stripe gifts + Premium + Boosts | Done |
| Admin users / ban / reports / refunds | Done |
| Admin revenue + pricing controls | Done |
| SQL DB (SQLite or Postgres) | Done |
| Rate limits, health check | Done |
| Account export / delete | Done |

---

## Must do before hosting (required)

These are **configuration / ops**, not missing app features:

### 1. Environment variables
Set on Railway / Render / similar:

| Variable | Why |
|----------|-----|
| `SECRET_KEY` | Strong random secret (required in production) |
| `FLASK_ENV=production` | Secure cookies + stricter payments |
| `APP_URL` | Your public HTTPS URL (emails + Stripe redirects) |
| `MAIL_SERVER` / `MAIL_PORT` / `MAIL_USE_TLS` | Email confirmation |
| `MAIL_USERNAME` / `MAIL_PASSWORD` | SMTP login (e.g. Gmail app password) |
| `MAIL_DEFAULT_SENDER` | From address |
| `STRIPE_SECRET_KEY` | Live or test secret key |
| `STRIPE_PUBLISHABLE_KEY` | Matching publishable key |
| `STRIPE_WEBHOOK_SECRET` | From Stripe webhook endpoint |
| `DATABASE_URL` | **Strongly recommended** Postgres URL (SQLite is wiped on most PaaS restarts) |

### 2. Postgres (strongly recommended)
SQLite on Railway/Render is **ephemeral** — users, chats, and paid orders can disappear on redeploy.  
Attach a Postgres plugin and set `DATABASE_URL`.

### 3. Stripe webhook
- Endpoint: `https://YOUR_DOMAIN/api/stripe/webhook`
- Event: `checkout.session.completed`
- Paste signing secret into `STRIPE_WEBHOOK_SECRET`

### 4. SMTP for email confirmation
Without mail in production, new users cannot verify (unless you set `REQUIRE_EMAIL_CONFIRM=false`, not recommended).

### 5. HTTPS + domain
Use the host’s HTTPS URL (or custom domain). Put that exact URL in `APP_URL` and `CORS_ORIGINS` if you lock CORS.

### 6. First admin
- Fresh DB: first registered user becomes admin  
- Or use an existing admin account after migrating data  

### 7. Smoke test after deploy
1. `/api/health` → `status: ok`, `stripe` / `mail` as expected  
2. Register → confirm email  
3. Two users connect → message  
4. Buy a gift / Premium with Stripe test card `4242…`  
5. Admin → Platform Revenue shows the payment  

---

## Nice to have (not blockers for first launch)

| Item | Notes |
|------|--------|
| Persistent file storage (S3/R2) | Uploads currently on local disk; may vanish on redeploy |
| Redis for Socket.IO + rate limits | Needed only if you run multiple app instances |
| Custom domain + brand email | e.g. `noreply@yourdomain.com` |
| Stripe live keys | Switch from `sk_test_` / `pk_test_` when ready for real money |
| Legal pages | Terms / Privacy / Refund policy (especially for payments) |
| Backups | Enable Postgres automated backups |
| Monitoring | Host logs + uptime check on `/api/health` |

---

## Not required to launch

- Mobile native apps  
- Web Push / offline PWA  
- Multi-region CDN  
- Changing the GitHub repo name (`valentines-love` can stay; the **product name** is TextLink)

---

## Deploy command (already in repo)

```
web: gunicorn --worker-class eventlet -w 1 app:app
```

See also `DEPLOY.md` and `.env.example`.
