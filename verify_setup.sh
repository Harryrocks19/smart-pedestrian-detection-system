#!/bin/bash
# verify_setup.sh — Pre-deployment verification script
# Run this before deploying to catch errors early

echo "🔍 AI Insem Project Verification"
echo "=================================="

ERRORS=0
WARNINGS=0

# Function to check if file exists
check_file() {
    if [ -f "$1" ]; then
        echo "✅ $1"
    else
        echo "❌ $1 - NOT FOUND"
        ((ERRORS++))
    fi
}

# Function to check if directory exists
check_dir() {
    if [ -d "$1" ]; then
        echo "✅ $1/"
    else
        echo "⚠️  $1/ - NOT FOUND (will be created at runtime)"
        ((WARNINGS++))
    fi
}

echo ""
echo "📁 Checking Python files..."
check_file "api_server.py"
check_file "dashboard.py"
check_file "Pedestrian_Detection.py"
check_file "db_manager.py"
check_file "saas_config.py"
check_file "pdf_report.py"
check_file "sort.py"
check_file "requirements.txt"
check_file ".env.example"

echo ""
echo "🐳 Checking Docker files..."
check_file "Dockerfile"
check_file "start.sh"
check_file ".dockerignore"
check_file "railway.json"
check_file "railway.toml"

echo ""
echo "🚄 Checking Flutter files..."
check_file "flutter_app/pubspec.yaml"
check_file "flutter_app/lib/main.dart"
check_file "flutter_app/test/widget_test.dart"

echo ""
echo "📊 Checking log directories..."
check_dir "logs"
check_dir "logs/snapshots"
check_dir "logs/incidents"
check_dir "logs/heatmaps"
check_dir "logs/reports"

echo ""
echo "🤖 Checking model files..."
if [ -f "yolov8n.pt" ]; then
    SIZE=$(du -h yolov8n.pt | cut -f1)
    echo "✅ yolov8n.pt ($SIZE)"
else
    echo "⚠️  yolov8n.pt - NOT FOUND (will be downloaded at runtime)"
    ((WARNINGS++))
fi

echo ""
echo "📦 Python Dependencies Check..."
python3 -c "
import sys
missing = []
try:
    import flask
    print('✅ flask')
except ImportError:
    missing.append('flask')
    print('❌ flask - NOT INSTALLED')

try:
    import streamlit
    print('✅ streamlit')
except ImportError:
    missing.append('streamlit')
    print('❌ streamlit - NOT INSTALLED')

try:
    import cv2
    print('✅ opencv')
except ImportError:
    missing.append('opencv')
    print('❌ opencv - NOT INSTALLED')

try:
    import ultralytics
    print('✅ ultralytics')
except ImportError:
    missing.append('ultralytics')
    print('❌ ultralytics - NOT INSTALLED')

if missing:
    print()
    print('Missing packages. Run: pip install -r requirements.txt')
    sys.exit(1)
" 2>/dev/null || echo "⚠️  Some Python packages not installed (will install in Docker)"

echo ""
echo "🔐 Environment Configuration Check..."
if [ -f ".env" ]; then
    echo "✅ .env file found"
else
    echo "⚠️  .env file not found"
    echo "  → Copy from .env.example and fill in your values"
    ((WARNINGS++))
fi

echo ""
echo "════════════════════════════════════"
echo "📊 VERIFICATION SUMMARY"
echo "════════════════════════════════════"
echo "Errors:   $ERRORS"
echo "Warnings: $WARNINGS"

if [ $ERRORS -gt 0 ]; then
    echo ""
    echo "❌ DEPLOYMENT BLOCKED - Fix errors above"
    exit 1
elif [ $WARNINGS -gt 0 ]; then
    echo ""
    echo "⚠️  WARNINGS - Review above but OK to deploy"
    exit 0
else
    echo ""
    echo "✅ ALL CHECKS PASSED - Ready to deploy!"
    exit 0
fi
