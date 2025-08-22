"""
Input Validation Utilities

Provides comprehensive input validation for API endpoints
"""

import re
import logging
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse
from app.utils.errors import ValidationError

logger = logging.getLogger(__name__)


class Validator:
    """Input validation class with chainable methods"""
    
    def __init__(self, value: Any, field_name: str = 'field'):
        self.value = value
        self.field_name = field_name
        self.errors = []
    
    def required(self, message: str = None):
        """Validate that value is not None or empty"""
        if self.value is None or (isinstance(self.value, str) and not self.value.strip()):
            error_msg = message or f"{self.field_name} is required"
            self.errors.append(error_msg)
        return self
    
    def string(self, min_length: int = None, max_length: int = None):
        """Validate string type and length"""
        if self.value is not None:
            if not isinstance(self.value, str):
                self.errors.append(f"{self.field_name} must be a string")
            else:
                if min_length is not None and len(self.value) < min_length:
                    self.errors.append(f"{self.field_name} must be at least {min_length} characters")
                if max_length is not None and len(self.value) > max_length:
                    self.errors.append(f"{self.field_name} must be at most {max_length} characters")
        return self
    
    def integer(self, min_value: int = None, max_value: int = None):
        """Validate integer type and range"""
        if self.value is not None:
            try:
                int_value = int(self.value)
                if min_value is not None and int_value < min_value:
                    self.errors.append(f"{self.field_name} must be at least {min_value}")
                if max_value is not None and int_value > max_value:
                    self.errors.append(f"{self.field_name} must be at most {max_value}")
            except (ValueError, TypeError):
                self.errors.append(f"{self.field_name} must be a valid integer")
        return self
    
    def float_num(self, min_value: float = None, max_value: float = None):
        """Validate float type and range"""
        if self.value is not None:
            try:
                float_value = float(self.value)
                if min_value is not None and float_value < min_value:
                    self.errors.append(f"{self.field_name} must be at least {min_value}")
                if max_value is not None and float_value > max_value:
                    self.errors.append(f"{self.field_name} must be at most {max_value}")
            except (ValueError, TypeError):
                self.errors.append(f"{self.field_name} must be a valid number")
        return self
    
    def email(self):
        """Validate email format"""
        if self.value is not None:
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, str(self.value)):
                self.errors.append(f"{self.field_name} must be a valid email address")
        return self
    
    def url(self, schemes: List[str] = None):
        """Validate URL format"""
        if self.value is not None:
            if schemes is None:
                schemes = ['http', 'https']
            
            try:
                parsed = urlparse(str(self.value))
                if not parsed.scheme or not parsed.netloc:
                    self.errors.append(f"{self.field_name} must be a valid URL")
                elif parsed.scheme not in schemes:
                    self.errors.append(f"{self.field_name} must use one of these schemes: {', '.join(schemes)}")
            except Exception:
                self.errors.append(f"{self.field_name} must be a valid URL")
        return self
    
    def one_of(self, allowed_values: List[Any]):
        """Validate value is in allowed list"""
        if self.value is not None and self.value not in allowed_values:
            self.errors.append(f"{self.field_name} must be one of: {', '.join(map(str, allowed_values))}")
        return self
    
    def regex(self, pattern: str, message: str = None):
        """Validate value matches regex pattern"""
        if self.value is not None:
            if not re.match(pattern, str(self.value)):
                error_msg = message or f"{self.field_name} format is invalid"
                self.errors.append(error_msg)
        return self
    
    def discord_id(self):
        """Validate Discord ID format (snowflake)"""
        return self.regex(r'^\d{17,19}$', f"{self.field_name} must be a valid Discord ID")
    
    def asin(self):
        """Validate Amazon ASIN format"""
        return self.regex(r'^[A-Z0-9]{10}$', f"{self.field_name} must be a valid ASIN")
    
    def get_errors(self) -> List[str]:
        """Get all validation errors"""
        return self.errors
    
    def is_valid(self) -> bool:
        """Check if validation passed"""
        return len(self.errors) == 0
    
    def raise_if_invalid(self):
        """Raise ValidationError if validation failed"""
        if not self.is_valid():
            raise ValidationError(f"Validation failed: {'; '.join(self.errors)}")


def validate_field(value: Any, field_name: str) -> Validator:
    """Create a new validator for a field"""
    return Validator(value, field_name)


def validate_request_data(data: Dict[str, Any], schema: Dict[str, Dict]) -> Dict[str, Any]:
    """
    Validate request data against a schema
    
    Schema format:
    {
        'field_name': {
            'required': True,
            'type': 'string',
            'min_length': 1,
            'max_length': 255
        }
    }
    """
    errors = []
    validated_data = {}
    
    for field_name, rules in schema.items():
        value = data.get(field_name)
        validator = validate_field(value, field_name)
        
        # Check if required
        if rules.get('required', False):
            validator.required()
        
        # Skip further validation if field is None and not required
        if value is None and not rules.get('required', False):
            continue
        
        # Type validation
        field_type = rules.get('type')
        if field_type == 'string':
            validator.string(
                min_length=rules.get('min_length'),
                max_length=rules.get('max_length')
            )
        elif field_type == 'integer':
            validator.integer(
                min_value=rules.get('min_value'),
                max_value=rules.get('max_value')
            )
        elif field_type == 'float':
            validator.float_num(
                min_value=rules.get('min_value'),
                max_value=rules.get('max_value')
            )
        elif field_type == 'email':
            validator.email()
        elif field_type == 'url':
            validator.url(schemes=rules.get('schemes'))
        elif field_type == 'discord_id':
            validator.discord_id()
        elif field_type == 'asin':
            validator.asin()
        
        # Additional validations
        if 'one_of' in rules:
            validator.one_of(rules['one_of'])
        
        if 'regex' in rules:
            validator.regex(rules['regex'], rules.get('regex_message'))
        
        # Collect errors
        field_errors = validator.get_errors()
        if field_errors:
            errors.extend(field_errors)
        else:
            # Convert value if validation passed
            if field_type == 'integer' and value is not None:
                validated_data[field_name] = int(value)
            elif field_type == 'float' and value is not None:
                validated_data[field_name] = float(value)
            else:
                validated_data[field_name] = value
    
    if errors:
        raise ValidationError(f"Validation errors: {'; '.join(errors)}")
    
    return validated_data


# Common validation schemas
USER_UPDATE_SCHEMA = {
    'username': {
        'type': 'string',
        'min_length': 1,
        'max_length': 50
    },
    'email': {
        'type': 'email'
    },
    'cogs_url': {
        'type': 'url'
    },
    'google_sheet_url': {
        'type': 'url'
    },
    'user_tier': {
        'type': 'string',
        'one_of': ['basic', 'pro', 'admin']
    },
    'enable_source_links': {
        'type': 'integer',
        'one_of': [0, 1]
    }
}

PURCHASE_CREATE_SCHEMA = {
    'asin': {
        'required': True,
        'type': 'asin'
    },
    'product_name': {
        'type': 'string',
        'max_length': 255
    },
    'quantity': {
        'required': True,
        'type': 'integer',
        'min_value': 1,
        'max_value': 10000
    },
    'unit_cost': {
        'required': True,
        'type': 'float',
        'min_value': 0.01
    },
    'supplier_name': {
        'type': 'string',
        'max_length': 255
    },
    'supplier_link': {
        'type': 'url'
    },
    'notes': {
        'type': 'string',
        'max_length': 1000
    }
}