"""
SP-API Analytics Module
Transforms SP-API data into the format expected by the dashboard frontend
Replaces Sellerboard data processing with native Amazon SP-API data
"""

import pandas as pd
from datetime import datetime, timedelta, timezone, date
from typing import Dict, List, Any, Optional, Tuple
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

class SPAPIAnalytics:
    """Processes SP-API data into analytics format compatible with existing frontend"""
    
    def __init__(self, sp_api_client):
        """
        Initialize analytics processor
        
        Args:
            sp_api_client: SPAPIClient instance
        """
        self.client = sp_api_client
        
    def get_orders_analytics(self, target_date: date, user_timezone: str = None) -> Dict[str, Any]:
        """
        Get comprehensive orders analytics for a specific date
        
        Args:
            target_date: Date to analyze
            user_timezone: User's timezone preference
            
        Returns:
            Analytics data dictionary compatible with frontend
        """
        try:
            # Calculate date range for orders query
            start_datetime = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            end_datetime = start_datetime + timedelta(days=1)
            
            
            # Fetch orders from SP-API
            orders = self.client.get_orders(start_datetime, end_datetime)
            
            # Fetch inventory data
            inventory = self.client.get_inventory_summary()
            
            # Process data into analytics format
            analytics_data = self._process_analytics_data(orders, inventory, target_date, user_timezone)
            
            return analytics_data
            
        except Exception as e:
            logger.error(f"Failed to generate SP-API analytics: {e}")
            return self._get_fallback_analytics(target_date, str(e))
    
    def _process_analytics_data(self, orders: List[Dict], inventory: List[Dict], target_date: date, user_timezone: str) -> Dict[str, Any]:
        """Process SP-API orders and inventory into analytics format"""
        
        # Initialize analytics structure
        analytics = {
            'report_date': target_date.strftime('%Y-%m-%d'),
            'user_timezone': user_timezone,
            'is_yesterday': target_date < date.today(),
            'source': 'sp-api',
            'last_updated': datetime.now().isoformat()
        }
        
        # Process orders data
        if orders:
            orders_df = pd.DataFrame(orders)
            analytics.update(self._analyze_orders(orders_df, target_date))
        else:
            analytics.update(self._get_empty_orders_data())
        
        # Process inventory data
        if inventory:
            inventory_df = pd.DataFrame(inventory)
            analytics.update(self._analyze_inventory(inventory_df))
        else:
            analytics.update(self._get_empty_inventory_data())
        
        # Add enhanced analytics
        analytics['enhanced_analytics'] = self._create_enhanced_analytics(orders, inventory)
        
        return analytics
    
    def _analyze_orders(self, orders_df: pd.DataFrame, target_date: date) -> Dict[str, Any]:
        """Analyze orders data"""
        
        # Calculate today's sales by ASIN
        today_sales = {}
        sellerboard_orders = []
        
        for _, order in orders_df.iterrows():
            # Process each order and ensure JSON-serializable
            order_dict = order.to_dict()
            serializable_order = {}
            for key, value in order_dict.items():
                try:
                    # Convert pandas/numpy types to native Python types
                    if hasattr(value, 'item'):  # numpy scalar
                        value = value.item()
                    elif hasattr(value, 'to_pydatetime'):  # pandas timestamp
                        value = value.to_pydatetime().isoformat()
                    elif str(type(value)).startswith('<class \'pandas.'):  # other pandas types
                        value = str(value)
                    elif str(type(value)).startswith('<class \'numpy.'):  # other numpy types
                        value = str(value)
                    serializable_order[key] = value
                except Exception:
                    # If conversion fails, convert to string as fallback
                    serializable_order[key] = str(value)
            
            sellerboard_orders.append(serializable_order)
            
            # Count sales by ASIN
            if 'ASINs' in order_dict and order_dict['ASINs']:
                quantities = order_dict.get('Quantities', {})
                for asin in order_dict['ASINs']:
                    quantity = quantities.get(asin, 1)
                    today_sales[asin] = today_sales.get(asin, 0) + quantity
            elif 'ASIN' in order_dict and order_dict['ASIN']:
                # Handle single ASIN or comma-separated ASINs
                asins = order_dict['ASIN'].split(',') if ',' in order_dict['ASIN'] else [order_dict['ASIN']]
                total_quantity = order_dict.get('TotalQuantity', 1)
                quantity_per_asin = total_quantity // len(asins) if asins else 0
                
                for asin in asins:
                    asin = asin.strip()
                    if asin:
                        today_sales[asin] = today_sales.get(asin, 0) + quantity_per_asin
        
        return {
            'today_sales': today_sales,
            'sellerboard_orders': sellerboard_orders
        }
    
    def _analyze_inventory(self, inventory_df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze inventory data"""
        
        # Calculate stock levels and alerts
        low_stock = {}
        restock_priority = {}
        stockout_30d = {}
        
        for _, item in inventory_df.iterrows():
            asin = item.get('asin', '')
            if not asin:
                continue
                
            available_qty = item.get('availableQuantity', 0)
            total_qty = item.get('totalQuantity', 0)
            product_name = item.get('productName', f'Product {asin}')
            
            # Simple velocity calculation (you may want to enhance this with historical data)
            # For now, use a conservative estimate
            estimated_daily_velocity = 1  # Conservative default
            
            # Calculate days of inventory remaining
            days_left = available_qty / estimated_daily_velocity if estimated_daily_velocity > 0 else 999
            
            # Low stock threshold: less than 14 days
            if days_left < 14 and available_qty > 0:
                low_stock[asin] = {
                    'title': product_name,
                    'current_stock': available_qty,
                    'days_left': f"{int(days_left)} days",
                    'reorder_qty': max(30, int(estimated_daily_velocity * 30))  # 30 days supply
                }
            
            # Restock priority: less than 30 days
            if days_left < 30:
                restock_priority[asin] = {
                    'title': product_name,
                    'current_stock': available_qty,
                    'suggested_reorder': max(60, int(estimated_daily_velocity * 60))  # 60 days supply
                }
            
            # 30-day stockout risk: less than 30 days
            if days_left < 30:
                stockout_30d[asin] = {
                    'title': product_name,
                    'sold_today': int(estimated_daily_velocity),  # Estimated
                    'current_stock': available_qty,
                    'days_left': f"{int(days_left)} days",
                    'suggested_reorder': max(60, int(estimated_daily_velocity * 60))
                }
        
        return {
            'low_stock': low_stock,
            'restock_priority': restock_priority,
            'stockout_30d': stockout_30d
        }
    
    def _create_enhanced_analytics(self, orders: List[Dict], inventory: List[Dict]) -> Dict[str, Any]:
        """Create enhanced analytics data structure"""
        
        enhanced = {}
        
        # Create ASIN-based analytics
        inventory_map = {item.get('asin', ''): item for item in inventory}
        
        # Calculate sales velocity from orders
        sales_by_asin = defaultdict(int)
        for order in orders:
            asins = order.get('ASINs', [])
            quantities = order.get('Quantities', {})
            for asin in asins:
                sales_by_asin[asin] += quantities.get(asin, 1)
        
        # Combine with inventory data
        for asin, inventory_item in inventory_map.items():
            if not asin:
                continue
                
            daily_velocity = sales_by_asin.get(asin, 0)  # Today's sales as velocity estimate
            current_stock = inventory_item.get('availableQuantity', 0)
            
            enhanced[asin] = {
                'product_name': inventory_item.get('productName', f'Product {asin}'),
                'velocity': {
                    'daily_velocity': daily_velocity,
                    'weighted_velocity': max(daily_velocity, 0.5),  # Minimum velocity to avoid division by zero
                    'velocity_trend': 'stable'  # Would need historical data for actual trend
                },
                'restock': {
                    'current_stock': current_stock,
                    'suggested_quantity': max(30, int(max(daily_velocity, 0.5) * 30)),  # 30 days supply
                    'days_until_stockout': int(current_stock / max(daily_velocity, 0.5)) if daily_velocity > 0 else 999,
                    'restock_urgency': 'high' if current_stock / max(daily_velocity, 0.5) < 14 else 'medium' if current_stock / max(daily_velocity, 0.5) < 30 else 'low'
                },
                'priority': {
                    'category': self._calculate_priority_category(current_stock, daily_velocity),
                    'score': self._calculate_priority_score(current_stock, daily_velocity)
                },
                'inventory_details': inventory_item.get('inventoryDetails', {}),
                'sales_data': {
                    'today_sales': daily_velocity,
                    'total_quantity_sold': daily_velocity  # Would be accumulated over time with historical data
                }
            }
        
        return enhanced
    
    def _calculate_priority_category(self, current_stock: int, daily_velocity: float) -> List[str]:
        """Calculate priority category for restocking"""
        categories = []
        
        if daily_velocity > 0:
            days_left = current_stock / daily_velocity
            
            if days_left < 7:
                categories.append('critical')
            elif days_left < 14:
                categories.append('warning')
            elif days_left < 30:
                categories.append('attention')
            else:
                categories.append('normal')
        else:
            categories.append('normal')
        
        return categories
    
    def _calculate_priority_score(self, current_stock: int, daily_velocity: float) -> float:
        """Calculate numerical priority score (higher = more urgent)"""
        if daily_velocity <= 0:
            return 0.0
        
        days_left = current_stock / daily_velocity
        
        if days_left < 7:
            return 10.0
        elif days_left < 14:
            return 7.0
        elif days_left < 30:
            return 5.0
        else:
            return 1.0
    
    def _get_empty_orders_data(self) -> Dict[str, Any]:
        """Return empty orders data structure"""
        return {
            'today_sales': {},
            'sellerboard_orders': []
        }
    
    def _get_empty_inventory_data(self) -> Dict[str, Any]:
        """Return empty inventory data structure"""
        return {
            'low_stock': {},
            'restock_priority': {},
            'stockout_30d': {}
        }
    
    def _get_fallback_analytics(self, target_date: date, error_message: str) -> Dict[str, Any]:
        """Return fallback analytics data when SP-API fails"""
        return {
            'report_date': target_date.strftime('%Y-%m-%d'),
            'source': 'sp-api-fallback',
            'error': f"SP-API Error: {error_message}",
            'fallback_mode': True,
            'message': 'Unable to fetch data from Amazon SP-API. Please check your API credentials and permissions.',
            'today_sales': {},
            'sellerboard_orders': [],
            'low_stock': {},
            'restock_priority': {},
            'stockout_30d': {},
            'enhanced_analytics': {},
            'last_updated': datetime.now().isoformat()
        }

def create_sp_api_analytics(sp_api_client) -> SPAPIAnalytics:
    """
    Create SP-API analytics processor
    
    Args:
        sp_api_client: SPAPIClient instance
        
    Returns:
        SPAPIAnalytics instance
    """
    return SPAPIAnalytics(sp_api_client)