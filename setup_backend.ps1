# FloodGuard Setup Script
# Run this from the backend directory

Write-Host "=== FloodGuard Backend Setup ===" -ForegroundColor Cyan
Write-Host ""

# Check if Python is available
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "Python not found. Please install Python 3.8+" -ForegroundColor Red
    exit 1
}

# Navigate to backend directory
Set-Location -Path "D:\FLoodGuard\backend"

# Create virtual environment if it doesn't exist
if (-not (Test-Path "venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& "D:\FLoodGuard\backend\venv\Scripts\Activate.ps1"

# Install dependencies
Write-Host "Installing dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt

# Run migrations
Write-Host "Running database migrations..." -ForegroundColor Yellow
python manage.py makemigrations
python manage.py migrate

# Register sensors
Write-Host "Registering ESP32 sensors..." -ForegroundColor Yellow
python manage.py register_sensors

Write-Host ""
Write-Host "=== Setup Complete! ===" -ForegroundColor Green
Write-Host ""
Write-Host "To start the server:" -ForegroundColor Cyan
Write-Host "  cd D:\FLoodGuard\backend"
Write-Host "  venv\Scripts\activate"
Write-Host "  python manage.py runserver 0.0.0.0:8000"
Write-Host ""
Write-Host "Dashboard will be available at: http://localhost:8000" -ForegroundColor Cyan
