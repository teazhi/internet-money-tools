#!/usr/bin/env python3
"""
Debug script to test discount opportunities without authentication
"""

import sys
import os
from datetime import datetime, timedelta, date
import pytz

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import from app.py
from app import (
    fetch_discount_email_alerts,
    get_user_record,
    analytics_cache,
    CONFIG_CACHE_EXPIRY_MINUTES,
    config_cache
)

def debug_enhanced_analytics():
    """Debug why enhanced_analytics might be empty"""
    
    print("🔍 Starting Discount Opportunities Debug...")
    
    # Test 1: Check email alerts
    print("\n1. Testing email alerts fetch...")
    try:
        email_alerts = fetch_discount_email_alerts()
        print(f"✅ Found {len(email_alerts)} email alerts")
        
        if email_alerts:
            sample_alerts = email_alerts[:3]
            for i, alert in enumerate(sample_alerts):
                print(f"   Alert {i+1}: ASIN={alert.get('asin')}, retailer={alert.get('retailer')}")
        else:
            print("   ⚠️  No email alerts found")
            
    except Exception as e:
        print(f"❌ Error fetching email alerts: {e}")
        return
    
    # Test 2: Check if we can simulate analytics generation
    print("\n2. Testing analytics generation simulation...")
    
    # Use a test discord ID (we won't actually fetch user data)
    test_discord_id = "123456789"
    today = datetime.now(pytz.UTC).date()
    
    print(f"   Today's date: {today}")
    print(f"   Analytics cache key: enhanced_analytics_{test_discord_id}_{today}")
    print(f"   Current analytics cache size: {len(analytics_cache)}")
    
    # Check if there's any cached analytics data
    if analytics_cache:
        print("   📋 Analytics cache contents:")
        for key in analytics_cache.keys():
            cache_entry = analytics_cache[key]
            timestamp = cache_entry.get('timestamp')
            data_size = len(cache_entry.get('data', {})) if cache_entry.get('data') else 0
            print(f"      {key}: {data_size} items, timestamp={timestamp}")
    else:
        print("   📋 Analytics cache is empty")
    
    # Test 3: Check config cache
    print("\n3. Testing config cache...")
    print(f"   Config cache size: {len(config_cache)}")
    if config_cache:
        print("   📋 Config cache contents:")
        for key in config_cache.keys():
            print(f"      {key}")
    
    print("\n🔍 Debug complete!")

if __name__ == "__main__":
    debug_enhanced_analytics()