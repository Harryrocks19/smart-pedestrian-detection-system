@echo off
echo 🚂 AI Insem Railway Deployment Script
echo ======================================

echo Step 1: Installing Railway CLI...
powershell -Command "& {try { npm install -g @railway/cli } catch { echo 'npm not found, trying alternative...'; Invoke-WebRequest -Uri 'https://railway.app/install.ps1' -OutFile 'install-railway.ps1'; .\install-railway.ps1 }}"

echo.
echo Step 2: Please complete these manual steps:
echo 1. Go to https://railway.app and create account
echo 2. Connect your GitHub account to Railway
echo 3. Create a new project from GitHub repo: Harryrocks19/smart-pedestrian-detection-system
echo.
echo Press any key when you've completed the above steps...
pause >nul

echo.
echo Step 3: Logging into Railway...
railway login

echo.
echo Step 4: Linking to your Railway project...
railway link

echo.
echo Step 5: Deploying application...
railway deploy

echo.
echo Step 6: Getting deployment URLs...
railway domain

echo.
echo 🎉 Deployment complete!
echo Your app should be available at the domain shown above
echo API: https://your-domain.railway.app
echo Dashboard: https://your-domain.railway.app:8501

pause