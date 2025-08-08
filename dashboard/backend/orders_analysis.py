import requests
import pandas as pd
from io import StringIO
from datetime import datetime, date, timedelta
import json
import os
import math
import numpy as np
from typing import Dict, Optional, List, Tuple
from purchase_analytics import PurchaseAnalytics

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
        
        # Initialize purchase analytics
        self.purchase_analytics = PurchaseAnalytics()
        
        # Test numpy import and warn if not available
        try:
            import numpy as np
            self.has_numpy = True
        except ImportError:
            pass  # Debug print removed
            self.has_numpy = False

    def _parse_datetime_robust(self, series: pd.Series, column_name: str) -> pd.Series:
        """Robust datetime parsing that tries multiple formats"""
        # Parsing datetime column
        
        # Common datetime formats from Sellerboard and other sources
        # PRIORITY ORDER: Most common Sellerboard formats first
        formats_to_try = [
            # Sellerboard specific formats (most common first)
            "%m/%d/%y %H:%M",        # 7/26/25 6:05 (US Sellerboard format)
            "%d/%m/%Y %H:%M:%S",     # 28/07/2025 06:21:44 (EU/International Sellerboard format)
            "%m/%d/%Y %H:%M:%S",     # 07/28/2025 14:30:45 (US with seconds)
            "%d/%m/%Y %H:%M",        # 28/07/2025 06:21 (EU without seconds)
            "%m/%d/%y %H:%M:%S",     # 7/26/25 6:05:00 (US with seconds)
            "%d/%m/%y %H:%M:%S",     # 28/07/25 06:21:44 (EU with 2-digit year)
            
            # Legacy formats for backward compatibility
            "%m/%d/%Y %I:%M:%S %p",  # 07/28/2025 02:30:45 PM (12-hour with AM/PM)
            "%d/%m/%Y %I:%M:%S %p",  # 28/07/2025 02:30:45 PM (EU with AM/PM)
            "%Y-%m-%d %H:%M:%S",     # 2025-07-28 14:30:45 (ISO-like)
            "%Y-%m-%d %I:%M:%S %p",  # 2025-07-28 02:30:45 PM
            "%m/%d/%Y",              # 07/28/2025 (date only)  
            "%Y-%m-%d",              # 2025-07-28 (ISO date)
            "%d/%m/%Y",              # 28/07/2025 (EU date only)
        ]
        
        parsed_series = None
        successful_format = None
        
        for fmt in formats_to_try:
            try:
                parsed_series = pd.to_datetime(series, format=fmt, errors='coerce')
                # Count how many values were successfully parsed
                valid_count = parsed_series.notna().sum()
                if valid_count > 0:
                    # Format parsed successfully
                    successful_format = fmt
                    break
            except Exception as e:
                continue
        
        # If no specific format worked, try pandas' flexible parsing as fallback
        if parsed_series is None or parsed_series.notna().sum() == 0:
            # All specific formats failed, trying flexible parsing
            parsed_series = pd.to_datetime(series, errors='coerce')
        
        # Log results
        final_valid_count = parsed_series.notna().sum()
        nat_count = parsed_series.isna().sum()
        
        # Final parsing results logged
        if successful_format:
            # Best format found
            pass
        
        # Show sample of unparseable values for debugging
        if nat_count > 0:
            invalid_mask = parsed_series.isna() & series.notna()
            if invalid_mask.any():
                sample_invalid = series[invalid_mask].head(3).tolist()
                # Sample unparseable values found
                pass
        
        return parsed_series

    def download_csv(self, url: str) -> pd.DataFrame:
        
        # Check if URL has required parameters
        if 'sellerboard.com' in url and 'format=csv' not in url:
            # Add CSV format if missing
            separator = '&' if '?' in url else '?'
            url = f"{url}{separator}format=csv"
        
        # Try to download with better error handling
        try:
            # Create a session to handle cookies properly
            session = requests.Session()
            
            # Add headers that might be expected by Sellerboard
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/csv,application/csv,text/plain,*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
            }
            
            # First, try to get the initial response without following redirects
            initial_response = session.get(url, timeout=30, allow_redirects=False, headers=headers)
            
            if initial_response.status_code == 302:
                # Handle redirect manually to see what's happening
                redirect_url = initial_response.headers.get('Location')
                
                # Check if the redirect URL is a download URL
                if redirect_url and 'download-report' in redirect_url:
                    pass  # Debug print removed
                    # Try to follow the redirect with the session cookies
                    response = session.get(redirect_url, timeout=30, headers=headers)
                else:
                    # Follow redirects normally
                    response = session.get(url, timeout=30, allow_redirects=True, headers=headers)
            else:
                response = initial_response
                
            pass  # Debug print removed
            
            # Check for authentication errors specifically
            if response.status_code == 401:
                pass  # Debug print removed
                pass  # Debug print removed
                pass  # Debug print removed
                pass  # Debug print removed
                pass  # Debug print removed
            
            response.raise_for_status()
            
            # Try to parse the CSV
            try:
                df = pd.read_csv(StringIO(response.text))
                pass  # Debug print removed
                return df
            except Exception as csv_error:
                pass  # Debug print removed
                pass  # Debug print removed
                raise
                
        except requests.exceptions.RequestException as e:
            pass  # Debug print removed
            if hasattr(e, 'response') and e.response is not None:
                pass  # Debug print removed
                pass  # Debug print removed
            raise

    def get_orders_for_date_range(self, df: pd.DataFrame, start_date: date, end_date: date, user_timezone: str = None) -> pd.DataFrame:
        """Get orders for a date range instead of just single date"""
        date_columns = [col for col in df.columns if 'date' in col.lower() or 'time' in col.lower()]
        if not date_columns:
            return df
        
        date_col = date_columns[0]
        if date_col == 'PurchaseDate(UTC)':
            # Try multiple datetime formats for PurchaseDate(UTC)
            df[date_col] = self._parse_datetime_robust(df[date_col], date_col)
        else:
            df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
        
        # Convert timestamps to user timezone if provided
        if user_timezone and not df[date_col].empty:
            try:
                # Assume UTC if no timezone info present, then convert to user timezone
                if df[date_col].dt.tz is None:
                    df[date_col] = df[date_col].dt.tz_localize('UTC')
                df[date_col] = df[date_col].dt.tz_convert(user_timezone)
            except Exception as e:
                pass  # Timezone conversion error
        
        # Filter by date range - convert dates to pandas datetime for comparison
        start_date_pd = pd.to_datetime(start_date)
        end_date_pd = pd.to_datetime(end_date)
        # Filter out NaT values before comparison to avoid TypeError
        valid_dates_mask = df[date_col].notna()
        date_range_mask = (df[date_col].dt.date >= start_date_pd.date()) & (df[date_col].dt.date <= end_date_pd.date())
        mask = valid_dates_mask & date_range_mask
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

    def get_orders_for_date(self, df: pd.DataFrame, for_date: date, user_timezone: str = None) -> pd.DataFrame:
        """Get orders for a specific date"""
        try:
            return self.get_orders_for_date_range(df, for_date, for_date, user_timezone)
        except Exception as e:
            if "Invalid comparison between dtype=datetime64[ns] and date" in str(e):
                pass  # Debug print removed
                pass  # Debug print removed
                pass  # Debug print removed
                pass  # Debug print removed
                # Try to find date columns
                date_columns = [col for col in df.columns if 'date' in col.lower() or 'time' in col.lower()]
                if date_columns:
                    pass  # Debug print removed
                    pass  # Debug print removed
                    pass  # Debug print removed
            raise

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

    def calculate_enhanced_velocity(self, asin: str, orders_df: pd.DataFrame, target_date: date, user_timezone: str = None) -> Dict:
        """Calculate enhanced multi-period velocity with trend analysis (optimized for 30-day Sellerboard data)"""
        # Adjusted periods for 30-day Sellerboard data limit
        periods = [3, 7, 14, 21, 30]
        velocity_data = {}
        
        try:
            for period in periods:
                start_date = target_date - timedelta(days=period-1)
                period_orders = self.get_orders_for_date_range(orders_df, start_date, target_date, user_timezone)
                period_sales = self.asin_sales_count(period_orders)
                daily_avg = period_sales.get(asin, 0) / period
                velocity_data[f'{period}d'] = daily_avg
        except Exception as e:
            if "Invalid comparison between dtype=datetime64[ns] and date" in str(e):
                pass  # Debug print removed
                pass  # Debug print removed
                pass  # Debug print removed
                pass  # Debug print removed
                pass  # Debug print removed
            raise
        
        # Calculate weighted velocity (recent performance weighted higher) - adjusted for 30-day data
        weighted_velocity = (
            velocity_data['3d'] * 0.35 +   # Very recent (3 days)
            velocity_data['7d'] * 0.3 +    # Recent (1 week)
            velocity_data['14d'] * 0.2 +   # Medium term (2 weeks)
            velocity_data['21d'] * 0.1 +   # Longer term (3 weeks)
            velocity_data['30d'] * 0.05    # Full period (1 month)
        )
        
        # Ensure no NaN/Inf values
        if not isinstance(weighted_velocity, (int, float)) or weighted_velocity != weighted_velocity:  # NaN check
            weighted_velocity = 0.0
            
        # If all historical periods are zero but we have sales today, use today's sales as baseline velocity
        if weighted_velocity == 0 and all(v == 0 for v in velocity_data.values()):
            today_orders = self.get_orders_for_date(orders_df, target_date, user_timezone)
            today_sales_for_asin = self.asin_sales_count(today_orders).get(asin, 0)
            if today_sales_for_asin > 0:
                weighted_velocity = today_sales_for_asin  # Use today's sales as velocity
                velocity_data['current_velocity'] = today_sales_for_asin
                # Using today's sales as velocity baseline
        
        # Trend analysis with safety checks (adjusted for 30-day data limit)
        recent_velocity = (velocity_data['3d'] + velocity_data['7d']) / 2      # Very recent: 3-7 days
        historical_velocity = (velocity_data['21d'] + velocity_data['30d']) / 2 # Historical: 3-4 weeks ago
        
        # Debug: Print trend calculation details for first few products
        if not hasattr(self, '_trend_debug_count'):
            self._trend_debug_count = 0
        
        if self._trend_debug_count < 3:  # Debug first 3 products
            pass  # Debug print removed
            pass  # Debug print removed
            pass  # Debug print removed
            pass  # Debug print removed
            pass  # Debug print removed
            pass  # Debug print removed
            pass  # Debug print removed
            pass  # Debug print removed
            self._trend_debug_count += 1
        
        # Ensure no NaN/Inf values in trend calculation
        if historical_velocity > 0 and recent_velocity >= 0:
            trend_factor = recent_velocity / historical_velocity
        else:
            trend_factor = 1.0
            
        # Clamp trend_factor to reasonable bounds to prevent extreme values
        raw_trend_factor = trend_factor
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
            'current_velocity': velocity_data['3d'],  # Use 3-day as "current"
            'weighted_velocity': weighted_velocity,
            'trend_factor': trend_factor,
            'trend_direction': trend_direction,
            'confidence': confidence,
            'period_data': velocity_data
        }

    def get_days_left_value(self, stock_record: dict):
        """Helper function to get days left value handling column name variations"""
        # Debug: print available columns (only once)
        if not hasattr(self, '_debug_printed'):
            # Stock columns available
            self._debug_printed = True
            
        # List of possible column name patterns for days left
        possible_patterns = [
            'Days of stock left',
            'Days Left',
            'Days of Stock Left', 
            'Days Of Stock Left',
            'DaysLeft',
            'Days_Left',
            'Days Stock Left',
            'Stock Days Left',
            'Inventory Days Left',
            'Days Until Out of Stock'
        ]
        
        # First try exact matches (case insensitive)
        for pattern in possible_patterns:
            for key in stock_record.keys():
                if key.lower() == pattern.lower():
                    value = stock_record.get(key)
                    if value is not None and str(value).strip() != '':
                        try:
                            return float(value)
                        except (ValueError, TypeError):
                            return value
        
        # Then try partial matches
        for key in stock_record.keys():
            key_lower = key.lower().replace(' ', '').replace('_', '')
            if ('days' in key_lower and 'stock' in key_lower and 'left' in key_lower) or \
               ('days' in key_lower and 'left' in key_lower) or \
               ('stock' in key_lower and 'days' in key_lower):
                value = stock_record.get(key)
                if value is not None and str(value).strip() != '':
                    try:
                        return float(value)
                    except (ValueError, TypeError):
                        return value
        
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
        
        # Show trend information with more nuanced display
        if trend_factor > 1.2:
            if trend_factor >= 3.0:
                reasoning_parts.append(f"strong acceleration (3x+ recent growth)")
            elif trend_factor >= 2.0:
                reasoning_parts.append(f"accelerating trend (+{(trend_factor-1)*100:.0f}%)")
            else:
                reasoning_parts.append(f"accelerating trend (+{(trend_factor-1)*100:.0f}%)")
        elif trend_factor < 0.8:
            if trend_factor <= 0.3:
                reasoning_parts.append(f"steep decline (-{(1-trend_factor)*100:.0f}%)")
            else:
                reasoning_parts.append(f"declining trend (-{(1-trend_factor)*100:.0f}%)")
        
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

    def calculate_optimal_restock_quantity(self, asin: str, velocity_data: Dict, stock_info: Dict, lead_time_days: int = 90, purchase_analytics: Dict = None) -> Dict:
        """Calculate realistic restock quantity with practical business constraints"""
        if not stock_info or not velocity_data:
            return {'suggested_quantity': 0, 'reasoning': 'Insufficient data', 'monthly_purchase_adjustment': 0}
        
        try:
            current_stock = float(stock_info.get('FBA/FBM Stock', 0))
        except (ValueError, TypeError):
            current_stock = 0
        
        # Base velocity with trend adjustment
        base_velocity = velocity_data.get('weighted_velocity', 0)
        trend_factor = velocity_data.get('trend_factor', 1.0)
        seasonality = self.calculate_seasonality_factor(date.today())
        
        # Smooth velocity to avoid extreme spikes (cap trend factor impact)
        trend_factor = max(0.3, min(trend_factor, 3.0))  # Limit trend impact to -70% to +200%
        
        # Adjusted daily velocity with smoothing
        adjusted_velocity = base_velocity * trend_factor * seasonality
        
        # Use user-configured lead time, fallback to 90 days (3 months for Amazon)
        amazon_lead_time = lead_time_days
        
        # Target stock after arrival: 45 days (1.5 months)
        target_stock_days = 45
        
        # Safety buffer based on velocity variability (much more conservative)
        confidence = velocity_data.get('confidence', 0.5)
        if confidence > 0.8:
            safety_days = 7   # High confidence products
        elif confidence > 0.6:
            safety_days = 14  # Medium confidence
        else:
            safety_days = 21  # Low confidence products
        
        # Calculate base needed inventory (lead time + target stock + safety)
        total_coverage_days = amazon_lead_time + target_stock_days + safety_days
        total_needed = adjusted_velocity * total_coverage_days
        
        # Apply velocity-based caps to prevent unrealistic orders (realistic caps for variable lead time)
        daily_velocity = adjusted_velocity
        if daily_velocity <= 0.5:
            # Very slow moving: cap at lead time + 2 months
            max_quantity = daily_velocity * (amazon_lead_time + 60)
        elif daily_velocity <= 1.0:
            # Slow moving: cap at lead time + 1.5 months
            max_quantity = daily_velocity * (amazon_lead_time + 45)
        elif daily_velocity <= 2.0:
            # Medium velocity: cap at lead time + 1 month
            max_quantity = daily_velocity * (amazon_lead_time + 30)
        elif daily_velocity <= 5.0:
            # High velocity: cap at lead time + 2 weeks
            max_quantity = daily_velocity * (amazon_lead_time + 14)
        else:
            # Very high velocity: cap at lead time + 1 week to reduce risk
            max_quantity = daily_velocity * (amazon_lead_time + 7)
        
        # Apply the cap
        total_needed = min(total_needed, max_quantity)
        
        # Subtract current stock to get reorder quantity
        suggested_quantity = max(0, total_needed - current_stock)
        
        # Adjust for recent purchases - reduce recommended quantity by what was already purchased in last 2 months
        monthly_purchase_adjustment = 0
        if purchase_analytics:
            recent_purchases = self.get_recent_2_months_purchases(asin, purchase_analytics)
            if recent_purchases > 0:
                monthly_purchase_adjustment = recent_purchases
                suggested_quantity = max(0, suggested_quantity - recent_purchases)
        
        # Apply minimum order thresholds and rounding
        if suggested_quantity <= 0:
            suggested_quantity = 0
        elif suggested_quantity < 5:
            suggested_quantity = max(1, math.ceil(suggested_quantity))  # Minimum 1 unit
        elif suggested_quantity < 20:
            suggested_quantity = math.ceil(suggested_quantity)  # Round up for small quantities
        elif suggested_quantity < 100:
            suggested_quantity = math.ceil(suggested_quantity / 5) * 5  # Round to nearest 5
        else:
            suggested_quantity = math.ceil(suggested_quantity / 10) * 10  # Round to nearest 10 for large quantities
        
        # Final safety check: never recommend more than lead time + 3 months of inventory at current velocity
        absolute_max = base_velocity * (amazon_lead_time + 90)  # Lead time + 3 months at base velocity
        if suggested_quantity > absolute_max and absolute_max > 0:
            suggested_quantity = math.ceil(absolute_max / 10) * 10
        
        # Calculate estimated coverage
        total_after_restock = current_stock + suggested_quantity
        estimated_coverage = total_after_restock / adjusted_velocity if adjusted_velocity > 0 else 999
        
        # Generate reasoning with new realistic approach
        reasoning_parts = [
            f"Base velocity: {base_velocity:.1f}/day",
            f"Lead time: {amazon_lead_time} days",
            f"Target stock: {target_stock_days} days",
            f"Safety buffer: {safety_days} days"
        ]
        
        if abs(trend_factor - 1.0) > 0.1:
            if trend_factor > 1.0:
                reasoning_parts.append(f"Growing trend (+{(trend_factor-1)*100:.0f}%)")
            else:
                reasoning_parts.append(f"Declining trend ({(trend_factor-1)*100:.0f}%)")
        
        if abs(seasonality - 1.0) > 0.1:
            reasoning_parts.append(f"Seasonal factor: {seasonality:.1f}x")
        
        # Add velocity-based capping info (dynamic based on lead time)
        if total_needed != adjusted_velocity * total_coverage_days:
            cap_days = max_quantity / daily_velocity if daily_velocity > 0 else 0
            cap_months = cap_days / 30
            if daily_velocity <= 0.5:
                reasoning_parts.append(f"Capped at {cap_months:.1f}mo (slow-moving)")
            elif daily_velocity <= 1.0:
                reasoning_parts.append(f"Capped at {cap_months:.1f}mo (moderate)")
            elif daily_velocity <= 2.0:
                reasoning_parts.append(f"Capped at {cap_months:.1f}mo (medium)")
            elif daily_velocity <= 5.0:
                reasoning_parts.append(f"Capped at {cap_months:.1f}mo (high velocity)")
            else:
                reasoning_parts.append(f"Capped at {cap_months:.1f}mo (very high velocity)")
        
        # Add recent purchase adjustment to reasoning
        if monthly_purchase_adjustment > 0:
            reasoning_parts.append(f"Reduced by {monthly_purchase_adjustment} units (recent purchases)")
        
        reasoning = ", ".join(reasoning_parts)
        
        return {
            'suggested_quantity': int(suggested_quantity),
            'current_stock': current_stock,
            'adjusted_velocity': adjusted_velocity,
            'estimated_coverage_days': round(estimated_coverage, 1),
            'safety_days': safety_days,
            'reasoning': reasoning,
            'lead_time_days': lead_time_days,
            'confidence': confidence,
            'monthly_purchase_adjustment': monthly_purchase_adjustment
        }

    def get_recent_2_months_purchases(self, asin: str, purchase_analytics: Dict) -> int:
        """Get the quantity purchased for this ASIN in the last 2 months (from last 2 worksheets)"""
        if not purchase_analytics:
            return 0
        
        # First check the dedicated recent 2 months purchases data
        recent_2_months_data = purchase_analytics.get('recent_2_months_purchases', {})
        if asin in recent_2_months_data:
            qty_purchased = recent_2_months_data[asin].get('total_quantity_purchased', 0)
            pass  # Debug print removed
            return qty_purchased
        
        # Fallback to velocity analysis approach
        velocity_analysis = purchase_analytics.get('purchase_velocity_analysis', {}).get(asin, {})
        if velocity_analysis:
            days_since_last = velocity_analysis.get('days_since_last_purchase', 999)
            
            # If purchased within the last 2 months (last 60 days), return the last purchase quantity
            if days_since_last <= 60:
                qty = int(velocity_analysis.get('avg_quantity_per_purchase', 0))
                pass  # Debug print removed
                return qty
        
        pass  # Debug print removed
        return 0
    
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

    def fetch_google_sheet_data(self, access_token: str, sheet_id: str, worksheet_title: str, column_mapping: dict) -> Tuple[Dict[str, dict], pd.DataFrame]:
        """Fetch both COGS data and full sheet data for purchase analytics"""
        try:
            pass  # Debug print removed
            
            # Fetch the sheet data using existing function
            import requests
            range_ = f"'{worksheet_title}'!A1:Z"
            url = (
                f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}"
                f"/values/{requests.utils.quote(range_, safe='')}?majorDimension=ROWS"
            )
            headers = {"Authorization": f"Bearer {access_token}"}
            r = requests.get(url, headers=headers)
            r.raise_for_status()
            values = r.json().get("values", [])
            
            if not values or len(values) < 2:
                pass  # Debug print removed
                return {}, pd.DataFrame()
            
            # Create DataFrame
            cols = values[0]
            pass  # Debug print removed
            rows = []
            for row in values[1:]:
                # pad/truncate to match header length
                if len(row) < len(cols):
                    row += [""] * (len(cols) - len(row))
                elif len(row) > len(cols):
                    row = row[: len(cols)]
                rows.append(row)
            
            df = pd.DataFrame(rows, columns=cols)
            pass  # Debug print removed
            
            # Generate COGS data using existing logic
            cogs_data = self._process_cogs_data(df, column_mapping)
            
            return cogs_data, df
            
        except Exception as e:
            pass  # Debug print removed
            return {}, pd.DataFrame()

    def fetch_google_sheet_cogs_data(self, access_token: str, sheet_id: str, worksheet_title: str, column_mapping: dict) -> Dict[str, dict]:
        """Fetch COGS and Source links from Google Sheet for each ASIN"""
        cogs_data, _ = self.fetch_google_sheet_data(access_token, sheet_id, worksheet_title, column_mapping)
        return cogs_data
    
    def _process_cogs_data(self, df: pd.DataFrame, column_mapping: dict) -> Dict[str, dict]:
        """Process DataFrame to extract COGS data"""
        try:
            pass  # Debug print removed
            pass  # Debug print removed
            
            # Get column mappings
            asin_field = column_mapping.get("ASIN", "ASIN")
            cogs_field = column_mapping.get("COGS", "COGS")
            date_field = column_mapping.get("Date", "Date")
            
            
            # Look for Source/Link columns
            source_field = None
            for col in df.columns:
                col_lower = col.lower()
                if any(keyword in col_lower for keyword in ['source', 'link', 'url', 'supplier', 'vendor', 'store']):
                    source_field = col
                    # Source field found
                    break
            
            if not source_field:
                # No source field found in columns
                pass
            
            # Clean and process data
            pass  # Debug print removed
            df[asin_field] = df[asin_field].astype(str).str.strip()
            pass  # Debug print removed
            
            pass  # Debug print removed
            
            # Process COGS field step by step with debugging
            cogs_raw = df[cogs_field].astype(str)
            
            cogs_cleaned = cogs_raw.replace(r"[\$,]", "", regex=True)
            
            df[cogs_field] = pd.to_numeric(cogs_cleaned, errors="coerce")
            pass  # Debug print removed
            pass  # Debug print removed
            pass  # Debug print removed
            
            # Convert date column for sorting
            try:
                df[date_field] = pd.to_datetime(df[date_field], errors="coerce")
            except:
                # If date conversion fails, use row order as proxy for chronological order
                df['_row_order'] = range(len(df))
            
            # Group by ASIN and get comprehensive purchase history
            cogs_data = {}
            for asin in df[asin_field].unique():
                if pd.isna(asin) or asin == '' or asin == 'nan':
                    continue
                    
                asin_rows = df[df[asin_field] == asin].copy()
                
                # Sort by date (or row order if date is unavailable) to get chronological order
                if date_field in asin_rows.columns and not asin_rows[date_field].isna().all():
                    asin_rows = asin_rows.sort_values(date_field, na_position='first')
                elif '_row_order' in asin_rows.columns:
                    asin_rows = asin_rows.sort_values('_row_order')
                
                # Get latest COGS (for the main COGS display)
                latest_row = asin_rows.iloc[-1]
                latest_cogs = latest_row[cogs_field]
                
                if pd.isna(latest_cogs) or latest_cogs <= 0:
                    continue
                
                # Collect all unique source links from purchase history
                all_sources = []
                last_known_source = None
                
                for _, row in asin_rows.iterrows():
                    source_value = row[source_field] if source_field else None
                    if source_value and not pd.isna(source_value):
                        cleaned_source = str(source_value).strip()
                        if cleaned_source and cleaned_source != '' and cleaned_source.lower() != 'nan':
                            # This row has a source, remember it
                            last_known_source = cleaned_source
                            if cleaned_source not in all_sources:
                                all_sources.append(cleaned_source)
                    # If this row has empty source but we have a last known source, use that
                    elif last_known_source and last_known_source not in all_sources:
                        all_sources.append(last_known_source)
                
                # Sources found for ASIN
                
                # Use the most recent valid source as the primary source
                primary_source = all_sources[-1] if all_sources else None
                
                cogs_data[asin] = {
                    'cogs': float(latest_cogs),
                    'source_link': primary_source,
                    'all_sources': all_sources,  # Keep all sources for potential future use
                    'last_purchase_date': latest_row[date_field] if date_field in latest_row and not pd.isna(latest_row[date_field]) else None,
                    'source_column': source_field,
                    'total_purchases': len(asin_rows)
                }
                # COGS data processed for ASIN
            
            # COGS data fetched from Google Sheet
            if len(cogs_data) > 0:
                # Show sample COGS data
                sample_asin = list(cogs_data.keys())[0]
                # Sample COGS data available
            else:
                # No COGS data found in sheet
                pass
            return cogs_data
            
        except Exception as e:
            pass  # Debug print removed
            return {}

    def fetch_google_sheet_cogs_data_all_worksheets(self, access_token: str, sheet_id: str, column_mapping: dict) -> tuple[Dict[str, dict], pd.DataFrame]:
        """Fetch COGS and Source links from ALL worksheets in the Google Sheet
        
        Args:
            access_token: Google API access token
            sheet_id: Google Sheet ID
            column_mapping: User's column mapping configuration
        
        Returns:
            tuple: (cogs_data dict, combined_dataframe for purchase analytics)
        """
        try:
            import requests
            
            # First, get list of all worksheets
            metadata_url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}?fields=sheets.properties"
            headers = {"Authorization": f"Bearer {access_token}"}
            r = requests.get(metadata_url, headers=headers)
            r.raise_for_status()
            
            sheets_info = r.json().get("sheets", [])
            worksheet_names = [sheet["properties"]["title"] for sheet in sheets_info]
            
            # Expected column structure based on user's column mapping
            # Get the actual column names from user's mapping (excluding source field which we'll detect dynamically)
            expected_columns = set()
            required_fields = ["Date", "ASIN", "COGS"]  # Removed "Store and Source Link" - we'll detect source columns dynamically
            for field in required_fields:
                mapped_column = column_mapping.get(field, field)  # Use mapping or fallback to field name
                expected_columns.add(mapped_column)
            
            
            combined_cogs_data = {}
            combined_dataframes = []  # For purchase analytics
            successful_sheets = []
            
            for worksheet_name in worksheet_names:
                try:
                    # Processing worksheet
                    
                    # Fetch worksheet data
                    range_ = f"'{worksheet_name}'!A1:Z"
                    url = (
                        f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}"
                        f"/values/{requests.utils.quote(range_, safe='')}?majorDimension=ROWS"
                    )
                    r = requests.get(url, headers=headers)
                    r.raise_for_status()
                    values = r.json().get("values", [])
                    
                    # Also fetch hyperlinks using batchGet to get rich text data
                    hyperlinks = {}
                    try:
                        batch_url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}:batchGet"
                        batch_params = {
                            'ranges': [f"'{worksheet_name}'!A1:ZZ"],
                            'includeGridData': 'true',
                            'fields': 'sheets.data.rowData.values.hyperlink,sheets.data.rowData.values.textFormatRuns,sheets.data.rowData.values.formattedValue'
                        }
                        batch_r = requests.get(batch_url, headers=headers, params=batch_params)
                        if batch_r.status_code == 200:
                            batch_data = batch_r.json()
                            hyperlinks = self.extract_hyperlinks_from_batch_data(batch_data)
                            pass  # Debug print removed
                    except Exception as e:
                        pass  # Debug print removed
                        hyperlinks = {}
                    
                    if not values or len(values) < 2:
                        # Skipping worksheet - insufficient data
                        continue
                    
                    # Check if column structure matches expected format
                    cols = values[0]
                    available_columns = set(cols)
                    pass  # Debug print removed
                    pass  # Debug print removed
                    
                    # Check if this looks like data instead of headers (common issue)
                    if any(col.startswith(('$', 'http', 'B0', '20')) or col.replace('.', '').replace('%', '').isdigit() for col in cols if col):
                        pass  # Debug print removed
                        continue
                    
                    if not expected_columns.issubset(available_columns):
                        missing = expected_columns - available_columns
                        pass  # Debug print removed
                        continue
                    
                    # Worksheet has correct structure
                    
                    # Create DataFrame
                    rows = []
                    for row in values[1:]:
                        # pad/truncate to match header length
                        if len(row) < len(cols):
                            row += [""] * (len(cols) - len(row))
                        elif len(row) > len(cols):
                            row = row[:len(cols)]
                        rows.append(row)
                    
                    df = pd.DataFrame(rows, columns=cols)
                    
                    # Use user's column mapping
                    asin_field = column_mapping.get("ASIN", "ASIN")
                    cogs_field = column_mapping.get("COGS", "COGS")
                    date_field = column_mapping.get("Date", "Date")
                    
                    # Dynamically detect source field - look for any column containing "Source"
                    source_field = None
                    # First try the user's mapping if they have one
                    if "Store and Source Link" in column_mapping:
                        mapped_source = column_mapping["Store and Source Link"]
                        if mapped_source in available_columns:
                            source_field = mapped_source
                    
                    # If no mapping or mapped field not found, search for any column containing "Source"
                    if not source_field:
                        for col in available_columns:
                            if "source" in col.lower():
                                source_field = col
                                pass  # Debug print removed
                                break
                    
                    if not source_field:
                        pass  # Debug print removed
                        source_field = None  # Will be handled gracefully in process_asin_cogs_data
                    
                    # Processing worksheet rows
                    
                    # Clean and process data
                    df[asin_field] = df[asin_field].astype(str).str.strip()
                    df[cogs_field] = pd.to_numeric(
                        df[cogs_field].astype(str).replace(r"[\$,]", "", regex=True), errors="coerce"
                    )
                    
                    # Convert date column for sorting
                    try:
                        df[date_field] = pd.to_datetime(df[date_field], errors="coerce")
                    except:
                        df['_row_order'] = range(len(df))
                    
                    # Process each ASIN in this worksheet, passing hyperlinks data
                    worksheet_cogs = self.process_asin_cogs_data(df, asin_field, cogs_field, date_field, source_field, hyperlinks)
                    
                    # Merge with combined data (later sheets override earlier ones for same ASIN)
                    for asin, data in worksheet_cogs.items():
                        if asin in combined_cogs_data:
                            # Combine sources from multiple sheets
                            existing_sources = combined_cogs_data[asin].get('all_sources', [])
                            new_sources = data.get('all_sources', [])
                            all_sources = existing_sources + [s for s in new_sources if s not in existing_sources]
                            
                            # Use the more recent data (assume later sheets are more recent)
                            combined_cogs_data[asin] = data
                            combined_cogs_data[asin]['all_sources'] = all_sources
                            combined_cogs_data[asin]['source_sheets'] = combined_cogs_data[asin].get('source_sheets', []) + [worksheet_name]
                        else:
                            combined_cogs_data[asin] = data
                            combined_cogs_data[asin]['source_sheets'] = [worksheet_name]
                    
                    # Check if this worksheet has purchase analytics columns (using user's mapping)
                    purchase_analytics_fields = ["Amount Purchased", "Sale Price", "# Units in Bundle"]
                    mapped_purchase_columns = set()
                    for field in purchase_analytics_fields:
                        mapped_column = column_mapping.get(field, field)
                        mapped_purchase_columns.add(mapped_column)
                    
                    if mapped_purchase_columns.intersection(available_columns):
                        pass  # Debug print removed
                        pass  # Debug print removed
                        # Add worksheet identifier to the DataFrame
                        try:
                            df_copy = df.copy()
                            df_copy['_worksheet_source'] = worksheet_name
                            # Reset index to avoid conflicts when concatenating
                            df_copy = df_copy.reset_index(drop=True)
                            combined_dataframes.append(df_copy)
                            pass  # Debug print removed
                        except Exception as df_error:
                            pass  # Debug print removed
                            continue
                    else:
                        missing_columns = mapped_purchase_columns - available_columns
                    
                    successful_sheets.append(worksheet_name)
                    # Worksheet processed successfully
                    
                except Exception as e:
                    # Error processing worksheet
                    continue
            
            # All worksheets processed
            # COGS data combined from all worksheets
            
            # Combine all DataFrames for purchase analytics
            if combined_dataframes:
                try:
                    pass  # Debug print removed
                    # Check for column compatibility before concatenating
                    if len(combined_dataframes) > 1:
                        first_cols = set(combined_dataframes[0].columns)
                        for i, df in enumerate(combined_dataframes[1:], 1):
                            current_cols = set(df.columns)
                            if first_cols != current_cols:
                                pass  # Column mismatch
                    
                    combined_df = pd.concat(combined_dataframes, ignore_index=True, sort=False)
                    pass  # Debug print removed
                except Exception as concat_error:
                    pass  # Debug print removed
                    # Fall back to using just the first DataFrame
                    if combined_dataframes:
                        combined_df = combined_dataframes[0].copy()
                        pass  # Debug print removed
                    else:
                        combined_df = pd.DataFrame()
            else:
                combined_df = pd.DataFrame()
            
            return combined_cogs_data, combined_df
            
        except Exception as e:
            pass  # Debug print removed
            return {}, pd.DataFrame()
    
    def extract_hyperlinks_from_batch_data(self, batch_data):
        """Extract hyperlinks from Google Sheets batchGet response"""
        hyperlinks = {}
        try:
            pass  # Debug print removed
            sheets = batch_data.get('sheets', [])
            if not sheets:
                pass  # Debug print removed
                return hyperlinks
                
            sheet = sheets[0]  # First sheet in the response
            pass  # Debug print removed
            data = sheet.get('data', [])
            if not data:
                pass  # Debug print removed
                return hyperlinks
                
            grid_data = data[0]  # First data range
            pass  # Debug print removed
            row_data = grid_data.get('rowData', [])
            
            for row_idx, row in enumerate(row_data):
                values = row.get('values', [])
                for col_idx, cell in enumerate(values):
                    cell_links = []
                    
                    # Check for direct hyperlink
                    if 'hyperlink' in cell:
                        cell_links.append(cell['hyperlink'])
                    
                    # Check for textFormatRuns (multiple hyperlinks in one cell)
                    if 'textFormatRuns' in cell:
                        pass  # Debug print removed
                        for run_idx, run in enumerate(cell['textFormatRuns']):
                            pass  # Debug print removed
                            if 'format' in run:
                                pass  # Debug print removed
                                if 'link' in run['format']:
                                    link_info = run['format']['link']
                                    pass  # Debug print removed
                                    if 'uri' in link_info:
                                        cell_links.append(link_info['uri'])
                    
                    if cell_links:
                        hyperlinks[f"{row_idx},{col_idx}"] = cell_links
                        
            pass  # Debug print removed
            return hyperlinks
        except Exception as e:
            pass  # Debug print removed
            import traceback
            traceback.print_exc()
            return {}

    def process_asin_cogs_data(self, df, asin_field, cogs_field, date_field, source_field, hyperlinks=None):
        """Extract COGS data for each ASIN from a worksheet DataFrame"""
        cogs_data = {}
        
        for asin in df[asin_field].unique():
            if pd.isna(asin) or asin == '' or asin == 'nan':
                continue
                
            asin_rows = df[df[asin_field] == asin].copy()
            
            # Sort by date (or row order if date is unavailable) to get chronological order
            if date_field in asin_rows.columns and not asin_rows[date_field].isna().all():
                asin_rows = asin_rows.sort_values(date_field, na_position='first')
            elif '_row_order' in asin_rows.columns:
                asin_rows = asin_rows.sort_values('_row_order')
            
            # Get latest COGS (for the main COGS display)
            latest_row = asin_rows.iloc[-1]
            latest_cogs = latest_row[cogs_field]
            
            if pd.isna(latest_cogs) or latest_cogs <= 0:
                continue
            
            # Collect all unique source links from purchase history
            all_sources = []
            last_known_source = None
            
            for row_idx, row in asin_rows.iterrows():
                source_value = row[source_field] if source_field else None
                
                # Check for hyperlinks from Google Sheets API data
                hyperlink_sources = []
                if hyperlinks and source_field:
                    # Find the column index for the source field
                    col_idx = None
                    try:
                        col_idx = df.columns.get_loc(source_field)
                        # Get the original row index (accounting for header row)
                        original_row_idx = row.name + 1  # Add 1 because Google Sheets rows are 1-indexed and we skip header
                        hyperlink_key = f"{original_row_idx},{col_idx}"
                        
                        pass  # Debug print removed
                        pass  # Debug print removed
                        
                        if hyperlink_key in hyperlinks:
                            hyperlink_sources = hyperlinks[hyperlink_key]
                            pass  # Debug print removed
                        else:
                            pass  # Debug print removed
                    except Exception as e:
                        pass  # Error getting hyperlinks
                
                # Process text-based source value
                if source_value and not pd.isna(source_value):
                    cleaned_source = str(source_value).strip()
                    if cleaned_source and cleaned_source != '' and cleaned_source.lower() != 'nan':
                        # This row has a source, remember it
                        last_known_source = cleaned_source
                        if cleaned_source not in all_sources:
                            all_sources.append(cleaned_source)
                
                # Add hyperlink sources
                for hyperlink_url in hyperlink_sources:
                    if hyperlink_url and hyperlink_url not in all_sources:
                        all_sources.append(hyperlink_url)
                        last_known_source = hyperlink_url
                        
                # If this row has empty source but we have a last known source, use that
                if not source_value or pd.isna(source_value):
                    if last_known_source and last_known_source not in all_sources:
                        all_sources.append(last_known_source)
            
            # Use the most recent valid source as the primary source
            primary_source = all_sources[-1] if all_sources else None
            
            cogs_data[asin] = {
                'cogs': float(latest_cogs),
                'source_link': primary_source,
                'all_sources': all_sources,
                'last_purchase_date': latest_row[date_field] if date_field in latest_row and not pd.isna(latest_row[date_field]) else None,
                'source_column': source_field,
                'total_purchases': len(asin_rows)
            }
        
        return cogs_data

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

    def analyze(self, for_date: date, prev_date: Optional[date] = None, user_timezone: str = None, user_settings: dict = None) -> dict:
        """Main analysis function with enhanced logic"""
        # Download and process orders data
        orders_df = self.download_csv(self.orders_url)
        today_orders = self.get_orders_for_date(orders_df, for_date, user_timezone)
        today_sales = self.asin_sales_count(today_orders)

        # Download stock report
        stock_df = self.download_csv(self.stock_url)
        stock_info = self.get_stock_info(stock_df)

        # Fetch COGS data and purchase analytics from Google Sheet if enabled
        cogs_data = {}
        purchase_insights = {}
        
        pass  # Debug print removed
        pass  # Debug print removed
        pass  # Debug print removed
        pass  # Debug print removed
        pass  # Debug print removed
        
        if user_settings and user_settings.get('enable_source_links'):
            pass  # Debug print removed
            try:
                # Import here to avoid circular imports
                import sys
                import os
                parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                if parent_dir not in sys.path:
                    sys.path.append(parent_dir)
                
                from app import refresh_google_token
                
                # Get user's Google Sheet settings
                sheet_id = user_settings.get('sheet_id')
                worksheet_title = user_settings.get('worksheet_title')
                google_tokens = user_settings.get('google_tokens', {})
                column_mapping = user_settings.get('column_mapping', {})
                
                if sheet_id and google_tokens:
                    # Create a temporary user_record for the refresh function
                    temp_user_record = {'google_tokens': google_tokens}
                    access_token = refresh_google_token(temp_user_record)
                    
                    # Check if we should search all worksheets or just the mapped one
                    if user_settings.get('search_all_worksheets', False):
                        pass  # Debug print removed
                        pass  # Debug print removed
                        cogs_data, sheet_data = self.fetch_google_sheet_cogs_data_all_worksheets(
                            access_token, sheet_id, column_mapping
                        )
                        # Use the user's column mapping for purchase analytics
                        column_mapping_for_purchase = column_mapping
                        
                        # If all worksheets search failed and we have a specific worksheet, try that instead
                        if not cogs_data and worksheet_title:
                            pass  # Debug print removed
                            pass  # Debug print removed
                            cogs_data, sheet_data = self.fetch_google_sheet_data(
                                access_token, sheet_id, worksheet_title, column_mapping
                            )
                            column_mapping_for_purchase = column_mapping
                            
                    elif worksheet_title:
                        pass  # Debug print removed
                        cogs_data, sheet_data = self.fetch_google_sheet_data(
                            access_token, sheet_id, worksheet_title, column_mapping
                        )
                        column_mapping_for_purchase = column_mapping
                    else:
                        pass  # Debug print removed
                        cogs_data = {}
                        sheet_data = pd.DataFrame()
                        column_mapping_for_purchase = {}
                    
                    
                    # Generate purchase analytics if we have sheet data
                    if not sheet_data.empty:
                        pass  # Debug print removed
                        purchase_insights = self.purchase_analytics.analyze_purchase_data(
                            sheet_data, column_mapping_for_purchase
                        )
                        pass  # Debug print removed
                    else:
                        pass  # No sheet data available for purchase analytics
                else:
                    pass  # Debug print removed
            except Exception as e:
                pass  # Debug print removed
                cogs_data = {}
                purchase_insights = {}

        # Load historical sales for comparison
        if prev_date is None:
            prev_date = for_date - timedelta(days=1)
        yesterday_sales = self.load_yesterday_sales()

        # Enhanced analytics for each ASIN
        enhanced_analytics = {}
        restock_alerts = {}
        critical_alerts = []
        
        # Only analyze products that have either sales today OR historical sales
        products_to_analyze = set()
        products_to_analyze.update(today_sales.keys())  # Products with sales today
        products_to_analyze.update(yesterday_sales.keys())  # Products with historical sales
        
        # Also include products from stock info that have sales in the past 7 days
        for asin in stock_info.keys():
            if asin in today_sales or asin in yesterday_sales:
                products_to_analyze.add(asin)
        
        # Total products to analyze calculated
        
        for asin in products_to_analyze:
            if asin not in stock_info:
                # Skipping product with no stock info
                continue
                
            # Calculate enhanced velocity
            velocity_data = self.calculate_enhanced_velocity(asin, orders_df, for_date, user_timezone)
            
            # Skip products with zero velocity across all periods
            if velocity_data.get('weighted_velocity', 0) == 0 and today_sales.get(asin, 0) == 0:
                # Skipping product with zero velocity
                continue
            
            # Get priority score
            current_sales = today_sales.get(asin, 0)
            priority_data = self.get_priority_score(asin, velocity_data, stock_info[asin], current_sales)
            
            # Get user's lead time setting, default to 90 days
            user_lead_time = user_settings.get('amazon_lead_time_days', 90) if user_settings else 90
            
            # Calculate optimal restock quantity with purchase analytics and user's lead time
            restock_data = self.calculate_optimal_restock_quantity(asin, velocity_data, stock_info[asin], lead_time_days=user_lead_time, purchase_analytics=purchase_insights)
            
            # Combine all data including COGS and purchase analytics data if available
            enhanced_analytics[asin] = {
                'current_sales': current_sales,
                'velocity': velocity_data,
                'priority': priority_data,
                'restock': restock_data,
                'stock_info': stock_info[asin],
                'product_name': stock_info[asin].get('Title', f'Product {asin}'),
                'cogs_data': cogs_data.get(asin, {}),  # Include COGS and source link data
                'purchase_analytics': {
                    'velocity_analysis': purchase_insights.get('purchase_velocity_analysis', {}).get(asin, {}),
                    'urgency_scoring': purchase_insights.get('restock_urgency_scoring', {}).get(asin, {}),
                    'roi_recommendations': purchase_insights.get('roi_based_recommendations', {}).get(asin, {}),
                    'seasonal_trends': purchase_insights.get('seasonal_purchase_trends', {}).get(asin, {})
                }
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
                    
        # Enhanced analytics completed

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
                # Try multiple possible column names for days left
                days_left = None
                for col in ['Days of stock left', 'Days left', 'Days of stock left (By Amazon)', 'Days of Stock Left']:
                    if col in stock and stock[col] not in [None, '', 'N/A']:
                        days_left = float(stock[col])
                        break
                if days_left is None:
                    days_left = 9999
            except:
                days_left = 9999
                
            # Try multiple possible column names for running out status
            running_out = ''
            for col in ['Running out of stock', 'Running out', 'Out of stock', 'Stock status']:
                if col in stock and stock[col] not in [None, '']:
                    running_out = str(stock[col]).strip().upper()
                    break
            
            # Debug: Print the first few items to see what values we're getting
            if len(low_stock) < 3:  # Only log first 3 to avoid spam
                # Processing stock analysis
                pass
                
            if days_left < 7 or running_out in ("SOON", "YES"):
                # Low stock item identified
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

        # Convert orders DataFrame to dict for revenue calculation
        sellerboard_orders = []
        if not today_orders.empty:
            # Convert DataFrame to dict format for frontend
            sellerboard_orders = today_orders.to_dict('records')
            # Revenue data prepared
            if sellerboard_orders:
                # Check what revenue fields are available
                sample_order = sellerboard_orders[0]
                revenue_fields = [k for k in sample_order.keys() if 'total' in k.lower() or 'amount' in k.lower() or 'revenue' in k.lower()]
                # Revenue fields identified

        return {
            # Enhanced analytics (new)
            "enhanced_analytics": enhanced_analytics,
            "restock_alerts": restock_alerts,
            "critical_alerts": critical_alerts,
            "total_products_analyzed": len(enhanced_analytics),
            "high_priority_count": len([a for a in enhanced_analytics.values() if a['priority']['category'] in ['critical_high_velocity', 'critical_low_velocity', 'warning_high_velocity']]),
            
            # Purchase analytics insights
            "purchase_insights": purchase_insights,
            
            # Legacy data (for backward compatibility)
            "today_sales": today_sales,
            "velocity": velocity,
            "low_stock": low_stock,
            "restock_priority": restock_priority,
            "stock_info": stock_info,
            "orders_df": today_orders,
            "stockout_30d": stockout_30d,
            
            # Revenue data for frontend
            "sellerboard_orders": sellerboard_orders,
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
            'sellerboard_orders': [],  # Empty revenue data for fallback
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
            pass  # Debug print removed
            # Fall back to basic implementation
            self.orders_url = orders_url
            self.stock_url = stock_url
            self.is_fallback = True
    
    def analyze(self, for_date: date, prev_date: Optional[date] = None, user_timezone: str = None, user_settings: dict = None) -> dict:
        if hasattr(self, 'is_fallback') and self.is_fallback:
            return BasicOrdersAnalysis(self.orders_url, self.stock_url).analyze(for_date)
        else:
            return super().analyze(for_date, prev_date, user_timezone, user_settings)