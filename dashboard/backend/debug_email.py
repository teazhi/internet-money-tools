#!/usr/bin/env python3

import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import app configuration
from app import DISCOUNT_MONITOR_EMAIL, DISCOUNT_SENDER_EMAIL, get_discount_email_days_back, get_users_config

def debug_email_config():
    print("=== Email Configuration Debug ===")
    print(f"DISCOUNT_MONITOR_EMAIL: {DISCOUNT_MONITOR_EMAIL}")
    print(f"DISCOUNT_SENDER_EMAIL: {DISCOUNT_SENDER_EMAIL}")
    print(f"Days back: {get_discount_email_days_back()}")
    
    if not DISCOUNT_MONITOR_EMAIL:
        print("\n❌ DISCOUNT_MONITOR_EMAIL is not configured!")
        print("This is why no emails are being found.")
        print("\nTo fix this:")
        print("1. Set the DISCOUNT_MONITOR_EMAIL environment variable")
        print("2. Or configure it in your app settings")
        return False
    
    print(f"\n=== User Configuration ===")
    users = get_users_config()
    print(f"Total users: {len(users)}")
    
    # Find user with monitor email
    monitor_user = None
    for user in users:
        if user.get('email') == DISCOUNT_MONITOR_EMAIL:
            monitor_user = user
            break
    
    if monitor_user:
        print(f"✅ Found user with monitor email: {DISCOUNT_MONITOR_EMAIL}")
        print(f"Has Google tokens: {bool(monitor_user.get('google_tokens'))}")
        print(f"Google linked: {monitor_user.get('google_linked', False)}")
        if monitor_user.get('google_tokens'):
            print(f"Token keys: {list(monitor_user.get('google_tokens', {}).keys())}")
    else:
        print(f"❌ No user found with email: {DISCOUNT_MONITOR_EMAIL}")
        print("Available users:")
        for user in users:
            print(f"  - {user.get('email', 'No email')}")
    
    return True

if __name__ == "__main__":
    debug_email_config()