#!/usr/bin/env python3
"""
Debug script to check user's COGS configuration
"""
import requests
import json

def check_cogs_status():
    """Check the user's COGS configuration status"""
    try:
        # Make request to debug endpoint
        response = requests.get('http://localhost:5000/api/debug/cogs-status', 
                              cookies={'session': 'your_session_cookie_here'})  # User would need to provide their session
        
        if response.status_code == 200:
            data = response.json()
            debug_info = data['debug_info']
            
            print("=== COGS Configuration Status ===")
            print(f"Source Links Enabled: {debug_info['enable_source_links']}")
            print(f"Sheet ID Configured: {debug_info['sheet_id']}")
            print(f"Worksheet Title Configured: {debug_info['worksheet_title']}")
            print(f"Google Tokens Available: {debug_info['google_tokens']}")
            print(f"Column Mapping: {debug_info['column_mapping']}")
            print(f"Orders URL Configured: {debug_info['sellerboard_orders_url']}")
            print(f"Stock URL Configured: {debug_info['sellerboard_stock_url']}")
            print(f"User Fully Configured: {debug_info['user_configured']}")
            
            # Provide recommendations
            print("\n=== Recommendations ===")
            if not debug_info['enable_source_links']:
                print("❌ ISSUE: Source Links toggle is disabled")
                print("   → Go to Settings and enable 'Source Links from Google Sheet'")
            
            if not debug_info['sheet_id'] or not debug_info['worksheet_title']:
                print("❌ ISSUE: Google Sheet not configured")
                print("   → Complete Google Sheet setup in the onboarding process")
            
            if not debug_info['google_tokens']:
                print("❌ ISSUE: Google authentication missing")
                print("   → Reconnect your Google account")
            
            if debug_info['enable_source_links'] and debug_info['user_configured'] and debug_info['google_tokens']:
                print("✅ Configuration looks good! Restock buttons should appear.")
                
        else:
            print(f"Error: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"Error checking COGS status: {e}")

if __name__ == "__main__":
    print("This script requires manual session setup.")
    print("For now, let's create a simple guide for the user...")
    
    print("\n=== Troubleshooting Guide for Missing Restock Buttons ===")
    print("\n1. Check Settings Page:")
    print("   - Go to Dashboard → Settings")
    print("   - Ensure 'Source Links from Google Sheet' toggle is ENABLED")
    print("   - This toggle is disabled by default for privacy")
    
    print("\n2. Verify Google Sheet Setup:")
    print("   - Make sure you completed the Google Sheet setup during onboarding")
    print("   - Your sheet should have columns for ASIN, COGS, and Source links")
    print("   - Ensure there are products with COGS data in your sheet")
    
    print("\n3. Check Smart Restock Page:")
    print("   - Go to Dashboard → Smart Restock (enhanced-analytics)")
    print("   - Restock buttons appear only for products that have:")
    print("     • Active restock alerts (products need restocking)")
    print("     • COGS data available in your Google Sheet")
    print("     • Source links in your Google Sheet")
    
    print("\n4. Browser Console Check:")
    print("   - Open browser Developer Tools (F12)")
    print("   - Go to Console tab")
    print("   - Look for debug messages starting with '[DEBUG] SmartRestockAlerts'")
    print("   - This will show if analytics data is being loaded correctly")
    
    print("\n5. Backend Logs:")
    print("   - Check the backend console for messages like:")
    print("   - '[DEBUG] Successfully fetched COGS data for X products'")
    print("   - If you see errors, they'll help identify the issue")