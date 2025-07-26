import requests
import pandas as pd
from io import StringIO
from datetime import datetime, date, timedelta
import json
import os
import math
import numpy as np
from typing import Dict, Optional, List, Tuple

# Default URLs removed for security - users must configure their own URLs
ORDERS_REPORT_URL = None
STOCK_REPORT_URL = None
YESTERDAY_SALES_FILE = "yesterday_sales.json"

class EnhancedOrdersAnalysis:
    def __init__(self, orders_url: Optional[str] = None, stock_url: Optional[str] = None):
        if not orders_url or not stock_url:
            raise ValueError("Both orders_url and stock_url must be provided. No default URLs available.")
        self.orders_url = orders_url
        self.stock_url = stock_url
        
        # Test numpy import and warn if not available
        try:
            import numpy as np
            self.has_numpy = True
        except ImportError:
            print("Warning: numpy not available, some enhanced analytics features may be limited")
            self.has_numpy = False

    def download_csv(self, url: str) -> pd.DataFrame:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        df = pd.read_csv(StringIO(response.text))
        return df

    def get_orders_for_date_range(self, df: pd.DataFrame, start_date: date, end_date: date) -> pd.DataFrame:
        """Get orders for a date range instead of just single date"""
        date_columns = [col for col in df.columns if 'date' in col.lower() or 'time' in col.lower()]
        if not date_columns:
            return df
        
        date_col = date_columns[0]
        if date_col == 'PurchaseDate(UTC)':
            df[date_col] = pd.to_datetime(df[date_col], format="%m/%d/%Y %I:%M:%S %p", errors='coerce')
        else:
            df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
        
        # Filter by date range
        mask = (df[date_col].dt.date >= start_date) & (df[date_col].dt.date <= end_date)
        filtered_df = df[mask]
        
        # Filter by order status
        status_col = None
        for col in df.columns:
            if col.lower().replace(' ', '') == 'orderstatus':
                status_col = col
                break
        
        if status_col:
            filtered_df = filtered_df[filtered_df[status_col].isin(['Shipped', 'Unshipped'])]
        
        return filtered_df

    def get_orders_for_date(self, df: pd.DataFrame, for_date: date) -> pd.DataFrame:
        """Get orders for a specific date"""
        return self.get_orders_for_date_range(df, for_date, for_date)

    def asin_sales_count(self, orders_df: pd.DataFrame) -> Dict[str, int]:
        """Count sales by ASIN"""
        product_col = None
        for col in orders_df.columns:
            if 'product' in col.lower() or 'asin' in col.lower():
                product_col = col
                break
        if not product_col:
            raise ValueError("Products column not found in CSV.")
        return orders_df[product_col].value_counts().to_dict()

    def calculate_enhanced_velocity(self, asin: str, orders_df: pd.DataFrame, target_date: date) -> Dict:
        """Calculate enhanced multi-period velocity with trend analysis"""
        periods = [7, 14, 30, 60, 90]
        velocity_data = {}
        
        for period in periods:
            start_date = target_date - timedelta(days=period-1)
            period_orders = self.get_orders_for_date_range(orders_df, start_date, target_date)
            period_sales = self.asin_sales_count(period_orders)
            daily_avg = period_sales.get(asin, 0) / period
            velocity_data[f'{period}d'] = daily_avg
        
        # Calculate weighted velocity (recent performance weighted higher)
        weighted_velocity = (
            velocity_data['7d'] * 0.4 +
            velocity_data['14d'] * 0.25 +
            velocity_data['30d'] * 0.2 +
            velocity_data['60d'] * 0.1 +
            velocity_data['90d'] * 0.05
        )
        
        # Ensure no NaN/Inf values
        if not isinstance(weighted_velocity, (int, float)) or weighted_velocity != weighted_velocity:  # NaN check
            weighted_velocity = 0.0
        
        # Trend analysis with safety checks
        recent_velocity = (velocity_data['7d'] + velocity_data['14d']) / 2
        historical_velocity = (velocity_data['60d'] + velocity_data['90d']) / 2
        
        # Ensure no NaN/Inf values in trend calculation
        if historical_velocity > 0 and recent_velocity >= 0:
            trend_factor = recent_velocity / historical_velocity
        else:
            trend_factor = 1.0
            
        # Clamp trend_factor to reasonable bounds to prevent extreme values
        trend_factor = max(0.0, min(10.0, trend_factor))
        
        # Determine trend direction
        if trend_factor > 1.2:
            trend_direction = 'accelerating'
        elif trend_factor < 0.8:
            trend_direction = 'declining'
        else:
            trend_direction = 'stable'
        
        # Calculate confidence score based on data consistency
        velocities = [velocity_data[key] for key in velocity_data if velocity_data[key] > 0]
        if len(velocities) > 1 and self.has_numpy:
            std_dev = np.std(velocities)
            mean_velocity = np.mean(velocities)
            confidence = max(0, min(1, 1 - (std_dev / mean_velocity) if mean_velocity > 0 else 0))
        elif len(velocities) > 1:
            # Fallback calculation without numpy
            mean_velocity = sum(velocities) / len(velocities)
            variance = sum((x - mean_velocity) ** 2 for x in velocities) / len(velocities)
            std_dev = variance ** 0.5
            confidence = max(0, min(1, 1 - (std_dev / mean_velocity) if mean_velocity > 0 else 0))
        else:
            confidence = 0.5
        
        return {
            'current_velocity': velocity_data['7d'],
            'weighted_velocity': weighted_velocity,
            'trend_factor': trend_factor,
            'trend_direction': trend_direction,
            'confidence': confidence,
            'period_data': velocity_data
        }

    def get_days_left_value(self, stock_record: dict):
        """Helper function to get days left value handling column name variations"""
        for key in stock_record.keys():
            if 'days' in key.lower() and 'stock' in key.lower() and 'left' in key.lower():
                return stock_record.get(key, 'Unknown')
        return 'Unknown'

    def calculate_seasonality_factor(self, target_date: date) -> float:
        """Calculate seasonal adjustment factor based on date"""
        month = target_date.month
        
        # Amazon seasonality patterns (rough estimates)
        seasonality_multipliers = {
            1: 0.85,   # January - post-holiday drop
            2: 0.90,   # February - slow
            3: 0.95,   # March - recovery
            4: 1.0,    # April - normal
            5: 1.0,    # May - normal  
            6: 0.95,   # June - slight dip
            7: 0.90,   # July - summer slowdown
            8: 0.95,   # August - back to school prep
            9: 1.05,   # September - back to school
            10: 1.15,  # October - holiday prep
            11: 1.4,   # November - Black Friday/Cyber Monday
            12: 1.25   # December - Christmas
        }
        
        return seasonality_multipliers.get(month, 1.0)

    def get_priority_score(self, asin: str, velocity_data: Dict, stock_info: Dict, current_sales: int) -> Dict:
        """Calculate priority score for restocking decisions"""
        if not stock_info:
            return {'score': 0, 'category': 'no_data', 'reasoning': 'No stock data available'}
        
        try:
            current_stock = float(stock_info.get('FBA/FBM Stock', 0))
            # Handle column name variations with spaces
            days_left_key = None
            for key in stock_info.keys():
                if 'days' in key.lower() and 'stock' in key.lower() and 'left' in key.lower():
                    days_left_key = key
                    break
            days_left = float(stock_info.get(days_left_key, 9999)) if days_left_key else 9999
        except (ValueError, TypeError):
            current_stock = 0
            days_left = 9999
        
        # For products with 0 stock, calculate urgency based on velocity and stock level
        velocity = velocity_data.get('weighted_velocity', 0)
        if current_stock <= 0:
            # Zero stock = maximum urgency regardless of days_left calculation
            urgency = 1.0
        elif current_stock <= velocity * 3:  # Less than 3 days worth of stock
            urgency = 1.0
        elif current_stock <= velocity * 7:  # Less than 7 days worth of stock
            urgency = 0.8
        elif days_left <= 3:
            urgency = 1.0
        elif days_left <= 7:
            urgency = 0.8
        elif days_left <= 14:
            urgency = 0.6
        elif days_left <= 30:
            urgency = 0.3
        else:
            urgency = 0.1
        
        # Calculate opportunity (velocity × trend factor × seasonality)
        velocity = velocity_data.get('weighted_velocity', 0)
        trend_factor = velocity_data.get('trend_factor', 1.0)
        seasonality = self.calculate_seasonality_factor(date.today())
        
        opportunity = velocity * trend_factor * seasonality
        
        # Combined priority score
        priority_score = urgency * (1 + opportunity)
        
        # Only generate recommendations for products with velocity > 0
        if velocity <= 0:
            category = 'no_velocity'
            emoji = '⏸️'
        # Determine category - Special handling for zero stock products
        elif current_stock <= 0 and velocity > 0:
            # Zero stock with any velocity should be critical
            if opportunity >= 1.0:
                category = 'critical_high_velocity'
                emoji = '🚨'
            else:
                category = 'critical_low_velocity'
                emoji = '🔴'
        elif urgency >= 0.8 and opportunity >= 1.0:
            category = 'critical_high_velocity'
            emoji = '🚨'
        elif urgency >= 0.8:
            category = 'critical_low_velocity'  
            emoji = '🔴'
        elif urgency >= 0.6 and opportunity >= 1.0:
            category = 'warning_high_velocity'
            emoji = '🚀'
        elif urgency >= 0.6:
            category = 'warning_moderate'
            emoji = '🟡'
        elif opportunity >= 2.0:
            category = 'opportunity_high_velocity'
            emoji = '⚡'
        elif urgency >= 0.3 or opportunity >= 0.5:
            category = 'monitor'
            emoji = '📊'
        else:
            category = 'low_priority'
            emoji = '⏸️'
        
        # Generate reasoning
        reasoning_parts = []
        if current_stock <= 0:
            reasoning_parts.append("OUT OF STOCK")
        else:
            reasoning_parts.append(f"{days_left:.1f} days stock remaining")
        reasoning_parts.append(f"{velocity:.1f} daily velocity")
        
        if trend_factor > 1.2:
            reasoning_parts.append(f"accelerating trend (+{(trend_factor-1)*100:.0f}%)")
        elif trend_factor < 0.8:
            reasoning_parts.append(f"declining trend ({(trend_factor-1)*100:.0f}%)")
        
        if seasonality > 1.1:
            reasoning_parts.append(f"high season (+{(seasonality-1)*100:.0f}%)")
        elif seasonality < 0.9:
            reasoning_parts.append(f"low season ({(seasonality-1)*100:.0f}%)")
        
        reasoning = f"{emoji} " + ", ".join(reasoning_parts)
        
        return {
            'score': priority_score,
            'category': category,
            'urgency': urgency,
            'opportunity': opportunity,
            'reasoning': reasoning,
            'emoji': emoji
        }

    def calculate_optimal_restock_quantity(self, asin: str, velocity_data: Dict, stock_info: Dict, lead_time_days: int = 30) -> Dict:
        """Calculate optimal restock quantity with dynamic factors"""
        if not stock_info or not velocity_data:
            return {'suggested_quantity': 0, 'reasoning': 'Insufficient data'}
        
        try:
            current_stock = float(stock_info.get('FBA/FBM Stock', 0))
        except (ValueError, TypeError):
            current_stock = 0
        
        # Base velocity with trend adjustment
        base_velocity = velocity_data.get('weighted_velocity', 0)
        trend_factor = velocity_data.get('trend_factor', 1.0)
        seasonality = self.calculate_seasonality_factor(date.today())
        
        # Adjusted daily velocity
        adjusted_velocity = base_velocity * trend_factor * seasonality
        
        # Safety stock calculation (dynamic based on variability)
        confidence = velocity_data.get('confidence', 0.5)
        if confidence > 0.8:
            safety_days = 7  # High confidence, less safety stock
        elif confidence > 0.6:
            safety_days = 14  # Medium confidence
        else:
            safety_days = 21  # Low confidence, more safety stock
        
        # Calculate total needed inventory
        total_needed = adjusted_velocity * (lead_time_days + safety_days)
        
        # Subtract current stock to get reorder quantity
        suggested_quantity = max(0, total_needed - current_stock)
        
        # Round to reasonable quantities
        if suggested_quantity < 10:
            suggested_quantity = math.ceil(suggested_quantity)
        else:
            suggested_quantity = math.ceil(suggested_quantity / 5) * 5  # Round to nearest 5
        
        # Calculate estimated coverage
        total_after_restock = current_stock + suggested_quantity
        estimated_coverage = total_after_restock / adjusted_velocity if adjusted_velocity > 0 else 999
        
        # Generate reasoning
        reasoning_parts = [
            f"Base velocity: {base_velocity:.1f}/day",
            f"Lead time: {lead_time_days} days",
            f"Safety buffer: {safety_days} days"
        ]
        
        if abs(trend_factor - 1.0) > 0.1:
            reasoning_parts.append(f"Trend adjustment: {trend_factor:.1f}x")
        
        if abs(seasonality - 1.0) > 0.1:
            reasoning_parts.append(f"Seasonal adjustment: {seasonality:.1f}x")
        
        reasoning = ", ".join(reasoning_parts)
        
        return {
            'suggested_quantity': int(suggested_quantity),
            'current_stock': current_stock,
            'adjusted_velocity': adjusted_velocity,
            'estimated_coverage_days': round(estimated_coverage, 1),
            'safety_days': safety_days,
            'reasoning': reasoning,
            'lead_time_days': lead_time_days,
            'confidence': confidence
        }

    def get_stock_info(self, stock_df: pd.DataFrame) -> Dict[str, dict]:
        """Extract stock information from stock report"""
        asin_col = None
        for col in stock_df.columns:
            if col.strip().upper() == 'ASIN':
                asin_col = col
                break
        if not asin_col:
            raise ValueError("ASIN column not found in stock report.")
        
        stock_info = {}
        for _, row in stock_df.iterrows():
            asin = str(row[asin_col])
            stock_info[asin] = row.to_dict()
        return stock_info

    def load_yesterday_sales(self) -> Dict[str, int]:
        """Load previous sales data for comparison"""
        if os.path.exists(YESTERDAY_SALES_FILE):
            with open(YESTERDAY_SALES_FILE, 'r') as f:
                return json.load(f)
        return {}

    def save_today_sales_as_yesterday(self, today_sales: Dict[str, int]):
        """Save current sales data for future comparison"""
        with open(YESTERDAY_SALES_FILE, 'w') as f:
            json.dump(today_sales, f)

    def analyze(self, for_date: date, prev_date: Optional[date] = None) -> dict:
        """Main analysis function with enhanced logic"""
        # Download and process orders data
        orders_df = self.download_csv(self.orders_url)
        today_orders = self.get_orders_for_date(orders_df, for_date)
        today_sales = self.asin_sales_count(today_orders)

        # Download stock report
        stock_df = self.download_csv(self.stock_url)
        stock_info = self.get_stock_info(stock_df)

        # Load historical sales for comparison
        if prev_date is None:
            prev_date = for_date - timedelta(days=1)
        yesterday_sales = self.load_yesterday_sales()

        # Enhanced analytics for each ASIN
        enhanced_analytics = {}
        restock_alerts = {}
        critical_alerts = []
        
        for asin in set(list(today_sales.keys()) + list(stock_info.keys())):
            if asin not in stock_info:
                continue
                
            # Calculate enhanced velocity
            velocity_data = self.calculate_enhanced_velocity(asin, orders_df, for_date)
            
            # Get priority score
            current_sales = today_sales.get(asin, 0)
            priority_data = self.get_priority_score(asin, velocity_data, stock_info[asin], current_sales)
            
            # Calculate optimal restock quantity
            restock_data = self.calculate_optimal_restock_quantity(asin, velocity_data, stock_info[asin])
            
            # Combine all data
            enhanced_analytics[asin] = {
                'current_sales': current_sales,
                'velocity': velocity_data,
                'priority': priority_data,
                'restock': restock_data,
                'stock_info': stock_info[asin],
                'product_name': stock_info[asin].get('Title', f'Product {asin}')
            }
            
            # Generate alerts for high priority items (only products with velocity > 0)
            alert_categories = [
                'critical_high_velocity', 
                'critical_low_velocity', 
                'warning_high_velocity',
                'warning_moderate',
                'opportunity_high_velocity',
                'monitor'  # Include monitor category for better coverage
            ]
            # Only include products with velocity > 0 in alerts
            if priority_data['category'] in alert_categories and velocity_data.get('weighted_velocity', 0) > 0:
                alert = {
                    'asin': asin,
                    'product_name': stock_info[asin].get('Title', f'Product {asin}'),
                    'category': priority_data['category'],
                    'priority_score': priority_data['score'],
                    'current_stock': restock_data['current_stock'],
                    'days_left': self.get_days_left_value(stock_info[asin]),
                    'suggested_quantity': restock_data['suggested_quantity'],
                    'velocity': velocity_data['weighted_velocity'],
                    'trend': velocity_data['trend_direction'],
                    'reasoning': priority_data['reasoning'],
                    'emoji': priority_data['emoji']
                }
                restock_alerts[asin] = alert
                
                if priority_data['category'].startswith('critical'):
                    critical_alerts.append(alert)

        # Legacy velocity calculation for backward compatibility
        velocity = {}
        for asin, today_count in today_sales.items():
            yest_count = yesterday_sales.get(asin, 0)
            change = today_count - yest_count
            pct = (change / yest_count * 100) if yest_count else (100 if today_count else 0)
            velocity[asin] = {"today": today_count, "yesterday": yest_count, "change": change, "pct": pct}

        # Legacy analysis for backward compatibility
        low_stock = {}
        restock_priority = {}
        stockout_30d = {}
        
        for asin, sales in today_sales.items():
            stock = stock_info.get(asin)
            if not stock:
                continue
                
            try:
                days_left = float(stock.get('Days of stock left', 9999))
            except:
                days_left = 9999
                
            running_out = str(stock.get('Running out of stock', '')).strip().upper()
            
            if days_left < 7 or running_out in ("SOON", "YES"):
                low_stock[asin] = {
                    "days_left": days_left,
                    "running_out": running_out,
                    "reorder_qty": stock.get('Recommended quantity for reordering', None),
                    "time_to_reorder": stock.get('Time to reorder', ''),
                    "title": stock.get('Title', '')
                }
                
            if (sales >= 3 or velocity.get(asin, {}).get("pct", 0) > 20) and (days_left < 7 or running_out in ("SOON", "YES")):
                restock_priority[asin] = low_stock.get(asin, {})
                
            # 30-day stockout calculation
            try:
                current_stock = float(stock.get('FBA/FBM Stock', 0))
                days_left_calc = current_stock / max(sales, 1)
                if days_left_calc < 30:
                    suggested_reorder = max(0, int((30 * sales) - current_stock))
                    stockout_30d[asin] = {
                        "title": stock.get('Title', ''),
                        "sold_today": sales,
                        "current_stock": current_stock,
                        "days_left": round(days_left_calc, 1),
                        "suggested_reorder": suggested_reorder
                    }
            except:
                pass

        return {
            # Enhanced analytics (new)
            "enhanced_analytics": enhanced_analytics,
            "restock_alerts": restock_alerts,
            "critical_alerts": critical_alerts,
            "total_products_analyzed": len(enhanced_analytics),
            "high_priority_count": len([a for a in enhanced_analytics.values() if a['priority']['category'] in ['critical_high_velocity', 'critical_low_velocity', 'warning_high_velocity']]),
            
            # Legacy data (for backward compatibility)
            "today_sales": today_sales,
            "velocity": velocity,
            "low_stock": low_stock,
            "restock_priority": restock_priority,
            "stock_info": stock_info,
            "orders_df": today_orders,
            "stockout_30d": stockout_30d,
        }

class BasicOrdersAnalysis:
    """Simple fallback analytics without enhanced features"""
    def __init__(self, orders_url: Optional[str] = None, stock_url: Optional[str] = None):
        self.orders_url = orders_url
        self.stock_url = stock_url

    def analyze(self, for_date: date) -> dict:
        """Basic analytics that always returns a valid structure"""
        return {
            'today_sales': {},
            'velocity': {},
            'low_stock': {},
            'restock_priority': {},
            'stockout_30d': {},
            'enhanced_analytics': {},
            'restock_alerts': {},
            'critical_alerts': [],
            'total_products_analyzed': 0,
            'high_priority_count': 0,
            'basic_mode': True,
            'message': 'Analytics data could not be loaded. Please check your report URLs in Settings.'
        }

# Maintain backward compatibility
class OrdersAnalysis(EnhancedOrdersAnalysis):
    """Backward compatible class name"""
    def __init__(self, orders_url: Optional[str] = None, stock_url: Optional[str] = None):
        try:
            super().__init__(orders_url, stock_url)
        except Exception as e:
            print(f"Enhanced analytics initialization failed: {e}")
            # Fall back to basic implementation
            self.orders_url = orders_url
            self.stock_url = stock_url
            self.is_fallback = True
    
    def analyze(self, for_date: date) -> dict:
        if hasattr(self, 'is_fallback') and self.is_fallback:
            return BasicOrdersAnalysis(self.orders_url, self.stock_url).analyze(for_date)
        else:
            return super().analyze(for_date)