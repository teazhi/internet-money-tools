#!/usr/bin/env python3
"""
Comprehensive ASIN extraction test for various email formats
"""
import re

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

def test_real_email_formats():
    """Test with realistic email subject and content formats"""
    
    # Realistic email examples based on common discount alert formats
    test_emails = [
        {
            'subject': '[Distill] Alert: B008XQO7WA price drop detected',
            'content': 'Price drop alert for product B008XQO7WA',
            'expected_asin': 'B008XQO7WA'
        },
        {
            'subject': 'Price Alert: Product (ASIN: B008XQO7WA) is now 30% off',
            'content': 'Your monitored product with ASIN B008XQO7WA has dropped in price',
            'expected_asin': 'B008XQO7WA'
        },
        {
            'subject': 'Deal Alert - B07XVTRJKX Available Now',
            'content': 'Check out this deal on https://amazon.com/dp/B07XVTRJKX',
            'expected_asin': 'B07XVTRJKX'
        },
        {
            'subject': 'Amazon Price Drop: ASIN B008XQO7WA',
            'content': 'ASIN: B008XQO7WA - Now available at reduced price',
            'expected_asin': 'B008XQO7WA'
        },
        {
            'subject': 'No ASIN here - just a regular email',
            'content': 'This email has no ASIN information',
            'expected_asin': None
        }
    ]
    
    # Current app patterns
    subject_pattern = r'\b(B[0-9A-Z]{9})\b'  # Updated pattern
    content_patterns = [
        r'\b(B[0-9A-Z]{9})\b',  # Any ASIN with word boundaries
        r'\(ASIN:\s*([B0-9A-Z]{10})\)',  # (ASIN: B123456789)
        r'amazon\.com/[^/]*/dp/([B0-9A-Z]{10})',  # Amazon URL
        r'ASIN[:\s]*([B0-9A-Z]{10})',  # ASIN: B123456789
    ]
    
    print("=== Testing Real Email Format ASIN Extraction ===")
    
    for i, email in enumerate(test_emails):
        print(f"\nTest {i+1}: {email['subject']}")
        print(f"Expected ASIN: {email['expected_asin']}")
        
        # Test subject extraction
        subject_match = re.search(subject_pattern, email['subject'], re.IGNORECASE)
        subject_asin = None
        if subject_match:
            potential_asin = subject_match.group(1)
            if is_valid_asin(potential_asin):
                subject_asin = potential_asin
        
        print(f"Subject extraction: {subject_asin}")
        
        # Test content extraction if subject failed
        content_asin = None
        if not subject_asin:
            for pattern in content_patterns:
                content_match = re.search(pattern, email['content'], re.IGNORECASE)
                if content_match:
                    potential_asin = content_match.group(1)
                    if is_valid_asin(potential_asin):
                        content_asin = potential_asin
                        break
        
        print(f"Content extraction: {content_asin}")
        
        final_asin = subject_asin or content_asin
        success = final_asin == email['expected_asin']
        print(f"Final ASIN: {final_asin}")
        print(f"✅ Success: {success}")

if __name__ == "__main__":
    test_real_email_formats()