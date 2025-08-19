"""
Test script to diagnose discount email configuration issues.
Add this as a temporary endpoint in your app.py to test in Railway.
"""

def test_discount_email_config():
    """Test function to add to app.py temporarily"""
    import os
    from datetime import datetime, timedelta
    
    results = {
        'environment': {
            'DISCOUNT_MONITOR_EMAIL': os.getenv('DISCOUNT_MONITOR_EMAIL'),
            'DISCOUNT_SENDER_EMAIL': os.getenv('DISCOUNT_SENDER_EMAIL'),
            'DISCOUNT_EMAIL_DAYS_BACK': os.getenv('DISCOUNT_EMAIL_DAYS_BACK', '7')
        },
        'checks': []
    }
    
    # Check 1: Environment variables
    if not results['environment']['DISCOUNT_MONITOR_EMAIL']:
        results['checks'].append({
            'check': 'Environment Variable',
            'status': 'FAIL',
            'message': 'DISCOUNT_MONITOR_EMAIL not set'
        })
    else:
        results['checks'].append({
            'check': 'Environment Variable',
            'status': 'PASS',
            'message': f"Monitor email: {results['environment']['DISCOUNT_MONITOR_EMAIL']}"
        })
    
    # Check 2: User exists
    monitor_email = results['environment']['DISCOUNT_MONITOR_EMAIL']
    if monitor_email:
        # You'll need to import get_users_config from your app
        users = []  # Replace with: users = get_users_config()
        user_found = False
        user_has_tokens = False
        
        for user in users:
            if user.get('email') == monitor_email:
                user_found = True
                user_has_tokens = bool(user.get('google_tokens'))
                break
        
        if user_found:
            results['checks'].append({
                'check': 'User Exists',
                'status': 'PASS',
                'message': f"User found with email {monitor_email}"
            })
            
            if user_has_tokens:
                results['checks'].append({
                    'check': 'Gmail Tokens',
                    'status': 'PASS',
                    'message': 'User has Gmail tokens'
                })
            else:
                results['checks'].append({
                    'check': 'Gmail Tokens',
                    'status': 'FAIL',
                    'message': 'User does NOT have Gmail tokens - need to link Gmail'
                })
        else:
            results['checks'].append({
                'check': 'User Exists',
                'status': 'FAIL',
                'message': f"No user found with email {monitor_email}"
            })
            results['available_users'] = [u.get('email', 'No email') for u in users]
    
    # Check 3: Date range
    try:
        days_back = int(results['environment']['DISCOUNT_EMAIL_DAYS_BACK'])
        cutoff = datetime.now() - timedelta(days=days_back)
        results['checks'].append({
            'check': 'Date Range',
            'status': 'PASS',
            'message': f"Searching emails from last {days_back} days (since {cutoff.strftime('%Y-%m-%d')})"
        })
    except:
        results['checks'].append({
            'check': 'Date Range',
            'status': 'FAIL',
            'message': 'Invalid DISCOUNT_EMAIL_DAYS_BACK value'
        })
    
    return results

# Add this endpoint to your app.py:
"""
@app.route('/api/test-discount-email', methods=['GET'])
@login_required
def test_discount_email_endpoint():
    import os
    from datetime import datetime, timedelta
    
    results = {
        'environment': {
            'DISCOUNT_MONITOR_EMAIL': os.getenv('DISCOUNT_MONITOR_EMAIL', 'Not Set'),
            'DISCOUNT_SENDER_EMAIL': os.getenv('DISCOUNT_SENDER_EMAIL', 'Not Set'),
            'DISCOUNT_EMAIL_DAYS_BACK': os.getenv('DISCOUNT_EMAIL_DAYS_BACK', '7')
        },
        'checks': []
    }
    
    # Check environment variables
    monitor_email = os.getenv('DISCOUNT_MONITOR_EMAIL')
    if not monitor_email:
        results['checks'].append({
            'check': 'Environment Variable',
            'status': 'FAIL',
            'message': 'DISCOUNT_MONITOR_EMAIL not set in Railway'
        })
        return jsonify(results), 200
    
    results['checks'].append({
        'check': 'Environment Variable',
        'status': 'PASS',
        'message': f"Monitor email: {monitor_email}"
    })
    
    # Check if user exists
    users = get_users_config()
    user_found = False
    user_has_tokens = False
    
    for user in users:
        if user.get('email') == monitor_email:
            user_found = True
            user_has_tokens = bool(user.get('google_tokens'))
            results['user_info'] = {
                'discord_id': user.get('discord_id'),
                'has_google_tokens': user_has_tokens,
                'google_linked': user.get('google_linked', False)
            }
            break
    
    if user_found:
        results['checks'].append({
            'check': 'User Exists',
            'status': 'PASS',
            'message': f"User found with email {monitor_email}"
        })
        
        if user_has_tokens:
            results['checks'].append({
                'check': 'Gmail Tokens',
                'status': 'PASS',
                'message': 'User has Gmail tokens'
            })
        else:
            results['checks'].append({
                'check': 'Gmail Tokens',
                'status': 'FAIL',
                'message': 'User does NOT have Gmail tokens - need to link Gmail in Settings'
            })
    else:
        results['checks'].append({
            'check': 'User Exists',
            'status': 'FAIL',
            'message': f"No user found with email {monitor_email}"
        })
        # Show available emails (masked for privacy)
        results['available_users'] = [
            f"{email[:3]}***{email[-10:]}" if email and len(email) > 13 else email
            for email in [u.get('email', 'No email') for u in users]
        ]
    
    return jsonify(results), 200
"""