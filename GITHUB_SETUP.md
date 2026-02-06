# GitHub Setup Instructions

## Step 1: Initialize Git Repository

```bash
cd c:\Users\Tinted\Documents\python
git init
git add .
git commit -m "Initial commit: Valentine's Love app"
```

## Step 2: Create GitHub Repository

1. Go to https://github.com/new
2. Name it: `valentines-love`
3. Add description: "A Valentine's Day connection app"
4. Click "Create repository"

## Step 3: Push to GitHub

Copy the commands from GitHub (it will look like):

```bash
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/valentines-love.git
git push -u origin main
```

Paste them in your terminal.

## Step 4: Deploy to Railway

1. Go to https://railway.app
2. Login with GitHub
3. Click "Start a New Project"
4. Select "Deploy from GitHub"
5. Find and select `valentines-love`
6. Railway will automatically deploy!

## Step 5: Set Environment Variables

In Railway dashboard:
1. Go to your project
2. Click "Environment"
3. Add variables:
   ```
   SECRET_KEY=<generate-a-random-string>
   FLASK_ENV=production
   ```
4. Redeploy

## Done! 🎉

Your app is now live! Railway will give you a URL like:
`https://valentines-love.up.railway.app`

---

## Subsequent Deployments

Just push to GitHub:
```bash
git add .
git commit -m "Your changes"
git push
```

Railway will automatically redeploy!

---

## Troubleshooting

**App won't start?**
- Check Railway logs for errors
- Ensure all dependencies are in requirements.txt

**Environment variables not working?**
- Redeploy after adding variables
- Check variable names are exact matches

**Need to use custom domain?**
- Railway → Domains → Add Custom Domain
- Update DNS records with Railway's nameservers
