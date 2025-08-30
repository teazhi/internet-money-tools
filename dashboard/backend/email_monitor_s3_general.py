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
        
        self.is_running = True
        
        while self.is_running:
            try:
                self.run_email_check_cycle()
                
                if self.is_running:
                    time.sleep(self.check_interval)
                    
            except Exception as e:
                if self.is_running:
                    time.sleep(300)  # Wait 5 minutes before retrying
    
    def stop(self):
        """Stop the email monitoring service"""
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
            
            
            try:
                # Get all active email configurations
                active_configs = self.manager.get_all_active_configs()
                
                for config in active_configs:
                    try:
                        self.check_monitor_email_account(config, send_webhooks=send_webhooks)
                    except Exception as e:
                        pass
                    
                # Update status to indicate check completed
                if send_webhooks:
                    self.manager.update_service_status({
                        'check_in_progress': False,
                        'last_check_run': datetime.utcnow().isoformat(),
                        'last_check_complete': datetime.utcnow().isoformat()
                    })
                
                
            except Exception as e:
                # Mark check as failed
                self.manager.update_service_status({
                    'check_in_progress': False,
                    'last_check_error': str(e),
                    'last_check_error_time': datetime.utcnow().isoformat()
                })
                raise
                
        except Exception as e:
            pass
    
    def monitor_update_last_checked(self, discord_id: str, email_address: str):
        """Update last checked timestamp for email account"""
        try:
            success = self.manager.update_last_checked(discord_id, email_address)
            if success:
                pass
            return success
        except Exception as e:
            pass
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
                pass
            return success
        except Exception as e:
            pass
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
            pass
            return str(header) if header else ""
    
    def monitor_matches_rule(self, email_msg: Dict, rule: Dict, debug: bool = False) -> bool:
        """Check if email email matches monitoring rule"""
        try:
            subject = email_msg.get('subject', '').lower()
            sender = email_msg.get('sender', '').lower() 
            content = email_msg.get('html_content', '').lower()
            
            
            # Check sender filter
            sender_filter = rule.get('sender_filter', '').lower().strip()
                
            if sender_filter and sender_filter not in sender:
                return False
            
            # Check subject filter
            subject_filter = rule.get('subject_filter', '').lower().strip()
                
            if subject_filter and subject_filter not in subject:
                return False
                
            # Check content filter
            content_filter = rule.get('content_filter', '').lower().strip()
                
            if content_filter and content_filter not in content:
                return False
            
            return True
            
        except Exception as e:
            pass
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
                return
            
            # Check if token needs refresh
            if token_expires_at:
                try:
                    expires_at = datetime.fromisoformat(token_expires_at.replace('Z', '+00:00'))
                    if datetime.utcnow() >= expires_at - timedelta(minutes=5):
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
                            return
                except Exception as e:
                    print(f"Error checking token expiry: {e}")
            
            # Get monitoring rules for this user first
            rules = self.manager.get_monitoring_rules(discord_id)
            if not rules:
                self.monitor_update_last_checked(discord_id, email_address)
                return
            
            # Always check only the past day for daily runs
            cutoff_date = datetime.utcnow() - timedelta(days=1)
            
            # Build targeted search queries based on rules
            all_messages = []
            matched_count = 0
            
            for rule in rules:
                if not rule.get('is_active', True):
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
                        
                        
                        # Check against this specific rule (content filter only, since Gmail already filtered sender/subject)
                        content_filter = rule.get('content_filter', '').strip()
                        content_matches = True
                        
                        if content_filter and html_content:
                            content_matches = content_filter.lower() in html_content.lower()
                        elif content_filter and not html_content:
                            content_matches = False
                        
                        if content_matches:
                            matched_count += 1
                            
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
                            else:
                                webhook_response = "Skipped (manual check)"
                            
                            # Log the match
                            self.monitor_log_email_match(
                                discord_id, rule['id'], subject, sender, 
                                date, webhook_sent, webhook_response, 
                                html_content if html_content else ""
                            )
                        
                    except Exception as e:
                        pass
            
            
            # Update last checked timestamp
            self.monitor_update_last_checked(discord_id, email_address)
            
        except Exception as e:
            pass
    
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
                mail.logout()
                self.monitor_update_last_checked(discord_id, email_address)
                return
            
            message_ids = messages[0].split()
            
            # Get monitoring rules
            rules = self.manager.get_monitoring_rules(discord_id)
            if not rules:
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
            self.monitor_update_last_checked(discord_id, email_address)
            
        except Exception as e:
            print(f"Error in email IMAP email check: {e}")
    
    def monitor_refresh_oauth_token(self, refresh_token: str) -> Optional[Dict]:
        """Refresh OAuth token for email email monitoring"""
        try:
            google_client_id = os.getenv('GOOGLE_CLIENT_ID')
            google_client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
            
            if not google_client_id or not google_client_secret:
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
            return rule_id
        else:
            return None
            
    except Exception as e:
        print(f"Error creating Yankee Candle email rule: {e}")
        return None


if __name__ == "__main__":
    # Test the email email monitor
    monitor = EmailMonitorS3()
    
    try:
        monitor.start()
    except KeyboardInterrupt:
        monitor.stop()