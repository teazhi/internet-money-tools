#!/usr/bin/env python3
"""
Refund Email Monitoring System (S3-based)

This is a completely separate email monitoring system specifically for refund tracking.
It uses unique function names to avoid conflicts with existing discount email functionality.

Key differences from existing discount email system:
- Uses refund_* prefix for all functions
- Separate S3 storage via email_monitoring_s3.py
- Independent Gmail API usage
- No interference with existing extract_email_content() or other functions
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


class RefundEmailMonitorS3:
    """Refund-specific email monitoring system using S3 storage"""
    
    def __init__(self):
        self.is_running = False
        self.check_interval = 86400  # 24 hours in seconds
        self.manager = email_monitoring_manager
        
    def start(self):
        """Start the refund email monitoring loop"""
        print("🚀 Starting Refund Email Monitoring Service (S3 Version)")
        print(f"Check interval: {self.check_interval // 86400} day(s)")
        
        self.is_running = True
        
        while self.is_running:
            try:
                print(f"🔄 Starting refund email monitoring cycle at {datetime.now()}")
                self.run_refund_email_check_cycle()
                print(f"✅ Refund email monitoring cycle completed at {datetime.now()}")
                
                if self.is_running:
                    time.sleep(self.check_interval)
                    
            except Exception as e:
                print(f"❌ Error in refund email monitoring cycle: {e}")
                if self.is_running:
                    time.sleep(300)  # Wait 5 minutes before retrying
    
    def stop(self):
        """Stop the refund email monitoring service"""
        print("🛑 Stopping Refund Email Monitoring Service...")
        self.is_running = False
    
    def run_refund_email_check_cycle(self):
        """Run one complete cycle of refund email checking"""
        try:
            # Get all active email configurations
            active_configs = self.manager.get_all_active_configs()
            print(f"Found {len(active_configs)} active email configurations")
            
            for config in active_configs:
                try:
                    self.check_refund_email_account(config)
                except Exception as e:
                    print(f"Error checking email account {config.get('email_address', 'Unknown')}: {e}")
                    
        except Exception as e:
            print(f"Error in refund email check cycle: {e}")
    
    def refund_update_last_checked(self, discord_id: str, email_address: str):
        """Update last checked timestamp for refund email account"""
        try:
            success = self.manager.update_last_checked(discord_id, email_address)
            if success:
                print(f"✅ Updated last checked time for {email_address}")
            return success
        except Exception as e:
            print(f"Error updating last checked for {email_address}: {e}")
            return False
    
    def refund_log_email_match(self, discord_id: str, rule_id: str, email_subject: str, 
                              email_sender: str, email_date: str, webhook_sent: bool, 
                              webhook_response: str):
        """Log refund email match to S3"""
        try:
            success = self.manager.log_email_match(
                discord_id, rule_id, email_subject, email_sender, 
                email_date, webhook_sent, webhook_response
            )
            if success:
                print(f"📊 Logged refund email match: {email_subject[:50]}...")
            return success
        except Exception as e:
            print(f"Error logging refund email match: {e}")
            return False
    
    def refund_decode_email_header(self, header):
        """Decode refund email header safely"""
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
            print(f"Error decoding refund email header '{header}': {e}")
            return str(header) if header else ""
    
    def refund_matches_rule(self, email_msg: Dict, rule: Dict) -> bool:
        """Check if refund email matches monitoring rule"""
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
            print(f"Error checking refund email against rule: {e}")
            return False
    
    def refund_send_webhook(self, webhook_url: str, email_data: Dict) -> tuple[bool, str]:
        """Send refund email notification to webhook"""
        try:
            payload = {
                "embeds": [{
                    "title": "🔔 Refund Email Alert",
                    "color": 0x00ff00,
                    "fields": [
                        {"name": "Subject", "value": email_data.get('subject', 'N/A')[:1024], "inline": False},
                        {"name": "From", "value": email_data.get('sender', 'N/A')[:1024], "inline": True},
                        {"name": "Date", "value": email_data.get('date', 'N/A')[:1024], "inline": True},
                    ],
                    "description": email_data.get('body', 'N/A')[:2048],
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
    
    def check_refund_email_account(self, config: Dict):
        """Check a refund email account for new messages"""
        try:
            discord_id = config['discord_id']
            email_address = config['email_address']
            auth_type = config.get('auth_type', 'imap')
            
            print(f"Checking refund email: {email_address} using {auth_type}")
            
            if auth_type == 'oauth':
                self.check_refund_email_account_oauth(
                    discord_id=discord_id,
                    email_address=email_address,
                    access_token=config.get('oauth_access_token'),
                    refresh_token=config.get('oauth_refresh_token'),
                    token_expires_at=config.get('oauth_token_expires_at'),
                    last_checked=config.get('last_checked')
                )
            else:  # imap
                self.check_refund_email_account_imap(
                    discord_id=discord_id,
                    email_address=email_address,
                    imap_server=config.get('imap_server'),
                    imap_port=config.get('imap_port'),
                    username=config.get('username'),
                    password=config.get('password_encrypted'),
                    last_checked=config.get('last_checked')
                )
                
        except Exception as e:
            print(f"Error checking refund email account: {e}")
    
    def check_refund_email_account_oauth(self, discord_id: str, email_address: str, 
                                        access_token: str, refresh_token: str, 
                                        token_expires_at: str, last_checked: Optional[str]):
        """Check refund email account using Gmail OAuth"""
        try:
            if not access_token:
                print(f"❌ No access token for {email_address}")
                return
            
            # Check if token needs refresh
            if token_expires_at:
                try:
                    expires_at = datetime.fromisoformat(token_expires_at.replace('Z', '+00:00'))
                    if datetime.now() >= expires_at - timedelta(minutes=5):
                        print(f"🔄 Refreshing token for {email_address}")
                        new_token = self.refund_refresh_oauth_token(refresh_token)
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
            
            # Determine date cutoff
            if last_checked:
                cutoff_date = datetime.fromisoformat(last_checked.replace('Z', '+00:00'))
            else:
                cutoff_date = datetime.now() - timedelta(days=7)  # Default 7 days back
            
            # Build search query for refunds - search ALL emails in inbox
            query = f'after:{cutoff_date.strftime("%Y/%m/%d")}'
            
            print(f"Gmail API refund search query: {query}")
            
            # Search Gmail
            search_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages"
            headers = {"Authorization": f"Bearer {access_token}"}
            params = {"q": query, "maxResults": 50}
            
            response = requests.get(search_url, headers=headers, params=params)
            
            if not response.ok:
                print(f"Error searching Gmail messages: {response.status_code} {response.text}")
                return
            
            search_results = response.json()
            messages = search_results.get('messages', [])
            
            print(f"Found {len(messages)} messages for refund monitoring")
            
            if not messages:
                print(f"No emails found in Gmail for {email_address}")
                self.refund_update_last_checked(discord_id, email_address)
                return
            
            # Get monitoring rules for this user
            rules = self.manager.get_monitoring_rules(discord_id)
            if not rules:
                print(f"No refund monitoring rules configured for user {discord_id}")
                self.refund_update_last_checked(discord_id, email_address)
                return
            
            matched_count = 0
            
            # Check each message against rules
            for message in messages:
                try:
                    message_id = message['id']
                    
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
                            subject = self.refund_decode_email_header(value)
                        elif name == 'from':
                            sender = self.refund_decode_email_header(value)
                        elif name == 'date':
                            date = value
                    
                    if not subject:
                        continue
                        
                    # Extract email content
                    html_content = self.refund_extract_email_content(email_data.get('payload', {}))
                    
                    email_msg = {
                        'subject': subject,
                        'sender': sender,
                        'date': date,
                        'html_content': html_content or "",
                        'message_id': message_id
                    }
                    
                    # Check against all active rules
                    for rule in rules:
                        if not rule.get('is_active', True):
                            continue
                            
                        if self.refund_matches_rule(email_msg, rule):
                            matched_count += 1
                            
                            print(f"📧 Refund email matched rule '{rule.get('rule_name', 'Unknown')}':")
                            print(f"   Subject: {subject}")
                            print(f"   From: {sender}")
                            
                            # Send webhook notification
                            webhook_sent = False
                            webhook_response = ""
                            
                            webhook_config = self.manager.get_system_webhook()
                            if webhook_config and webhook_config.get('is_active'):
                                webhook_url = webhook_config['webhook_url']
                                
                                webhook_sent, webhook_response = self.refund_send_webhook(webhook_url, {
                                    'subject': subject,
                                    'sender': sender,
                                    'date': date,
                                    'body': html_content[:500] if html_content else "No content"
                                })
                                
                                if webhook_sent:
                                    print(f"✅ Webhook sent for refund email")
                                else:
                                    print(f"❌ Webhook failed: {webhook_response}")
                            
                            # Log the match
                            self.refund_log_email_match(
                                discord_id, rule['id'], subject, sender, 
                                date, webhook_sent, webhook_response
                            )
                        
                except Exception as e:
                    print(f"Error processing refund email message: {e}")
            
            print(f"✅ Processed {len(messages)} messages, {matched_count} refund matches found")
            
            # Update last checked timestamp
            self.refund_update_last_checked(discord_id, email_address)
            
        except Exception as e:
            print(f"Error in refund OAuth email check: {e}")
    
    def refund_extract_email_content(self, payload: Dict) -> Optional[str]:
        """Extract HTML content from Gmail message payload for refund monitoring"""
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
                result = self.refund_extract_email_content(part)
                if result:
                    return result
            
            # Check if body has data directly (plain text fallback)
            body_data = payload.get('body', {}).get('data')
            if body_data and payload.get('mimeType') == 'text/plain':
                decoded = base64.urlsafe_b64decode(body_data + '===').decode('utf-8')
                return decoded
                
            return None
        except Exception as e:
            print(f"Error extracting refund email content: {e}")
            return None
    
    def check_refund_email_account_imap(self, discord_id: str, email_address: str,
                                       imap_server: str, imap_port: int, username: str,
                                       password_encrypted: str, last_checked: Optional[str]):
        """Check refund email account using IMAP"""
        try:
            import imaplib
            import email
            from cryptography.fernet import Fernet
            
            # Load encryption key
            encryption_key = os.getenv('EMAIL_ENCRYPTION_KEY')
            if not encryption_key:
                # Generate a consistent key for development
                encryption_key = base64.urlsafe_b64encode(b'development_key_32_chars_long!').decode()
                print("⚠️  Warning: Using auto-generated encryption key for refund email. Set EMAIL_ENCRYPTION_KEY environment variable for production.")
            
            cipher = Fernet(encryption_key)
            
            # Decrypt password
            password = cipher.decrypt(password_encrypted.encode()).decode()
            
            # Connect to IMAP server
            mail = imaplib.IMAP4_SSL(imap_server, imap_port)
            mail.login(username, password)
            mail.select('inbox')
            
            # Determine date cutoff
            if last_checked:
                cutoff_date = datetime.fromisoformat(last_checked.replace('Z', '+00:00'))
            else:
                cutoff_date = datetime.now() - timedelta(days=7)
            
            # Search for emails since last check
            date_str = cutoff_date.strftime('%d-%b-%Y')
            result, messages = mail.search(None, f'SINCE "{date_str}"')
            
            if result != 'OK' or not messages[0]:
                print(f"No new refund emails found via IMAP for {email_address}")
                mail.logout()
                self.refund_update_last_checked(discord_id, email_address)
                return
            
            message_ids = messages[0].split()
            print(f"Found {len(message_ids)} messages for refund IMAP processing")
            
            # Get monitoring rules
            rules = self.manager.get_monitoring_rules(discord_id)
            if not rules:
                print(f"No refund monitoring rules configured for user {discord_id}")
                mail.logout()
                self.refund_update_last_checked(discord_id, email_address)
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
                    subject = self.refund_decode_email_header(email_msg_raw.get('Subject', ''))
                    sender = self.refund_decode_email_header(email_msg_raw.get('From', ''))
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
                            
                        if self.refund_matches_rule(email_msg, rule):
                            matched_count += 1
                            
                            print(f"📧 Refund email matched rule '{rule.get('rule_name', 'Unknown')}' via IMAP:")
                            print(f"   Subject: {subject}")
                            print(f"   From: {sender}")
                            
                            # Send webhook
                            webhook_sent = False
                            webhook_response = ""
                            
                            webhook_config = self.manager.get_system_webhook()
                            if webhook_config and webhook_config.get('is_active'):
                                webhook_url = webhook_config['webhook_url']
                                
                                webhook_sent, webhook_response = self.refund_send_webhook(webhook_url, {
                                    'subject': subject,
                                    'sender': sender,
                                    'date': date,
                                    'body': html_content[:500] if html_content else "No content"
                                })
                            
                            # Log the match
                            self.refund_log_email_match(
                                discord_id, rule['id'], subject, sender,
                                date, webhook_sent, webhook_response
                            )
                        
                except Exception as e:
                    print(f"Error processing refund IMAP message: {e}")
            
            mail.logout()
            print(f"✅ IMAP: Processed {len(message_ids)} messages, {matched_count} refund matches")
            self.refund_update_last_checked(discord_id, email_address)
            
        except Exception as e:
            print(f"Error in refund IMAP email check: {e}")
    
    def refund_refresh_oauth_token(self, refresh_token: str) -> Optional[Dict]:
        """Refresh OAuth token for refund email monitoring"""
        try:
            google_client_id = os.getenv('GOOGLE_CLIENT_ID')
            google_client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
            
            if not google_client_id or not google_client_secret:
                print("❌ Missing Google OAuth credentials for refund monitoring")
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
                expires_at = (datetime.now() + timedelta(seconds=expires_in)).isoformat()
                
                return {
                    'access_token': access_token,
                    'expires_at': expires_at
                }
            else:
                print(f"❌ Failed to refresh refund OAuth token: {response.text}")
                return None
                
        except Exception as e:
            print(f"Error refreshing refund OAuth token: {e}")
            return None


def create_yankee_candle_refund_rule(discord_id: str) -> Optional[str]:
    """Create a Yankee Candle refund monitoring rule"""
    try:
        rule = {
            'rule_name': 'Yankee Candle Refund Alert',
            'sender_filter': '',  # Empty to match any sender
            'subject_filter': '',  # Empty to match any subject
            'content_filter': 'yankee candle',  # Look for Yankee Candle in content
            'is_active': True
        }
        
        rule_id = email_monitoring_manager.add_monitoring_rule(discord_id, rule)
        
        if rule_id:
            print(f"✅ Created Yankee Candle refund rule for discord_id: {discord_id}")
            return rule_id
        else:
            print(f"❌ Failed to create Yankee Candle refund rule")
            return None
            
    except Exception as e:
        print(f"Error creating Yankee Candle refund rule: {e}")
        return None


if __name__ == "__main__":
    # Test the refund email monitor
    monitor = RefundEmailMonitorS3()
    print("Refund Email Monitor S3 - Test Mode")
    print("Press Ctrl+C to stop")
    
    try:
        monitor.start()
    except KeyboardInterrupt:
        print("\\nStopping refund email monitor...")
        monitor.stop()