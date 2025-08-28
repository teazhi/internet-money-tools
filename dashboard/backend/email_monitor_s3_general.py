#!/usr/bin/env python3
"""
General Email Monitoring System (S3-based)

This is a completely separate email monitoring system for monitoring any type of emails.
Users can set up rules to monitor for specific emails and receive webhook notifications.
It uses unique function names to avoid conflicts with existing discount email functionality.

Key differences from existing discount email system:
- Uses monitor_* prefix for all functions  
- Separate S3 storage via email_monitoring_s3.py
- Independent Gmail API usage
- No interference with existing extract_email_content() or other functions
- Runs automatically daily to check for new emails
"""

import os
import sys
import threading
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import base64
import re
from email.header import decode_header
import requests

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from email_monitoring_s3 import email_monitoring_manager


class EmailMonitorS3:
    """General email monitoring system using S3 storage"""
    
    def __init__(self):
        self.is_running = False
        self.check_interval = 86400  # 24 hours in seconds
        self.manager = email_monitoring_manager
        
    def start(self):
        """Start the email monitoring loop"""
        print("🚀 Starting Email Monitoring Service (S3 Version)")
        print(f"Check interval: {self.check_interval // 86400} day(s)")
        
        self.is_running = True
        
        while self.is_running:
            try:
                print(f"🔄 Starting email monitoring cycle at {datetime.now()}")
                self.run_email_check_cycle()
                print(f"✅ Email monitoring cycle completed at {datetime.now()}")
                
                if self.is_running:
                    time.sleep(self.check_interval)
                    
            except Exception as e:
                print(f"❌ Error in email monitoring cycle: {e}")
                if self.is_running:
                    time.sleep(300)  # Wait 5 minutes before retrying
    
    def stop(self):
        """Stop the email monitoring service"""
        print("🛑 Stopping Email Monitoring Service...")
        self.is_running = False
    
    def run_email_check_cycle(self, send_webhooks=True):
        """Run one complete cycle of email checking"""
        try:
            # Check if we should run based on S3 status
            status = self.manager.get_service_status()
            last_run = status.get('last_check_run')
            
            # For manual checks (send_webhooks=False), always allow
            if send_webhooks and last_run:
                try:
                    last_run_time = datetime.fromisoformat(last_run.replace('Z', '+00:00'))
                    time_since_last = datetime.utcnow() - last_run_time
                    
                    # Don't run if less than 23 hours since last automated run
                    if time_since_last.total_seconds() < 82800:  # 23 hours
                        hours_until_next = (82800 - time_since_last.total_seconds()) / 3600
                        print(f"⏳ Skipping automated run - last run was {time_since_last.total_seconds()/3600:.1f} hours ago")
                        print(f"   Next automated run in {hours_until_next:.1f} hours")
                        return
                except Exception as e:
                    print(f"Error parsing last run time: {e}")
            
            # Update status to indicate check in progress
            instance_id = f"{os.getenv('RAILWAY_REPLICA_ID', 'local')}_{os.getpid()}"
            self.manager.update_service_status({
                'check_in_progress': True,
                'last_check_instance': instance_id,
                'last_check_start': datetime.utcnow().isoformat()
            })
            
            print(f"🔄 Starting email check cycle (instance: {instance_id})")
            
            try:
                # Get all active email configurations
                active_configs = self.manager.get_all_active_configs()
                print(f"Found {len(active_configs)} active email configurations")
                
                for config in active_configs:
                    try:
                        self.check_monitor_email_account(config, send_webhooks=send_webhooks)
                    except Exception as e:
                        print(f"Error checking email account {config.get('email_address', 'Unknown')}: {e}")
                
                # Update status to indicate check completed
                if send_webhooks:
                    self.manager.update_service_status({
                        'check_in_progress': False,
                        'last_check_run': datetime.utcnow().isoformat(),
                        'last_check_complete': datetime.utcnow().isoformat()
                    })
                
                print(f"✅ Email check cycle completed")
                
            except Exception as e:
                # Mark check as failed
                self.manager.update_service_status({
                    'check_in_progress': False,
                    'last_check_error': str(e),
                    'last_check_error_time': datetime.utcnow().isoformat()
                })
                raise
                
        except Exception as e:
            print(f"Error in email check cycle: {e}")
    
    def monitor_update_last_checked(self, discord_id: str, email_address: str):
        """Update last checked timestamp for email account"""
        try:
            success = self.manager.update_last_checked(discord_id, email_address)
            if success:
                print(f"✅ Updated last checked time for {email_address}")
            return success
        except Exception as e:
            print(f"Error updating last checked for {email_address}: {e}")
            return False
    
    def monitor_log_email_match(self, discord_id: str, rule_id: str, email_subject: str, 
                               email_sender: str, email_date: str, webhook_sent: bool, 
                               webhook_response: str, email_body: str = ""):
        """Log email match to S3"""
        try:
            success = self.manager.log_email_match(
                discord_id, rule_id, email_subject, email_sender, 
                email_date, webhook_sent, webhook_response, email_body
            )
            if success:
                print(f"📊 Logged email email match: {email_subject[:50]}...")
            return success
        except Exception as e:
            print(f"Error logging email email match: {e}")
            return False
    
    def monitor_decode_email_header(self, header):
        """Decode email email header safely"""
        if not header:
            return ""
        
        try:
            decoded_header = ""
            for part, encoding in decode_header(header):
                if isinstance(part, bytes):
                    decoded_header += part.decode(encoding or 'utf-8', errors='ignore')
                else:
                    decoded_header += str(part)
            return decoded_header.strip()
        except Exception as e:
            print(f"Error decoding email email header '{header}': {e}")
            return str(header) if header else ""
    
    def monitor_matches_rule(self, email_msg: Dict, rule: Dict, debug: bool = False) -> bool:
        """Check if email email matches monitoring rule"""
        try:
            subject = email_msg.get('subject', '').lower()
            sender = email_msg.get('sender', '').lower() 
            content = email_msg.get('html_content', '').lower()
            
            if debug:
                print(f"    🔍 Rule matching debug:")
                print(f"      Email subject (lowercase): '{subject}'")
                print(f"      Email sender (lowercase): '{sender}'")
                print(f"      Email content length: {len(content)} chars")
                if content:
                    print(f"      Email content preview: '{content[:100]}...'")
            
            # Check sender filter
            sender_filter = rule.get('sender_filter', '').lower().strip()
            if debug:
                print(f"      Sender filter: '{sender_filter}' (empty = match all)")
                
            if sender_filter and sender_filter not in sender:
                if debug:
                    print(f"      ❌ Sender filter failed: '{sender_filter}' not in '{sender}'")
                return False
            elif debug and sender_filter:
                print(f"      ✅ Sender filter passed: '{sender_filter}' found in '{sender}'")
            elif debug:
                print(f"      ✅ Sender filter skipped (empty)")
            
            # Check subject filter
            subject_filter = rule.get('subject_filter', '').lower().strip()
            if debug:
                print(f"      Subject filter: '{subject_filter}' (empty = match all)")
                
            if subject_filter and subject_filter not in subject:
                if debug:
                    print(f"      ❌ Subject filter failed: '{subject_filter}' not in '{subject}'")
                return False
            elif debug and subject_filter:
                print(f"      ✅ Subject filter passed: '{subject_filter}' found in '{subject}'")
            elif debug:
                print(f"      ✅ Subject filter skipped (empty)")
                
            # Check content filter
            content_filter = rule.get('content_filter', '').lower().strip()
            if debug:
                print(f"      Content filter: '{content_filter}' (empty = match all)")
                
            if content_filter and content_filter not in content:
                if debug:
                    print(f"      ❌ Content filter failed: '{content_filter}' not found in content")
                    # Show where we're looking for the content
                    if content:
                        if 'yankee' in content_filter and 'yankee' in content:
                            yankee_pos = content.find('yankee')
                            print(f"      📍 'yankee' found at position {yankee_pos}")
                            print(f"      📍 Context: '{content[max(0, yankee_pos-50):yankee_pos+50]}'")
                        if 'candle' in content_filter and 'candle' in content:
                            candle_pos = content.find('candle')
                            print(f"      📍 'candle' found at position {candle_pos}")  
                            print(f"      📍 Context: '{content[max(0, candle_pos-50):candle_pos+50]}'")
                return False
            elif debug and content_filter:
                print(f"      ✅ Content filter passed: '{content_filter}' found in content")
            elif debug:
                print(f"      ✅ Content filter skipped (empty)")
            
            if debug:
                print(f"    🎉 EMAIL MATCHES ALL RULE CONDITIONS!")
            return True
            
        except Exception as e:
            print(f"Error checking email email against rule: {e}")
            return False
    
    def monitor_send_webhook(self, webhook_url: str, email_data: Dict, discord_id: str = None, include_body: bool = False) -> tuple[bool, str]:
        """Send email notification to webhook with Discord user ping"""
        try:
            fields = [
                {"name": "Subject", "value": email_data.get('subject', 'N/A')[:1024], "inline": False},
                {"name": "From", "value": email_data.get('sender', 'N/A')[:1024], "inline": True},
                {"name": "Date", "value": email_data.get('date', 'N/A')[:1024], "inline": True},
            ]
            
            # Add body field if enabled
            if include_body and email_data.get('body'):
                body_text = email_data.get('body', '')
                # Clean HTML and truncate to Discord's field limit (1024 chars)
                import re
                clean_body = re.sub(r'<[^>]+>', '', body_text)  # Remove HTML tags
                clean_body = clean_body.strip()
                if len(clean_body) > 1024:
                    clean_body = clean_body[:1021] + "..."
                fields.append({"name": "Body", "value": clean_body, "inline": False})
            
            # Create content with user ping if discord_id is provided
            content = ""
            if discord_id:
                content = f"<@{discord_id}>"
            
            payload = {
                "content": content,
                "embeds": [{
                    "title": "🔔 Email Alert",
                    "color": 0x00ff00,
                    "fields": fields,
                    "timestamp": datetime.utcnow().isoformat()
                }]
            }
            
            response = requests.post(webhook_url, json=payload, timeout=10)
            
            if response.status_code == 204:
                return True, "Webhook sent successfully"
            else:
                return False, f"Webhook failed with status {response.status_code}: {response.text}"
                
        except Exception as e:
            return False, f"Webhook error: {str(e)}"
    
    def check_monitor_email_account(self, config: Dict, send_webhooks=True):
        """Check a email email account for new messages"""
        try:
            discord_id = config['discord_id']
            email_address = config['email_address']
            auth_type = config.get('auth_type', 'imap')
            
            print(f"Checking email email: {email_address} using {auth_type}")
            
            if auth_type == 'oauth':
                self.check_monitor_email_account_oauth(
                    discord_id=discord_id,
                    email_address=email_address,
                    access_token=config.get('oauth_access_token'),
                    refresh_token=config.get('oauth_refresh_token'),
                    token_expires_at=config.get('oauth_token_expires_at'),
                    last_checked=config.get('last_checked'),
                    send_webhooks=send_webhooks
                )
            else:  # imap
                self.check_monitor_email_account_imap(
                    discord_id=discord_id,
                    email_address=email_address,
                    imap_server=config.get('imap_server'),
                    imap_port=config.get('imap_port'),
                    username=config.get('username'),
                    password=config.get('password_encrypted'),
                    last_checked=config.get('last_checked'),
                    send_webhooks=send_webhooks
                )
                
        except Exception as e:
            print(f"Error checking email email account: {e}")
    
    def check_monitor_email_account_oauth(self, discord_id: str, email_address: str, 
                                        access_token: str, refresh_token: str, 
                                        token_expires_at: str, last_checked: Optional[str],
                                        send_webhooks: bool = True):
        """Check email email account using Gmail OAuth"""
        try:
            if not access_token:
                print(f"❌ No access token for {email_address}")
                return
            
            # Check if token needs refresh
            if token_expires_at:
                try:
                    expires_at = datetime.fromisoformat(token_expires_at.replace('Z', '+00:00'))
                    if datetime.utcnow() >= expires_at - timedelta(minutes=5):
                        print(f"🔄 Refreshing token for {email_address}")
                        new_token = self.monitor_refresh_oauth_token(refresh_token)
                        if new_token:
                            access_token = new_token['access_token']
                            # Update token in S3
                            self.manager.update_oauth_tokens(
                                discord_id, email_address, 
                                new_token['access_token'],
                                refresh_token,
                                new_token.get('expires_at')
                            )
                        else:
                            print(f"❌ Failed to refresh token for {email_address}")
                            return
                except Exception as e:
                    print(f"Error checking token expiry: {e}")
            
            # Get monitoring rules for this user first
            rules = self.manager.get_monitoring_rules(discord_id)
            if not rules:
                print(f"No email monitoring rules configured for user {discord_id}")
                self.monitor_update_last_checked(discord_id, email_address)
                return
            
            print(f"🔍 DEBUG: Found {len(rules)} rules for user {discord_id}")
            for i, rule in enumerate(rules):
                print(f"  Rule {i+1}: '{rule.get('rule_name', 'Unknown')}'")
                print(f"    - Sender filter: '{rule.get('sender_filter', '')}'")
                print(f"    - Subject filter: '{rule.get('subject_filter', '')}'")
                print(f"    - Content filter: '{rule.get('content_filter', '')}'")
                print(f"    - Is active: {rule.get('is_active', True)}")
            
            # Always check only the past day for daily runs
            cutoff_date = datetime.utcnow() - timedelta(days=1)
            
            # Build targeted search queries based on rules
            all_messages = []
            matched_count = 0
            
            for rule in rules:
                if not rule.get('is_active', True):
                    print(f"⚠️  Skipping inactive rule: {rule.get('rule_name', 'Unknown')}")
                    continue
                
                # Build Gmail search query for this rule
                query_parts = [f'after:{cutoff_date.strftime("%Y/%m/%d")}']
                
                # Add sender filter if specified
                sender_filter = rule.get('sender_filter', '').strip()
                if sender_filter:
                    query_parts.append(f'from:"{sender_filter}"')
                
                # Add subject filter if specified
                subject_filter = rule.get('subject_filter', '').strip()
                if subject_filter:
                    query_parts.append(f'subject:"{subject_filter}"')
                
                # Note: Gmail API doesn't support body content search in the same way
                # Content filter will still need to be checked after fetching
                
                query = ' '.join(query_parts)
                print(f"🔍 Gmail API search query for rule '{rule.get('rule_name')}': {query}")
                
                # Search Gmail for this rule
                search_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages"
                headers = {"Authorization": f"Bearer {access_token}"}
                params = {"q": query, "maxResults": 50}
                
                response = requests.get(search_url, headers=headers, params=params)
                
                if not response.ok:
                    print(f"Error searching Gmail messages for rule '{rule.get('rule_name')}': {response.status_code} {response.text}")
                    continue
                
                search_results = response.json()
                messages = search_results.get('messages', [])
                
                print(f"Found {len(messages)} messages matching rule '{rule.get('rule_name')}'")
                
                if not messages:
                    continue
                
                # Process each message for this specific rule
                rule_processed_count = 0
                for message in messages:
                    try:
                        message_id = message['id']
                        rule_processed_count += 1
                        
                        # Check if we already processed this message (avoid duplicates across rules)
                        if message_id in [msg.get('message_id') for msg in all_messages]:
                            continue
                        
                        # Get full message details
                        message_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}"
                        msg_response = requests.get(message_url, headers=headers)
                        
                        if not msg_response.ok:
                            print(f"❌ Failed to get message {message_id}: {msg_response.status_code}")
                            continue
                            
                        email_data = msg_response.json()
                        
                        # Extract email details
                        headers_list = email_data.get('payload', {}).get('headers', [])
                        subject = None
                        sender = None
                        date = None
                        
                        for header in headers_list:
                            name = header.get('name', '').lower()
                            value = header.get('value', '')
                            
                            if name == 'subject':
                                subject = self.monitor_decode_email_header(value)
                            elif name == 'from':
                                sender = self.monitor_decode_email_header(value)
                            elif name == 'date':
                                date = value
                        
                        if not subject:
                            print(f"⚠️  Skipping message {message_id}: No subject found")
                            continue
                            
                        # Extract email content (only if rule has content filter)
                        html_content = ""
                        if rule.get('content_filter', '').strip():
                            html_content = self.monitor_extract_email_content(email_data.get('payload', {}))
                        
                        email_msg = {
                            'subject': subject,
                            'sender': sender,
                            'date': date,
                            'html_content': html_content or "",
                            'message_id': message_id
                        }
                        
                        # Debug first few emails in detail
                        if rule_processed_count <= 2:
                            print(f"🔍 DEBUG Email {rule_processed_count} for rule '{rule.get('rule_name')}':")
                            print(f"  Message ID: {message_id}")
                            print(f"  Subject: '{subject}'")
                            print(f"  From: '{sender}'")
                            print(f"  Date: '{date}'")
                            if html_content:
                                content_preview = html_content[:200].replace('\n', ' ').replace('\r', ' ')
                                print(f"  Content preview: '{content_preview}...'")
                        
                        # Check against this specific rule (content filter only, since Gmail already filtered sender/subject)
                        content_filter = rule.get('content_filter', '').strip()
                        content_matches = True
                        
                        if content_filter and html_content:
                            content_matches = content_filter.lower() in html_content.lower()
                            if rule_processed_count <= 2:
                                print(f"  Content filter '{content_filter}': {'✅ PASS' if content_matches else '❌ FAIL'}")
                        elif content_filter and not html_content:
                            content_matches = False
                            if rule_processed_count <= 2:
                                print(f"  Content filter '{content_filter}': ❌ FAIL (no content)")
                        
                        if content_matches:
                            matched_count += 1
                            
                            print(f"📧 Email matched rule '{rule.get('rule_name', 'Unknown')}':")
                            print(f"   Subject: {subject}")
                            print(f"   From: {sender}")
                            
                            # Add to processed messages to avoid duplicates
                            all_messages.append(email_msg)
                            
                            # Send webhook notification (only if enabled)
                            webhook_sent = False
                            webhook_response = ""
                            
                            if send_webhooks:
                                webhook_config = self.manager.get_system_webhook()
                                if webhook_config and webhook_config.get('is_active'):
                                    webhook_url = webhook_config['webhook_url']
                                    include_body = webhook_config.get('include_body', False)
                                    
                                    webhook_sent, webhook_response = self.monitor_send_webhook(webhook_url, {
                                        'subject': subject,
                                        'sender': sender,
                                        'date': date,
                                        'body': html_content if html_content else "No content"
                                    }, discord_id, include_body)
                                    
                                    if webhook_sent:
                                        print(f"✅ Webhook sent for email")
                                    else:
                                        print(f"❌ Webhook failed: {webhook_response}")
                            else:
                                print(f"🔇 Webhook skipped (manual check mode)")
                                webhook_response = "Skipped (manual check)"
                            
                            # Log the match
                            self.monitor_log_email_match(
                                discord_id, rule['id'], subject, sender, 
                                date, webhook_sent, webhook_response, 
                                html_content if html_content else ""
                            )
                        
                    except Exception as e:
                        print(f"Error processing email message: {e}")
            
            print(f"✅ Processed {len(all_messages)} unique messages across {len(rules)} rules, {matched_count} matches found")
            
            # Update last checked timestamp
            self.monitor_update_last_checked(discord_id, email_address)
            
        except Exception as e:
            print(f"Error in email OAuth email check: {e}")
    
    def monitor_extract_email_content(self, payload: Dict) -> Optional[str]:
        """Extract HTML content from Gmail message payload for email monitoring"""
        try:
            # Check if this part has HTML content
            if payload.get('mimeType') == 'text/html':
                body_data = payload.get('body', {}).get('data')
                if body_data:
                    # Decode base64 URL-safe encoding
                    decoded = base64.urlsafe_b64decode(body_data + '===').decode('utf-8')
                    return decoded
            
            # Check multipart content
            parts = payload.get('parts', [])
            for part in parts:
                result = self.monitor_extract_email_content(part)
                if result:
                    return result
            
            # Check if body has data directly (plain text fallback)
            body_data = payload.get('body', {}).get('data')
            if body_data and payload.get('mimeType') == 'text/plain':
                decoded = base64.urlsafe_b64decode(body_data + '===').decode('utf-8')
                return decoded
                
            return None
        except Exception as e:
            print(f"Error extracting email email content: {e}")
            return None
    
    def check_monitor_email_account_imap(self, discord_id: str, email_address: str,
                                       imap_server: str, imap_port: int, username: str,
                                       password_encrypted: str, last_checked: Optional[str],
                                       send_webhooks: bool = True):
        """Check email email account using IMAP"""
        try:
            import imaplib
            import email
            from cryptography.fernet import Fernet
            
            # Load encryption key
            encryption_key = os.getenv('EMAIL_ENCRYPTION_KEY')
            if not encryption_key:
                # Generate a consistent key for development
                encryption_key = base64.urlsafe_b64encode(b'development_key_32_chars_long!').decode()
                print("⚠️  Warning: Using auto-generated encryption key for email email. Set EMAIL_ENCRYPTION_KEY environment variable for production.")
            
            cipher = Fernet(encryption_key)
            
            # Decrypt password
            password = cipher.decrypt(password_encrypted.encode()).decode()
            
            # Connect to IMAP server
            mail = imaplib.IMAP4_SSL(imap_server, imap_port)
            mail.login(username, password)
            mail.select('inbox')
            
            # Always check only the past day for daily runs
            cutoff_date = datetime.utcnow() - timedelta(days=1)
            
            # Search for emails from past day
            date_str = cutoff_date.strftime('%d-%b-%Y')
            result, messages = mail.search(None, f'SINCE "{date_str}"')
            
            if result != 'OK' or not messages[0]:
                print(f"No new email emails found via IMAP for {email_address}")
                mail.logout()
                self.monitor_update_last_checked(discord_id, email_address)
                return
            
            message_ids = messages[0].split()
            print(f"Found {len(message_ids)} messages for email IMAP processing")
            
            # Get monitoring rules
            rules = self.manager.get_monitoring_rules(discord_id)
            if not rules:
                print(f"No email monitoring rules configured for user {discord_id}")
                mail.logout()
                self.monitor_update_last_checked(discord_id, email_address)
                return
            
            matched_count = 0
            
            # Check each message
            for message_id in message_ids[-50:]:  # Limit to most recent 50
                try:
                    result, msg_data = mail.fetch(message_id, '(RFC822)')
                    if result != 'OK':
                        continue
                    
                    email_msg_raw = email.message_from_bytes(msg_data[0][1])
                    
                    # Extract email details
                    subject = self.monitor_decode_email_header(email_msg_raw.get('Subject', ''))
                    sender = self.monitor_decode_email_header(email_msg_raw.get('From', ''))
                    date = email_msg_raw.get('Date', '')
                    
                    # Extract HTML content
                    html_content = ""
                    if email_msg_raw.is_multipart():
                        for part in email_msg_raw.walk():
                            if part.get_content_type() == "text/html":
                                charset = part.get_content_charset() or 'utf-8'
                                html_content = part.get_payload(decode=True).decode(charset, errors='ignore')
                                break
                    else:
                        if email_msg_raw.get_content_type() == "text/html":
                            charset = email_msg_raw.get_content_charset() or 'utf-8'
                            html_content = email_msg_raw.get_payload(decode=True).decode(charset, errors='ignore')
                    
                    email_msg = {
                        'subject': subject,
                        'sender': sender,
                        'date': date,
                        'html_content': html_content
                    }
                    
                    # Check against rules
                    for rule in rules:
                        if not rule.get('is_active', True):
                            continue
                            
                        if self.monitor_matches_rule(email_msg, rule):
                            matched_count += 1
                            
                            print(f"📧 Email email matched rule '{rule.get('rule_name', 'Unknown')}' via IMAP:")
                            print(f"   Subject: {subject}")
                            print(f"   From: {sender}")
                            
                            # Send webhook (only if enabled)
                            webhook_sent = False
                            webhook_response = ""
                            
                            if send_webhooks:
                                webhook_config = self.manager.get_system_webhook()
                                if webhook_config and webhook_config.get('is_active'):
                                    webhook_url = webhook_config['webhook_url']
                                    include_body = webhook_config.get('include_body', False)
                                    
                                    webhook_sent, webhook_response = self.monitor_send_webhook(webhook_url, {
                                        'subject': subject,
                                        'sender': sender,
                                        'date': date,
                                        'body': html_content if html_content else "No content"
                                    }, discord_id, include_body)
                            else:
                                print(f"🔇 Webhook skipped (manual check mode)")
                                webhook_response = "Skipped (manual check)"
                            
                            # Log the match
                            self.monitor_log_email_match(
                                discord_id, rule['id'], subject, sender,
                                date, webhook_sent, webhook_response,
                                html_content if html_content else ""
                            )
                        
                except Exception as e:
                    print(f"Error processing email IMAP message: {e}")
            
            mail.logout()
            print(f"✅ IMAP: Processed {len(message_ids)} messages, {matched_count} email matches")
            self.monitor_update_last_checked(discord_id, email_address)
            
        except Exception as e:
            print(f"Error in email IMAP email check: {e}")
    
    def monitor_refresh_oauth_token(self, refresh_token: str) -> Optional[Dict]:
        """Refresh OAuth token for email email monitoring"""
        try:
            google_client_id = os.getenv('GOOGLE_CLIENT_ID')
            google_client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
            
            if not google_client_id or not google_client_secret:
                print("❌ Missing Google OAuth credentials for email monitoring")
                return None
            
            token_data = {
                'client_id': google_client_id,
                'client_secret': google_client_secret,
                'refresh_token': refresh_token,
                'grant_type': 'refresh_token'
            }
            
            response = requests.post('https://oauth2.googleapis.com/token', data=token_data)
            
            if response.ok:
                tokens = response.json()
                access_token = tokens.get('access_token')
                expires_in = tokens.get('expires_in', 3600)
                expires_at = (datetime.utcnow() + timedelta(seconds=expires_in)).isoformat()
                
                return {
                    'access_token': access_token,
                    'expires_at': expires_at
                }
            else:
                print(f"❌ Failed to refresh email OAuth token: {response.text}")
                return None
                
        except Exception as e:
            print(f"Error refreshing email OAuth token: {e}")
            return None


def create_yankee_candle_rule(discord_id: str) -> Optional[str]:
    """Create a Yankee Candle email monitoring rule"""
    try:
        rule = {
            'rule_name': 'Yankee Candle Alert',
            'sender_filter': '',  # Empty to match any sender
            'subject_filter': '',  # Empty to match any subject
            'content_filter': 'yankee candle',  # Look for Yankee Candle in content
            'is_active': True
        }
        
        rule_id = email_monitoring_manager.add_monitoring_rule(discord_id, rule)
        
        if rule_id:
            print(f"✅ Created Yankee Candle email rule for discord_id: {discord_id}")
            return rule_id
        else:
            print(f"❌ Failed to create Yankee Candle email rule")
            return None
            
    except Exception as e:
        print(f"Error creating Yankee Candle email rule: {e}")
        return None


if __name__ == "__main__":
    # Test the email email monitor
    monitor = EmailEmailMonitorS3()
    print("Email Email Monitor S3 - Test Mode")
    print("Press Ctrl+C to stop")
    
    try:
        monitor.start()
    except KeyboardInterrupt:
        print("\\nStopping email email monitor...")
        monitor.stop()