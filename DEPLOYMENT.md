# Valentine's Love - Deployment Guide

## Quick Deployment Options

### Option 1: Railway (Recommended - Easiest)

1. **Sign up** at https://railway.app
2. **Create a new project**
3. **Connect your GitHub repository** (or upload directly)
4. **Add environment variables**:
   - `SECRET_KEY` = your-secret-key
   - `MAIL_SERVER` = smtp.gmail.com (optional)
   - `MAIL_PORT` = 587 (optional)
   - `MAIL_USERNAME` = your-email@gmail.com (optional)
   - `MAIL_PASSWORD` = your-app-password (optional)
5. **Deploy** - Railway will automatically detect the Procfile

**Live URL**: Your app will be available at `your-app-name.railway.app`

---

### Option 2: Render

1. **Sign up** at https://render.com
2. **Create new Web Service**
3. **Connect GitHub repository**
4. **Configure**:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn --worker-class eventlet -w 1 app:app`
5. **Add environment variables** (same as above)
6. **Deploy**

**Live URL**: Your app will be available at `your-app-name.onrender.com`

---

### Option 3: Heroku (Alternative)

1. **Install Heroku CLI** from https://devcenter.heroku.com/articles/heroku-cli
2. **Login**: `heroku login`
3. **Create app**: `heroku create your-app-name`
4. **Set environment variables**:
   ```bash
   heroku config:set SECRET_KEY=your-secret-key
   ```
5. **Deploy**: 
   ```bash
   git push heroku main
   ```

**Live URL**: Your app will be available at `your-app-name.herokuapp.com`

---

### Option 4: PythonAnywhere

1. **Sign up** at https://www.pythonanywhere.com/
2. **Upload your files** via web interface
3. **Configure WSGI file** in Web tab
4. **Add environment variables** in .env file
5. **Reload web app**

**Live URL**: Your app will be available at `yourusername.pythonanywhere.com`

---

## Setup Instructions for All Platforms

### Prerequisites
- GitHub account (for Railway/Render/Heroku)
- Your Flask app ready to deploy

### Before Deploying
1. Update `.env` with production settings
2. Ensure all dependencies are in `requirements.txt`
3. Test locally: `python app.py`

### Environment Variables to Set
```
SECRET_KEY=your-secure-random-key-here
FLASK_ENV=production
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-specific-password
```

---

## Post-Deployment

1. **Test your app** by visiting the live URL
2. **Create an account** and test features
3. **Monitor logs** in your platform's dashboard
4. **Set up custom domain** (optional)

---

## Troubleshooting

### "502 Bad Gateway"
- Check that app starts without errors: `python app.py`
- Verify all dependencies are in requirements.txt
- Check environment variables are set correctly

### "Module not found"
- Ensure requirements.txt has all packages
- Run `pip install -r requirements.txt` locally to test

### "SocketIO not connecting"
- Ensure flask-socketio is installed
- Add CORS allowed origins in production

### File uploads not working
- Check that `data/uploads` directory exists and is writable
- Some platforms have ephemeral filesystems; use cloud storage instead

---

## Recommended: Railway Quick Deploy

1. Go to https://railway.app
2. Click "Start a New Project"
3. Select "Deploy from GitHub"
4. Authorize and select this repository
5. Railway automatically detects Procfile and deploys!

Your app will be live in 2-3 minutes!
