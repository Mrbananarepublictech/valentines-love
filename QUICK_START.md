# Valentine's Love - Quick Start Guide

## 🚀 Deploy Now (30 seconds!)

### Fastest Method: Railway

1. **Visit**: https://railway.app
2. **Click**: "Start a New Project" → "Deploy from GitHub"
3. **Authorize** GitHub and select your repository
4. **Railway will automatically:**
   - Detect the Procfile
   - Install dependencies from requirements.txt
   - Deploy your app
   - Give you a live URL

**Your app will be live in 2-3 minutes!**

---

## Alternative: Render

1. Visit https://render.com
2. Click "New +" → "Web Service"
3. Connect your GitHub repository
4. Use these settings:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn --worker-class eventlet -w 1 app:app`
5. Add environment variables
6. Click "Create Web Service"

---

## Environment Variables to Set

In your deployment platform's settings, add:

```
SECRET_KEY=your-random-secret-key-here
FLASK_ENV=production
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
```

---

## After Deployment

1. ✅ Visit your live URL
2. ✅ Create a test account
3. ✅ Test all features
4. ✅ Share with friends!

---

## Features Deployed

✨ User Registration & Authentication
💌 Valentine's Love Requests
💕 Like & Follow System
👥 Discover & Connect
💬 Real-time Messaging
🎁 Gift Recommendations
🎨 Custom Love Cards
📊 Analytics & Statistics
🔔 Notifications
⚙️ Settings & Preferences
🚨 Report & Block Users

---

## Need Help?

- **Railway**: https://docs.railway.app
- **Render**: https://render.com/docs
- **Documentation**: See DEPLOYMENT.md

Your Valentine's Love app is ready to connect people! 💕
