# TextLink — Deployment checklist

Use **HOSTING.md** as the source of truth.

Quick tick list:

- [ ] `SECRET_KEY` set (strong random)
- [ ] `FLASK_ENV=production`
- [ ] `APP_URL` = public HTTPS URL
- [ ] Postgres `DATABASE_URL` (recommended)
- [ ] SMTP `MAIL_*` for email confirmation
- [ ] Stripe keys + webhook `/api/stripe/webhook`
- [ ] Deploy via Procfile (gunicorn + eventlet)
- [ ] `/api/health` OK
- [ ] Register → confirm email works
- [ ] Gift / Premium test payment works
- [ ] Admin can see Platform Revenue
