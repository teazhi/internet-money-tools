# Deployment Guide - builders+ Dashboard

## 🚀 Railway Deployment (Recommended)

### Prerequisites
- GitHub account
- Discord Developer Application
- AWS S3 bucket for user configuration storage

### Step 1: Prepare Repository
```bash
git add .
git commit -m "Prepare for Railway deployment"
git push origin main
```

### Step 2: Deploy to Railway
1. Go to [railway.app](https://railway.app)
2. Click "Login with GitHub"
3. Click "New Project" → "Deploy from GitHub repo"
4. Select your repository
5. Railway will automatically detect and deploy your Flask app

### Step 3: Configure Environment Variables
In Railway dashboard, go to your project → Variables → Add these:

#### Required Variables:
```
FLASK_SECRET_KEY=generate-a-secure-random-string
DISCORD_CLIENT_ID=your-discord-client-id
DISCORD_CLIENT_SECRET=your-discord-client-secret
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
CONFIG_S3_BUCKET=your-s3-bucket-name
```

#### Optional Variables:
```
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
FRONTEND_URL=https://your-frontend-domain.vercel.app
```

### Step 4: Update Discord Application
1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Select your application
3. Go to OAuth2 → General
4. Update Redirect URIs to include:
   ```
   https://your-app.railway.app/auth/discord/callback
   ```

### Step 5: Deploy Frontend (Optional)
You can deploy the React frontend separately to Vercel:

1. Go to [vercel.com](https://vercel.com)
2. Import your GitHub repository
3. Set build command: `cd frontend && npm run build`
4. Set output directory: `frontend/build`
5. Add environment variable: `REACT_APP_API_URL=https://your-app.railway.app`

## 🌐 Custom Domain (Optional)

### Railway Custom Domain:
1. Go to Railway project → Settings → Domains
2. Add your custom domain
3. Update DNS records as instructed
4. SSL certificate is automatically provisioned

### Update Environment Variables:
```
DISCORD_REDIRECT_URI=https://yourdomain.com/auth/discord/callback
FRONTEND_URL=https://yourdomain.com
```

## 📊 Monitoring

### Health Check
Your app includes a health check endpoint: `/api/health`

### Uptime Monitoring (Free)
1. Sign up for [UptimeRobot](https://uptimerobot.com)
2. Add HTTP monitor for: `https://your-app.railway.app/api/health`
3. Set check interval to 5 minutes

### View Logs
- Railway: Project → Deployments → View logs
- Real-time monitoring in Railway dashboard

## 🔧 Troubleshooting

### Common Issues:

#### 1. "Application Error" on Railway
- Check logs in Railway dashboard
- Verify all environment variables are set
- Ensure requirements.txt includes all dependencies

#### 2. Discord OAuth Not Working
- Verify redirect URI matches exactly
- Check Discord application settings
- Ensure DISCORD_CLIENT_ID and DISCORD_CLIENT_SECRET are correct

#### 3. AWS S3 Errors
- Verify AWS credentials have S3 permissions
- Check bucket name is correct
- Ensure bucket exists and is accessible

#### 4. CORS Errors
- Update FRONTEND_URL environment variable
- Check allowed origins in Flask app
- Verify frontend is making requests to correct backend URL

### Debug Endpoints:
- Health check: `/api/health`
- Stock columns debug: `/api/debug/stock-columns`

## 💰 Cost Estimate

### Railway:
- **Free tier**: $5 credit monthly (usually sufficient)
- **Estimated usage**: $2-4/month for small apps
- **Scaling**: Automatic based on usage

### Total estimated cost: **Free to $5/month**

## 🚀 Going Live Checklist

- [ ] Repository pushed to GitHub
- [ ] Railway deployment successful
- [ ] Environment variables configured
- [ ] Discord OAuth redirect URI updated
- [ ] Health check endpoint responding
- [ ] Test login flow works
- [ ] Test analytics functionality
- [ ] Optional: Custom domain configured
- [ ] Optional: Uptime monitoring setup

Your builders+ dashboard should now be live and accessible worldwide! 🎉