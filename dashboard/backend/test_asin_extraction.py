#!/usr/bin/env python3
"""
Test ASIN extraction patterns independently
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
        'BXT5V5XPNW',  # Seen in Stumptown coffee emails
        'BOOPSS7GDF',  # Another false positive pattern
        'BJZN9KFZ3K',  # Another false positive pattern  
        'BGFZD1HP12',  # Another false positive pattern
    ]
    
    if asin in false_positives:
        return False
        
    return True

def test_asin_patterns():
    """Test ASIN extraction patterns with sample email subjects"""
    
    # Test sample email subjects that might contain ASINs
    test_subjects = [
        "[Distill] Alert: B008XQO7WA price drop detected",
        "Price alert for (ASIN: B008XQO7WA) - 30% off",
        "Vitacost Sale: B07XVTRJKX now available",
        "Amazon deal: https://amazon.com/dp/B008XQO7WA",
        "Alert for product ASIN: B008XQO7WA",
        "[Amazon] B008XQO7WA Price Drop Alert",
        "No ASIN in this subject",
        "Product B123456789 on sale",  # Invalid ASIN
        "ASIN B008XQO7WA special offer"
    ]
    
    # Test patterns
    patterns = [
        r'\(ASIN:\s*([B0-9A-Z]{10})\)',  # Default pattern
        r'B[0-9A-Z]{9}',  # Simple ASIN pattern
        r'amazon\.com/[^/]*/dp/([B0-9A-Z]{10})',  # Amazon URL
        r'ASIN[:\s]*([B0-9A-Z]{10})',  # ASIN: format
        r'\b(B[0-9A-Z]{9})\b',  # Word boundary ASIN
    ]
    
    print("=== Testing ASIN Extraction Patterns ===")
    
    for i, subject in enumerate(test_subjects):
        print(f"\nTest {i+1}: {subject}")
        
        for j, pattern in enumerate(patterns):
            match = re.search(pattern, subject, re.IGNORECASE)
            if match:
                # Get the ASIN (either full match or first group)
                if match.groups():
                    asin = match.group(1)
                else:
                    asin = match.group(0)
                
                valid = is_valid_asin(asin)
                print(f"  Pattern {j+1}: {asin} (valid: {valid})")
            else:
                print(f"  Pattern {j+1}: No match")

if __name__ == "__main__":
    test_asin_patterns()