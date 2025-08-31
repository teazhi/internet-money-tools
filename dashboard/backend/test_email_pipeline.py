#!/usr/bin/env python3
"""
Test the complete email processing pipeline with mock data
"""
import re
from datetime import datetime, timedelta

def is_valid_asin(asin):
    """Validate if a string is a proper Amazon ASIN format"""
    if not asin or len(asin) != 10:
        return False
    
    # Must start with B followed by 9 alphanumeric characters  
    if not re.match(r'^B[0-9A-Z]{9}$', asin):
        return False
        
    # Additional validation - avoid common false positives
    false_positives = [
        'BXT5V5XPNW',  'BOOPSS7GDF',  'BJZN9KFZ3K',  'BGFZD1HP12',
    ]
    
    if asin in false_positives:
        return False
        
    return True

def simulate_email_processing():
    """Simulate the complete email processing pipeline"""
    
    # Mock email data that simulates what Gmail API returns
    mock_emails = [
        {
            'id': '1',
            'payload': {
                'headers': [
                    {'name': 'Subject', 'value': '[Distill] Alert: B008XQO7WA price drop detected'},
                    {'name': 'From', 'value': 'alert@distill.io'},
                    {'name': 'Date', 'value': 'Wed, 28 Aug 2024 15:30:00 +0000'}
                ],
                'body': {
                    'data': 'VGhpcyBpcyBhIHRlc3QgZW1haWwgZm9yIEIwMDhYUU83V0E='  # Base64 encoded test content
                }
            }
        },
        {
            'id': '2', 
            'payload': {
                'headers': [
                    {'name': 'Subject', 'value': 'Price Alert: Product (ASIN: B07XVTRJKX) is now 30% off'},
                    {'name': 'From', 'value': 'alert@distill.io'},
                    {'name': 'Date', 'value': 'Thu, 29 Aug 2024 10:15:00 +0000'}
                ],
                'body': {
                    'data': 'UHJpY2UgZHJvcCBhbGVydCBmb3IgcHJvZHVjdCBCMDdYVlRSSkt4'
                }
            }
        },
        {
            'id': '3',
            'payload': {
                'headers': [
                    {'name': 'Subject', 'value': 'No ASIN in this email - just a test'},
                    {'name': 'From', 'value': 'alert@distill.io'},
                    {'name': 'Date', 'value': 'Fri, 30 Aug 2024 08:45:00 +0000'}
                ],
                'body': {
                    'data': 'VGhpcyBlbWFpbCBoYXMgbm8gQVNJTg=='
                }
            }
        }
    ]
    
    print("=== Simulating Email Processing Pipeline ===")
    
    # Simulate the extraction logic from the app
    alerts = []
    days_back = 7
    sender_filter = 'alert@distill.io'
    
    # Date filtering
    cutoff_date = datetime.now() - timedelta(days=days_back)
    print(f"🔍 Query would be: from:{sender_filter} after:{cutoff_date.strftime('%Y/%m/%d')}")
    print(f"📧 Processing {len(mock_emails)} mock emails...")
    
    for i, email_data in enumerate(mock_emails):
        print(f"\n--- Processing Email {i+1} ---")
        
        try:
            # Extract headers (simulating app logic)
            headers = {h['name']: h['value'] for h in email_data.get('payload', {}).get('headers', [])}
            subject = headers.get('Subject', '')
            sender = headers.get('From', '')
            date_received = headers.get('Date', '')
            
            print(f"Subject: {subject}")
            print(f"From: {sender}")
            print(f"Date: {date_received}")
            
            # Mock HTML content extraction
            html_content = f"<div>Email content for {subject}</div>"
            
            # ASIN extraction (using the improved pattern)
            asin = None
            asin_pattern = r'\b(B[0-9A-Z]{9})\b'  # Updated pattern
            
            print(f"Using pattern: {asin_pattern}")
            
            # Extract ASIN from subject line
            asin_match = re.search(asin_pattern, subject, re.IGNORECASE)
            
            if asin_match:
                potential_asin = asin_match.group(1)
                print(f"Found potential ASIN: {potential_asin}")
                if is_valid_asin(potential_asin):
                    asin = potential_asin
                    print(f"✅ Valid ASIN: {asin}")
                else:
                    print(f"❌ Invalid ASIN: {potential_asin}")
            else:
                print("No ASIN found in subject")
            
            # Fallback: try content patterns
            if not asin:
                print("Trying content patterns...")
                # Would try content patterns here
            
            # Skip emails without ASINs
            if not asin:
                print("❌ Skipping - no valid ASIN found")
                continue
            
            # Create alert object
            alert = {
                'retailer': 'Unknown',
                'asin': asin,
                'subject': subject,
                'html_content': html_content,
                'alert_time': date_received
            }
            
            alerts.append(alert)
            print(f"✅ Added alert for ASIN: {asin}")
            
        except Exception as e:
            print(f"❌ Error processing email: {e}")
            continue
    
    print(f"\n🎯 Final result: {len(alerts)} alerts processed")
    for alert in alerts:
        print(f"  - {alert['asin']}: {alert['subject'][:50]}...")

if __name__ == "__main__":
    simulate_email_processing()