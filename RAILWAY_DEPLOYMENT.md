# 🚂 Railway Deployment Guide for AI Insem

## Overview
Your AI Insem pedestrian detection application is fully prepared for Railway deployment. All configuration files are ready and committed to your GitHub repository.

## 📋 Deployment Steps

### Step 1: Create Railway Account
1. Visit [railway.app](https://railway.app)
2. Click **"Get Started"**
3. Sign up with **GitHub** (recommended) or email
4. Verify your email if required

### Step 2: Deploy from GitHub
1. Click **"New Project"** in Railway dashboard
2. Select **"Deploy from GitHub repo"**
3. Search for your repository: `Harryrocks19/smart-pedestrian-detection-system`
4. Click **"Connect GitHub"** if prompted
5. Select your repository from the list
6. Click **"Deploy"**

### Step 3: Monitor Deployment
- Railway will automatically build your Docker container
- Install all Python dependencies
- Deploy both API server and Streamlit dashboard
- This may take **5-15 minutes** for first deployment

## 🌐 Access Your Application

Once deployed, you'll get a Railway domain like:
- **API Server**: `https://your-project.railway.app`
  - Health check: `https://your-project.railway.app/status`
  - Alerts: `https://your-project.railway.app/alerts`
- **Dashboard**: `https://your-project.railway.app:8501`

## 📁 Configuration Files

The following files have been created for Railway deployment:

- `Dockerfile` - Container build instructions
- `railway.json` - Railway platform configuration
- `start.sh` - Startup script for both services
- `requirements.txt` - Python dependencies
- `.dockerignore` - Build optimization

## 💰 Pricing

- **Hobby Plan**: $5/month (512MB RAM, perfect for development)
- **Pro Plan**: $10/month (2GB RAM, recommended for ML workloads)

## 🔧 Troubleshooting

### Build Fails
- Check Railway build logs in dashboard
- Ensure all dependencies are in `requirements.txt`
- Verify Dockerfile syntax

### App Won't Start
- Check container logs in Railway dashboard
- Verify `start.sh` has execute permissions
- Ensure ports 5000 and 8501 are available

### Performance Issues
- Upgrade to Pro plan for more RAM
- Check Railway metrics dashboard
- Optimize ML model loading

## 🚀 Post-Deployment

1. **Add Custom Domain** (optional)
   - Go to Railway project settings
   - Add your custom domain
   - Configure DNS records

2. **Set Environment Variables** (if needed)
   - Add any required env vars in Railway dashboard
   - Examples: API keys, database URLs

3. **Monitor & Scale**
   - Use Railway's built-in monitoring
   - Scale resources as needed
   - Set up alerts for downtime

## 📞 Support

- Railway Docs: [docs.railway.app](https://docs.railway.app)
- Railway Discord: [railway.app/discord](https://railway.app/discord)

---

**🎉 Your AI Insem app is ready for production on Railway!**