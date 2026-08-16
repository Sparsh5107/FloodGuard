#!/usr/bin/env python
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'floodguard.settings')
sys.path.insert(0, 'D:\\FLoodGuard\\backend')

import subprocess
import time
import requests
import json
import signal
import atexit

# Start the server
proc = subprocess.Popen(
    [sys.executable, 'manage.py', 'runserver', '0.0.0.0:8000'],
    cwd='D:\\FLoodGuard\\backend',
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)

# Wait for server to start
time.sleep(3)

try:
    # Test the predictions API
    r = requests.get('http://127.0.0.1:8000/api/predictions/', timeout=10)
    print(f"Status: {r.status_code}")
    print(f"Response: {r.text[:2000]}")
    
    # Test single sensor prediction
    r2 = requests.get('http://127.0.0.1:8000/api/predictions/esp32-001/', timeout=10)
    print(f"\nSingle sensor Status: {r2.status_code}")
    print(f"Single sensor Response: {r2.text[:2000]}")
    
    # Test what-if simulator
    r3 = requests.post('http://127.0.0.1:8000/api/predictions/whatif/', 
                       json={'device_id': 'esp32-001', 'rainfall_mm': 40, 'duration_hours': 3},
                       timeout=10)
    print(f"\nWhat-if Status: {r3.status_code}")
    print(f"What-if Response: {r3.text[:2000]}")
    
    # Test sensor status
    r4 = requests.get('http://127.0.0.1:8000/api/sensor-status/', timeout=10)
    print(f"\nSensor status: {r4.text[:500]}")
    
finally:
    # Kill the server
    proc.terminate()
    proc.wait()
    print("\nServer stopped")