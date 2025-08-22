"""
Demo Data Service

Provides demo data for development and testing
"""

from datetime import datetime, timedelta


def get_demo_data(endpoint):
    """Get demo data for a specific endpoint"""
    demo_data_map = {
        'analytics.get_orders_analytics': _get_demo_analytics(),
        'purchases.list_purchases': _get_demo_purchases(),
        'user.get_profile': _get_demo_user_profile(),
    }
    
    return demo_data_map.get(endpoint)


def _get_demo_analytics():
    """Demo analytics data"""
    return {
        'enhanced_analytics': {
            'B09V1M6SZL': {
                'current_inventory': 5,
                'product_name': 'Demo Product 1',
                'sales_velocity': 2.1
            },
            'B08DK833R3': {
                'current_inventory': 12,
                'product_name': 'Demo Product 2', 
                'sales_velocity': 1.8
            }
        },
        'summary': {
            'total_products': 25,
            'total_inventory_value': 15420.50,
            'avg_sales_velocity': 1.95
        }
    }


def _get_demo_purchases():
    """Demo purchase data"""
    return {
        'purchases': [
            {
                'id': 1,
                'asin': 'B09V1M6SZL',
                'product_name': 'Demo Product 1',
                'quantity': 10,
                'unit_cost': 15.99,
                'total_cost': 159.90,
                'status': 'pending',
                'created_at': datetime.now().isoformat()
            }
        ]
    }


def _get_demo_user_profile():
    """Demo user profile"""
    return {
        'discord_id': 'demo_user',
        'username': 'Demo User',
        'email': 'demo@example.com',
        'user_tier': 'basic',
        'user_type': 'user'
    }