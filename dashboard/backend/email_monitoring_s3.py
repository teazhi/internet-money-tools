#!/usr/bin/env python3
"""
Email Monitoring S3 Storage Manager

This module handles all email monitoring data storage in S3 instead of SQLite,
maintaining consistency with the existing architecture pattern.

S3 Structure:
- email_monitoring.json contains all email monitoring data
- Organized by user discord_id for easy access
- Includes configurations, rules, logs, and webhook settings
"""

import json
import boto3
from datetime import datetime, timedelta
import uuid
import os
from typing import Dict, List, Optional, Any

class EmailMonitoringS3Manager:
    def __init__(self):
        self.s3_client = self._get_s3_client()
        self.bucket = os.getenv('CONFIG_S3_BUCKET', 'your-config-bucket')
        self.email_monitoring_key = 'email_monitoring.json'
        self.cache = {}
        self.cache_expiry = 300  # 5 minutes
        self.cache_timestamp = None
    
    def _get_s3_client(self):
        """Get S3 client with credentials"""
        # Load .env file if not already loaded
        from dotenv import load_dotenv
        load_dotenv()
        
        return boto3.client(
            's3',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
        )
    
    def _get_empty_structure(self) -> Dict:
        """Get empty email monitoring structure"""
        return {
            "version": "1.0",
            "last_updated": datetime.now().isoformat(),
            "system_webhook": {
                "webhook_url": None,
                "description": None,
                "is_active": False,
                "created_by": None,
                "created_at": None
            },
            "service_status": {
                "last_check_run": None,
                "last_check_instance": None,
                "check_in_progress": False
            },
            "users": {}
        }
    
    def _load_data(self, force_refresh=False) -> Dict:
        """Load email monitoring data from S3 with caching"""
        current_time = datetime.now()
        
        # Check cache
        if (not force_refresh and 
            self.cache and 
            self.cache_timestamp and 
            (current_time - self.cache_timestamp).total_seconds() < self.cache_expiry):
            return self.cache
        
        try:
            response = self.s3_client.get_object(Bucket=self.bucket, Key=self.email_monitoring_key)
            data = json.loads(response['Body'].read().decode('utf-8'))
            
            # Cache the data
            self.cache = data
            self.cache_timestamp = current_time
            
            return data
            
        except self.s3_client.exceptions.NoSuchKey:
            # File doesn't exist yet, create empty structure
            print("📧 Creating new email_monitoring.json file")
            empty_data = self._get_empty_structure()
            self._save_data(empty_data)
            return empty_data
            
        except Exception as e:
            print(f"❌ Error loading email monitoring data: {e}")
            return self._get_empty_structure()
    
    def _save_data(self, data: Dict) -> bool:
        """Save email monitoring data to S3"""
        try:
            # Update timestamp
            data["last_updated"] = datetime.now().isoformat()
            
            # Save to S3
            json_data = json.dumps(data, indent=2)
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=self.email_monitoring_key,
                Body=json_data,
                ContentType='application/json'
            )
            
            # Update cache
            self.cache = data
            self.cache_timestamp = datetime.now()
            
            return True
            
        except Exception as e:
            print(f"❌ Error saving email monitoring data: {e}")
            return False
    
    def _ensure_user_structure(self, data: Dict, discord_id: str):
        """Ensure user has proper structure in data"""
        if discord_id not in data["users"]:
            data["users"][discord_id] = {
                "discord_id": discord_id,
                "email_configurations": [],
                "monitoring_rules": [],
                "activity_logs": []
            }
    
    # Email Configuration Methods
    def add_email_config(self, discord_id: str, email_config: Dict) -> bool:
        """Add or update email configuration"""
        data = self._load_data()
        self._ensure_user_structure(data, discord_id)
        
        # Find existing config or add new one
        configs = data["users"][discord_id]["email_configurations"]
        email_address = email_config.get("email_address")
        
        # Remove existing config for same email
        configs[:] = [c for c in configs if c.get("email_address") != email_address]
        
        # Add new/updated config
        email_config.update({
            "id": str(uuid.uuid4()),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        })
        
        configs.append(email_config)
        
        return self._save_data(data)
    
    def get_email_configs(self, discord_id: str) -> List[Dict]:
        """Get email configurations for a user"""
        data = self._load_data()
        return data.get("users", {}).get(discord_id, {}).get("email_configurations", [])
    
    def get_all_active_configs(self) -> List[Dict]:
        """Get all active email configurations across all users"""
        data = self._load_data()
        active_configs = []
        
        for discord_id, user_data in data.get("users", {}).items():
            for config in user_data.get("email_configurations", []):
                if config.get("is_active", False):
                    config["discord_id"] = discord_id  # Add discord_id for reference
                    active_configs.append(config)
        
        return active_configs
    
    def delete_email_config(self, discord_id: str, config_id: str) -> bool:
        """Delete an email configuration"""
        data = self._load_data()
        if discord_id not in data.get("users", {}):
            return False
        
        configs = data["users"][discord_id]["email_configurations"]
        original_count = len(configs)
        configs[:] = [c for c in configs if c.get("id") != config_id]
        
        if len(configs) < original_count:
            return self._save_data(data)
        return False
    
    # Monitoring Rules Methods
    def add_monitoring_rule(self, discord_id: str, rule: Dict) -> str:
        """Add monitoring rule and return rule ID"""
        data = self._load_data()
        self._ensure_user_structure(data, discord_id)
        
        rule_id = str(uuid.uuid4())
        rule.update({
            "id": rule_id,
            "discord_id": discord_id,
            "created_at": datetime.now().isoformat(),
            "is_active": rule.get("is_active", True)
        })
        
        data["users"][discord_id]["monitoring_rules"].append(rule)
        
        if self._save_data(data):
            return rule_id
        return None
    
    def get_monitoring_rules(self, discord_id: str, active_only: bool = True) -> List[Dict]:
        """Get monitoring rules for a user"""
        data = self._load_data()
        rules = data.get("users", {}).get(discord_id, {}).get("monitoring_rules", [])
        
        if active_only:
            rules = [r for r in rules if r.get("is_active", True)]
        
        return rules
    
    def delete_monitoring_rule(self, discord_id: str, rule_id: str) -> bool:
        """Delete a monitoring rule"""
        data = self._load_data()
        if discord_id not in data.get("users", {}):
            return False
        
        rules = data["users"][discord_id]["monitoring_rules"]
        original_count = len(rules)
        rules[:] = [r for r in rules if r.get("id") != rule_id]
        
        if len(rules) < original_count:
            return self._save_data(data)
        return False
    
    # Activity Logs Methods
    def log_email_match(self, discord_id: str, rule_id: str, email_subject: str, 
                       email_sender: str, email_date: str, webhook_sent: bool, 
                       webhook_response: str, email_body: str = "") -> bool:
        """Log email match activity"""
        data = self._load_data()
        self._ensure_user_structure(data, discord_id)
        
        log_entry = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "rule_id": rule_id,
            "email_subject": email_subject,
            "email_sender": email_sender,
            "email_date": email_date,
            "email_body": email_body[:2000] if email_body else "",  # Truncate body to 2000 chars
            "webhook_sent": webhook_sent,
            "webhook_response": webhook_response
        }
        
        # Add to logs (keep last 1000 entries per user)
        logs = data["users"][discord_id]["activity_logs"]
        logs.append(log_entry)
        
        # Trim old logs
        if len(logs) > 1000:
            logs[:] = logs[-1000:]
        
        return self._save_data(data)
    
    def get_recent_logs(self, discord_id: str, limit: int = 50) -> List[Dict]:
        """Get recent activity logs for a user"""
        data = self._load_data()
        logs = data.get("users", {}).get(discord_id, {}).get("activity_logs", [])
        
        # Sort by timestamp (newest first) and limit
        logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return logs[:limit]
    
    def get_all_recent_logs(self, limit: int = 100) -> List[Dict]:
        """Get recent activity logs across all users"""
        data = self._load_data()
        all_logs = []
        
        for discord_id, user_data in data.get("users", {}).items():
            for log in user_data.get("activity_logs", []):
                log["discord_id"] = discord_id
                all_logs.append(log)
        
        # Sort by timestamp (newest first) and limit
        all_logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return all_logs[:limit]
    
    # System Webhook Methods
    def set_system_webhook(self, webhook_url: str, description: str, created_by: str, include_body: bool = False) -> bool:
        """Set system-wide webhook configuration"""
        data = self._load_data()
        
        data["system_webhook"] = {
            "webhook_url": webhook_url,
            "description": description,
            "is_active": True,
            "created_by": created_by,
            "created_at": datetime.now().isoformat(),
            "include_body": include_body
        }
        
        return self._save_data(data)
    
    def get_system_webhook(self) -> Optional[Dict]:
        """Get system webhook configuration"""
        data = self._load_data()
        webhook = data.get("system_webhook", {})
        
        if webhook.get("is_active"):
            return webhook
        return None
    
    def delete_system_webhook(self) -> bool:
        """Delete system webhook configuration"""
        data = self._load_data()
        data["system_webhook"] = {
            "webhook_url": None,
            "description": None,
            "is_active": False,
            "created_by": None,
            "created_at": None
        }
        return self._save_data(data)
    
    # Utility Methods
    def update_last_checked(self, discord_id: str, email_address: str) -> bool:
        """Update last checked timestamp for email configuration"""
        data = self._load_data()
        if discord_id not in data.get("users", {}):
            return False
        
        configs = data["users"][discord_id]["email_configurations"]
        for config in configs:
            if config.get("email_address") == email_address:
                config["last_checked"] = datetime.now().isoformat()
                return self._save_data(data)
        
        return False
    
    def update_service_status(self, status_update: Dict) -> bool:
        """Update service status in S3"""
        data = self._load_data()
        
        if "service_status" not in data:
            data["service_status"] = {
                "last_check_run": None,
                "last_check_instance": None,
                "check_in_progress": False
            }
        
        data["service_status"].update(status_update)
        return self._save_data(data)
    
    def get_service_status(self) -> Dict:
        """Get current service status"""
        data = self._load_data()
        return data.get("service_status", {
            "last_check_run": None,
            "last_check_instance": None,
            "check_in_progress": False
        })
    
    def get_stats(self) -> Dict:
        """Get email monitoring statistics"""
        data = self._load_data()
        
        total_users = len(data.get("users", {}))
        total_configs = 0
        total_rules = 0
        active_configs = 0
        total_logs = 0
        
        for user_data in data.get("users", {}).values():
            configs = user_data.get("email_configurations", [])
            rules = user_data.get("monitoring_rules", [])
            logs = user_data.get("activity_logs", [])
            
            total_configs += len(configs)
            total_rules += len(rules)
            total_logs += len(logs)
            active_configs += len([c for c in configs if c.get("is_active")])
        
        return {
            "total_users": total_users,
            "total_configurations": total_configs,
            "active_configurations": active_configs,
            "total_rules": total_rules,
            "total_logs": total_logs,
            "system_webhook_configured": bool(data.get("system_webhook", {}).get("is_active"))
        }

# Global instance for use throughout the application
email_monitoring_manager = EmailMonitoringS3Manager()