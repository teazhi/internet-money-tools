#!/usr/bin/env python3
"""
Test script for DMS email fetching functionality
"""
import os
import sys
from datetime import datetime, timedelta

# Add current directory to Python path
sys.path.insert(0, '.')

# Load the app.py file directly 
print("Loading app.py...")
with open('app.py', 'r') as f:
    app_code = f.read()

# Execute the app code to get access to functions
exec(app_code)

def test_dms():
    print("=== Testing DMS Email Fetching ===")
    
    # First test the configuration
    try:        
        print("1. Testing email configuration...")
        config = get_discount_email_config()
        print(f"   Email config exists: {bool(config)}")
        if config:
            print(f"   Email address: {config.get('email_address', 'Not set')}")
            print(f"   Config type: {config.get('config_type', 'Not set')}")
        
        print("2. Testing days back configuration...")
        days_back = get_discount_email_days_back()
        print(f"   Days back: {days_back}")
        
        # Test the actual email fetching
        print("3. Testing email fetching...")
        alerts = fetch_discount_email_alerts()
        print(f"   Total alerts fetched: {len(alerts)}")
        
        if alerts:
            print("   First few alerts:")
            for i, alert in enumerate(alerts[:3]):
                print(f"   Alert {i+1}:")
                print(f"     ASIN: {alert.get('asin')}")
                print(f"     Subject: {alert.get('subject', '')[:80]}...")
                print(f"     Retailer: {alert.get('retailer')}")
                print(f"     Time: {alert.get('alert_time')}")
        
        # Test ASIN validation function
        print("4. Testing ASIN validation...")
        test_asins = ['B008XQO7WA', 'B07XVTRJKX', 'INVALID123', '']
        for test_asin in test_asins:
            result = is_valid_asin(test_asin)
            print(f"   {test_asin}: {result}")
            
    except Exception as e:
        print(f"Error during testing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_dms()