#!/usr/bin/env python3
"""
Update app.py to use S3-based email monitoring endpoints
"""

import re

# Read the current app.py
with open('app.py', 'r') as f:
    content = f.read()

# First, add the import for S3 manager at the top of the file
import_section = """
# Email Monitoring S3 Manager
from email_monitoring_s3 import email_monitoring_manager
"""

# Find where to insert the import (after other imports)
import_pattern = r'(from email_monitor import EmailMonitor.*\n)'
content = re.sub(import_pattern, r'\1' + import_section + '\n', content)

# Now we need to replace all the email monitoring endpoints
# Let's find the start and end of email monitoring section

# Find the first email monitoring route
start_pattern = r'@app.route\(\'/api/email-monitoring/config\', methods=\[\'GET\'\]\)'
start_match = re.search(start_pattern, content)

if start_match:
    start_pos = start_match.start()
    
    # Find the end of email monitoring section (before the next non-email-monitoring route)
    # Look for the service control endpoint as the last one
    end_pattern = r'(@app\.route\(\'/api/email-monitoring/service-control\'.*?\n(?:.*?\n)*?return jsonify\({.*?}\).*?\n)'
    end_match = re.search(end_pattern, content[start_pos:], re.DOTALL)
    
    if end_match:
        end_pos = start_pos + end_match.end()
        
        # Extract the section to replace
        old_section = content[start_pos:end_pos]
        
        # Create new S3-based endpoints
        new_section = '''@app.route('/api/email-monitoring/config', methods=['GET'])
@login_required
def get_email_monitoring_config():
    """Get user's email monitoring configuration from S3"""
    try:
        discord_id = session['discord_id']
        
        if not has_feature_access(discord_id, 'email_monitoring'):
            return jsonify({'error': 'Access denied to email monitoring feature'}), 403
        
        configs = email_monitoring_manager.get_email_configs(discord_id)
        
        formatted_configs = []
        for config in configs:
            formatted_config = {
                'id': config.get('id'),
                'email_address': config.get('email_address'),
                'auth_type': config.get('auth_type', 'imap'),
                'is_active': config.get('is_active', True),
                'last_checked': config.get('last_checked')
            }
            
            if config.get('auth_type') != 'oauth':
                formatted_config.update({
                    'imap_server': config.get('imap_server'),
                    'imap_port': config.get('imap_port'),
                    'username': config.get('username')
                })
            
            formatted_configs.append(formatted_config)
        
        print(f"🔍 GET email configs for discord_id {discord_id}: found {len(formatted_configs)} configs")
        for config in formatted_configs:
            print(f"  - {config['email_address']} (auth_type: {config['auth_type']})")
        
        return jsonify({'configs': formatted_configs})
        
    except Exception as e:
        print(f"Error fetching email monitoring config: {e}")
        return jsonify({'error': 'Failed to fetch email monitoring configuration'}), 500

@app.route('/api/email-monitoring/rules', methods=['GET'])
@login_required
def get_email_monitoring_rules():
    """Get user's email monitoring rules from S3"""
    try:
        discord_id = session['discord_id']
        
        if not has_feature_access(discord_id, 'email_monitoring'):
            return jsonify({'error': 'Access denied to email monitoring feature'}), 403
        
        rules = email_monitoring_manager.get_monitoring_rules(discord_id, active_only=False)
        
        formatted_rules = []
        for rule in rules:
            formatted_rule = {
                'id': rule.get('id'),
                'rule_name': rule.get('rule_name'),
                'sender_filter': rule.get('sender_filter'),
                'subject_filter': rule.get('subject_filter'),
                'content_filter': rule.get('content_filter'),
                'is_active': rule.get('is_active', True)
            }
            formatted_rules.append(formatted_rule)
        
        return jsonify({'rules': formatted_rules})
        
    except Exception as e:
        print(f"Error fetching email monitoring rules: {e}")
        return jsonify({'error': 'Failed to fetch email monitoring rules'}), 500

@app.route('/api/email-monitoring/rules', methods=['POST'])
@login_required
def create_email_monitoring_rule():
    """Create email monitoring rule in S3"""
    try:
        discord_id = session['discord_id']
        
        if not has_feature_access(discord_id, 'email_monitoring'):
            return jsonify({'error': 'Access denied to email monitoring feature'}), 403
        
        data = request.get_json()
        
        rule = {
            'rule_name': data.get('rule_name'),
            'sender_filter': data.get('sender_filter'),
            'subject_filter': data.get('subject_filter'),
            'content_filter': data.get('content_filter'),
            'is_active': data.get('is_active', True)
        }
        
        rule_id = email_monitoring_manager.add_monitoring_rule(discord_id, rule)
        
        if rule_id:
            return jsonify({'message': 'Email monitoring rule created successfully', 'rule_id': rule_id})
        else:
            return jsonify({'error': 'Failed to create rule'}), 500
        
    except Exception as e:
        print(f"Error creating email monitoring rule: {e}")
        return jsonify({'error': 'Failed to create email monitoring rule'}), 500

@app.route('/api/email-monitoring/rules/<rule_id>', methods=['DELETE'])
@login_required
def delete_email_monitoring_rule(rule_id):
    """Delete email monitoring rule from S3"""
    try:
        discord_id = session['discord_id']
        
        if not has_feature_access(discord_id, 'email_monitoring'):
            return jsonify({'error': 'Access denied to email monitoring feature'}), 403
        
        success = email_monitoring_manager.delete_monitoring_rule(discord_id, rule_id)
        
        if success:
            return jsonify({'message': 'Email monitoring rule deleted successfully'})
        else:
            return jsonify({'error': 'Rule not found'}), 404
            
    except Exception as e:
        print(f"Error deleting email monitoring rule: {e}")
        return jsonify({'error': 'Failed to delete email monitoring rule'}), 500

@app.route('/api/email-monitoring/status', methods=['GET'])
@login_required
def get_email_monitoring_status():
    """Get email monitoring status from S3"""
    try:
        discord_id = session['discord_id']
        
        if not has_feature_access(discord_id, 'email_monitoring'):
            return jsonify({'error': 'Access denied to email monitoring feature'}), 403
        
        configs = email_monitoring_manager.get_email_configs(discord_id)
        rules = email_monitoring_manager.get_monitoring_rules(discord_id)
        recent_logs = email_monitoring_manager.get_recent_logs(discord_id, 10)
        
        stats = email_monitoring_manager.get_stats()
        
        status = {
            'service_running': True,  # S3 version is always "running"
            'active_configs': len([c for c in configs if c.get('is_active')]),
            'active_rules': len([r for r in rules if r.get('is_active')]),
            'recent_logs': [
                {
                    'timestamp': log.get('timestamp'),
                    'subject': log.get('email_subject'),
                    'sender': log.get('email_sender'),
                    'webhook_sent': log.get('webhook_sent')
                }
                for log in recent_logs
            ],
            'system_stats': stats
        }
        
        return jsonify(status)
        
    except Exception as e:
        print(f"Error getting email monitoring status: {e}")
        return jsonify({'error': 'Failed to get email monitoring status'}), 500

@app.route('/api/email-monitoring/oauth-url', methods=['GET'])
@login_required
def get_email_monitoring_oauth_url():
    """Get Gmail OAuth authorization URL for email monitoring"""
    try:
        state = str(uuid.uuid4())
        session['email_oauth_state'] = state
        
        auth_url = (
            f"https://accounts.google.com/o/oauth2/v2/auth?"
            f"client_id={GOOGLE_CLIENT_ID}&"
            f"redirect_uri={urllib.parse.quote(GOOGLE_REDIRECT_URI)}&"
            f"scope=https://www.googleapis.com/auth/gmail.readonly&"
            f"response_type=code&"
            f"access_type=offline&"
            f"prompt=consent&"
            f"state=email_monitoring_{state}"
        )
        
        return jsonify({
            'auth_url': auth_url,
            'state': state
        })
    except Exception as e:
        print(f"Error generating OAuth URL: {e}")
        return jsonify({'error': 'Failed to generate authorization URL'}), 500

@app.route('/api/email-monitoring/oauth-setup', methods=['POST'])
@login_required
def setup_email_monitoring_oauth():
    """Complete OAuth setup for email monitoring and save to S3"""
    try:
        data = request.get_json()
        email_address = data.get('email_address')
        auth_code = data.get('auth_code')
        
        if not email_address or not auth_code:
            return jsonify({'error': 'Email address and authorization code are required'}), 400
            
        token_data = {
            'client_id': GOOGLE_CLIENT_ID,
            'client_secret': GOOGLE_CLIENT_SECRET,
            'code': auth_code,
            'grant_type': 'authorization_code',
            'redirect_uri': GOOGLE_REDIRECT_URI
        }
        
        token_response = requests.post('https://oauth2.googleapis.com/token', data=token_data)
        
        if not token_response.ok:
            print(f"Token exchange failed: {token_response.text}")
            return jsonify({'error': 'Failed to exchange authorization code for tokens'}), 400
            
        tokens = token_response.json()
        access_token = tokens.get('access_token')
        refresh_token = tokens.get('refresh_token')
        expires_in = tokens.get('expires_in', 3600)
        
        if not access_token:
            return jsonify({'error': 'No access token received'}), 400
            
        expires_at = (datetime.now() + timedelta(seconds=expires_in)).isoformat()
        
        discord_id = session['discord_id']
        
        email_config = {
            'email_address': email_address,
            'auth_type': 'oauth',
            'oauth_access_token': access_token,
            'oauth_refresh_token': refresh_token,
            'oauth_token_expires_at': expires_at,
            'is_active': True
        }
        
        success = email_monitoring_manager.add_email_config(discord_id, email_config)
        
        if success:
            print(f"✅ OAuth setup completed for {email_address} (discord_id: {discord_id})")
            return jsonify({'message': 'OAuth setup completed successfully'})
        else:
            return jsonify({'error': 'Failed to save email configuration'}), 500
        
    except Exception as e:
        print(f"Error setting up OAuth: {e}")
        return jsonify({'error': f'Failed to setup OAuth: {str(e)}'}), 500

@app.route('/api/email-monitoring/quick-setup', methods=['POST'])
@login_required
def email_monitoring_quick_setup():
    """Quick setup for Yankee Candle refund monitoring using S3"""
    try:
        discord_id = session['discord_id']
        
        if not has_feature_access(discord_id, 'email_monitoring'):
            return jsonify({'error': 'Access denied to email monitoring feature'}), 403
        
        from email_monitor_s3 import create_yankee_candle_rule
        rule_id = create_yankee_candle_rule(discord_id)
        
        if rule_id:
            return jsonify({'message': 'Yankee Candle refund monitoring rule created successfully'})
        else:
            return jsonify({'error': 'Failed to create Yankee Candle rule'}), 500
            
    except Exception as e:
        print(f"Error in quick setup: {e}")
        return jsonify({'error': 'Failed to create Yankee Candle rule'}), 500

@app.route('/api/email-monitoring/check-now', methods=['POST'])
@login_required
def trigger_email_check():
    """Trigger manual email check using S3 data"""
    try:
        discord_id = session['discord_id']
        
        if not has_feature_access(discord_id, 'email_monitoring'):
            return jsonify({'error': 'Access denied to email monitoring feature'}), 403
        
        from email_monitor_s3 import EmailMonitorS3
        monitor = EmailMonitorS3()
        
        configs = email_monitoring_manager.get_email_configs(discord_id)
        active_configs = [c for c in configs if c.get('is_active')]
        
        if not active_configs:
            return jsonify({'message': 'No active email configurations found'}), 200
        
        for config in active_configs:
            config['discord_id'] = discord_id
            monitor.check_email_account(config)
        
        return jsonify({'message': f'Email check completed for {len(active_configs)} configurations'})
        
    except Exception as e:
        print(f"Error triggering email check: {e}")
        return jsonify({'error': 'Failed to trigger email check'}), 500

@app.route('/api/admin/email-monitoring/webhook', methods=['GET'])
@admin_required
def get_email_monitoring_webhook():
    """Get system-wide email monitoring webhook configuration from S3"""
    try:
        webhook_config = email_monitoring_manager.get_system_webhook()
        
        if webhook_config:
            return jsonify({
                'configured': True,
                'config': {
                    'webhook_url': webhook_config['webhook_url'],
                    'description': webhook_config['description'],
                    'is_active': webhook_config['is_active'],
                    'created_at': webhook_config['created_at'],
                    'created_by': webhook_config['created_by']
                }
            })
        else:
            return jsonify({'configured': False})
            
    except Exception as e:
        print(f"Error getting email monitoring webhook: {e}")
        return jsonify({'error': 'Failed to get webhook configuration'}), 500

@app.route('/api/admin/email-monitoring/webhook', methods=['POST'])
@admin_required
def set_email_monitoring_webhook():
    """Set system-wide email monitoring webhook configuration in S3"""
    try:
        data = request.get_json()
        webhook_url = data.get('webhook_url')
        description = data.get('description', 'Default Webhook')
        
        if not webhook_url:
            return jsonify({'error': 'Webhook URL is required'}), 400
        
        success = email_monitoring_manager.set_system_webhook(
            webhook_url, description, session.get('discord_id', 'admin')
        )
        
        if success:
            print(f"✅ Webhook saved successfully: {webhook_url}")
            return jsonify({'message': 'Webhook configuration saved successfully'})
        else:
            return jsonify({'error': 'Failed to save webhook'}), 500
            
    except Exception as e:
        print(f"Error setting email monitoring webhook: {e}")
        return jsonify({'error': 'Failed to save webhook configuration'}), 500

@app.route('/api/admin/email-monitoring/webhook', methods=['DELETE'])
@admin_required
def delete_email_monitoring_webhook():
    """Delete the system-wide email monitoring webhook configuration from S3"""
    try:
        success = email_monitoring_manager.delete_system_webhook()
        
        if success:
            return jsonify({'message': 'Webhook configuration deleted successfully'})
        else:
            return jsonify({'error': 'Failed to delete webhook'}), 500
            
    except Exception as e:
        print(f"Error deleting email monitoring webhook: {e}")
        return jsonify({'error': 'Failed to delete webhook configuration'}), 500

@app.route('/api/admin/email-monitoring/webhook/test', methods=['POST'])
@admin_required
def test_email_monitoring_webhook():
    """Test the email monitoring webhook from S3 config"""
    try:
        data = request.get_json()
        test_webhook_url = data.get('webhook_url')
        
        if not test_webhook_url:
            webhook_config = email_monitoring_manager.get_system_webhook()
            if not webhook_config:
                return jsonify({'error': 'No webhook configured'}), 400
            test_webhook_url = webhook_config['webhook_url']
        
        from email_monitor_s3 import EmailMonitorS3
        monitor = EmailMonitorS3()
        
        test_email_data = {
            'sender': 'test@example.com',
            'subject': 'Test Email Notification',
            'date': datetime.now().isoformat(),
            'body': 'This is a test email to verify your webhook configuration is working correctly.'
        }
        
        webhook_sent, webhook_response = monitor.send_webhook(test_webhook_url, test_email_data)
        
        if webhook_sent:
            return jsonify({'message': 'Webhook test successful'})
        else:
            return jsonify({'error': f'Webhook test failed: {webhook_response}'}), 400
            
    except Exception as e:
        print(f"Error testing webhook: {e}")
        return jsonify({'error': 'Failed to test webhook'}), 500

@app.route('/api/email-monitoring/service-control', methods=['POST'])
@admin_required
def control_email_monitoring_service():
    """Admin endpoint to start/stop the email monitoring service"""
    try:
        data = request.get_json()
        action = data.get('action')  # 'start' or 'stop'
        
        if action == 'start':
            if email_monitor_thread and email_monitor_thread.is_alive():
                return jsonify({'message': 'Email monitoring service is already running'})'''
        
        # Replace the old section with the new one
        content = content[:start_pos] + new_section + content[end_pos:]
        
        print(f"✅ Replaced email monitoring endpoints (from position {start_pos} to {end_pos})")
    else:
        print("❌ Could not find end pattern")
else:
    print("❌ Could not find start pattern")

# Save the updated app.py
with open('app.py', 'w') as f:
    f.write(content)

print("✅ Updated app.py with S3-based email monitoring endpoints")