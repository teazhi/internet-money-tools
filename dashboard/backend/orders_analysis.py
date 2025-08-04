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
            print("Warning: numpy not available, some enhanced analytics features may be limited")
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
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        df = pd.read_csv(StringIO(response.text))
        return df

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
                print(f"Warning: Could not convert to timezone {user_timezone}: {e}")
        
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
                print(f"[ERROR] Pandas datetime comparison error in get_orders_for_date")
                print(f"[ERROR] for_date: {for_date} (type: {type(for_date)})")
                print(f"[ERROR] DataFrame shape: {df.shape}")
                print(f"[ERROR] DataFrame columns: {list(df.columns)}")
                # Try to find date columns
                date_columns = [col for col in df.columns if 'date' in col.lower() or 'time' in col.lower()]
                if date_columns:
                    print(f"[ERROR] Date columns found: {date_columns}")
                    print(f"[ERROR] First date column dtype: {df[date_columns[0]].dtype}")
                    print(f"[ERROR] Sample values: {df[date_columns[0]].head().tolist()}")
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
        """Calculate enhanced multi-period velocity with trend analysis"""
        periods = [7, 14, 30, 60, 90]
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
                print(f"[ERROR] Pandas datetime comparison error in calculate_enhanced_velocity")
                print(f"[ERROR] ASIN: {asin}")
                print(f"[ERROR] target_date: {target_date} (type: {type(target_date)})")
                print(f"[ERROR] Failed on period: {period}")
                print(f"[ERROR] start_date: {start_date} (type: {type(start_date)})")
            raise
        
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
            
        # If all historical periods are zero but we have sales today, use today's sales as baseline velocity
        if weighted_velocity == 0 and all(v == 0 for v in velocity_data.values()):
            today_orders = self.get_orders_for_date(orders_df, target_date, user_timezone)
            today_sales_for_asin = self.asin_sales_count(today_orders).get(asin, 0)
            if today_sales_for_asin > 0:
                weighted_velocity = today_sales_for_asin  # Use today's sales as velocity
                velocity_data['current_velocity'] = today_sales_for_asin
                # Using today's sales as velocity baseline
        
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

    def fetch_google_sheet_data(self, access_token: str, sheet_id: str, worksheet_title: str, column_mapping: dict) -> Tuple[Dict[str, dict], pd.DataFrame]:
        """Fetch both COGS data and full sheet data for purchase analytics"""
        try:
            print(f"[DEBUG FETCH] Fetching data from sheet {sheet_id}, worksheet '{worksheet_title}'")
            print(f"[DEBUG FETCH] Column mapping: {column_mapping}")
            
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
            print(f"[DEBUG FETCH] Retrieved {len(values)} rows from Google Sheets API")
            
            if not values or len(values) < 2:
                print(f"[DEBUG FETCH] Insufficient data: {len(values) if values else 0} rows")
                return {}, pd.DataFrame()
            
            # Create DataFrame
            cols = values[0]
            print(f"[DEBUG FETCH] Sheet columns: {cols}")
            rows = []
            for row in values[1:]:
                # pad/truncate to match header length
                if len(row) < len(cols):
                    row += [""] * (len(cols) - len(row))
                elif len(row) > len(cols):
                    row = row[: len(cols)]
                rows.append(row)
            
            df = pd.DataFrame(rows, columns=cols)
            print(f"[DEBUG FETCH] DataFrame created: {df.shape} rows x columns")
            print(f"[DEBUG FETCH] DataFrame columns: {list(df.columns)}")
            
            # Generate COGS data using existing logic
            cogs_data = self._process_cogs_data(df, column_mapping)
            print(f"[DEBUG FETCH] Final result: {len(cogs_data)} COGS records processed")
            
            return cogs_data, df
            
        except Exception as e:
            print(f"[Google Sheets] Error fetching sheet data: {e}")
            return {}, pd.DataFrame()

    def fetch_google_sheet_cogs_data(self, access_token: str, sheet_id: str, worksheet_title: str, column_mapping: dict) -> Dict[str, dict]:
        """Fetch COGS and Source links from Google Sheet for each ASIN"""
        cogs_data, _ = self.fetch_google_sheet_data(access_token, sheet_id, worksheet_title, column_mapping)
        return cogs_data
    
    def _process_cogs_data(self, df: pd.DataFrame, column_mapping: dict) -> Dict[str, dict]:
        """Process DataFrame to extract COGS data"""
        try:
            print(f"[DEBUG COGS] Sheet shape: {df.shape}")
            print(f"[DEBUG COGS] Available columns: {list(df.columns)}")
            print(f"[DEBUG COGS] Column mapping: {column_mapping}")
            
            # Get column mappings
            asin_field = column_mapping.get("ASIN", "ASIN")
            cogs_field = column_mapping.get("COGS", "COGS")
            date_field = column_mapping.get("Date", "Date")
            
            print(f"[DEBUG COGS] Using fields - ASIN: '{asin_field}', COGS: '{cogs_field}', Date: '{date_field}'")
            
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
            print(f"[DEBUG COGS] Processing ASIN field '{asin_field}' - sample raw values: {df[asin_field].head().tolist()}")
            df[asin_field] = df[asin_field].astype(str).str.strip()
            print(f"[DEBUG COGS] After ASIN cleaning: {df[asin_field].head().tolist()}")
            print(f"[DEBUG COGS] Valid ASINs: {len(df[df[asin_field].notna() & (df[asin_field] != '') & (df[asin_field] != 'nan')])}")
            
            print(f"[DEBUG COGS] Processing COGS field '{cogs_field}' - sample raw values: {df[cogs_field].head().tolist()}")
            print(f"[DEBUG COGS] COGS column dtype: {df[cogs_field].dtype}")
            
            # Process COGS field step by step with debugging
            cogs_raw = df[cogs_field].astype(str)
            print(f"[DEBUG COGS] After str conversion: {cogs_raw.head().tolist()}")
            
            cogs_cleaned = cogs_raw.replace(r"[\$,]", "", regex=True)
            print(f"[DEBUG COGS] After removing $,: {cogs_cleaned.head().tolist()}")
            
            df[cogs_field] = pd.to_numeric(cogs_cleaned, errors="coerce")
            print(f"[DEBUG COGS] After numeric conversion: {df[cogs_field].head().tolist()}")
            print(f"[DEBUG COGS] Valid COGS values (>0): {len(df[df[cogs_field].notna() & (df[cogs_field] > 0)])}")
            print(f"[DEBUG COGS] Total non-null COGS: {df[cogs_field].notna().sum()}")
            print(f"[DEBUG COGS] COGS field stats: min={df[cogs_field].min()}, max={df[cogs_field].max()}")
            
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
            print(f"[ERROR] Failed to fetch COGS data from Google Sheet: {e}")
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
            print(f"[DEBUG COGS ALL] Found {len(worksheet_names)} worksheets: {worksheet_names}")
            
            # Expected column structure based on user's column mapping
            # Get the actual column names from user's mapping (excluding source field which we'll detect dynamically)
            expected_columns = set()
            required_fields = ["Date", "ASIN", "COGS"]  # Removed "Store and Source Link" - we'll detect source columns dynamically
            for field in required_fields:
                mapped_column = column_mapping.get(field, field)  # Use mapping or fallback to field name
                expected_columns.add(mapped_column)
            
            print(f"[DEBUG COGS ALL] Expected columns based on user mapping (excluding source): {expected_columns}")
            
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
                            'ranges': [f"'{worksheet_name}'!A1:Z"],
                            'includeGridData': 'true',
                            'fields': 'sheets.data.rowData.values.hyperlink,sheets.data.rowData.values.textFormatRuns'
                        }
                        batch_r = requests.get(batch_url, headers=headers, params=batch_params)
                        if batch_r.status_code == 200:
                            batch_data = batch_r.json()
                            hyperlinks = self.extract_hyperlinks_from_batch_data(batch_data)
                            print(f"[DEBUG COGS ALL] Extracted {len(hyperlinks)} hyperlink entries from '{worksheet_name}'")
                    except Exception as e:
                        print(f"[DEBUG COGS ALL] Could not fetch hyperlinks for '{worksheet_name}': {e}")
                        hyperlinks = {}
                    
                    if not values or len(values) < 2:
                        # Skipping worksheet - insufficient data
                        continue
                    
                    # Check if column structure matches expected format
                    cols = values[0]
                    available_columns = set(cols)
                    print(f"[DEBUG COGS ALL] Worksheet '{worksheet_name}' columns: {cols}")
                    print(f"[DEBUG COGS ALL] Expected columns: {expected_columns}")
                    print(f"[DEBUG COGS ALL] Available columns: {available_columns}")
                    
                    # Check if this looks like data instead of headers (common issue)
                    if any(col.startswith(('$', 'http', 'B0', '20')) or col.replace('.', '').replace('%', '').isdigit() for col in cols if col):
                        print(f"[DEBUG COGS ALL] Skipping '{worksheet_name}' - first row appears to be data, not headers")
                        continue
                    
                    if not expected_columns.issubset(available_columns):
                        missing = expected_columns - available_columns
                        print(f"[DEBUG COGS ALL] Skipping '{worksheet_name}' - missing columns: {missing}")
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
                                print(f"[DEBUG COGS ALL] Found source field: '{col}' in worksheet '{worksheet_name}'")
                                break
                    
                    if not source_field:
                        print(f"[DEBUG COGS ALL] No source field found in worksheet '{worksheet_name}' - COGS data will have no source links")
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
                        print(f"[DEBUG COGS ALL] Worksheet '{worksheet_name}' has purchase analytics columns - adding to combined data")
                        print(f"[DEBUG COGS ALL] Found purchase columns: {mapped_purchase_columns.intersection(available_columns)}")
                        # Add worksheet identifier to the DataFrame
                        try:
                            df_copy = df.copy()
                            df_copy['_worksheet_source'] = worksheet_name
                            # Reset index to avoid conflicts when concatenating
                            df_copy = df_copy.reset_index(drop=True)
                            combined_dataframes.append(df_copy)
                            print(f"[DEBUG COGS ALL] Added DataFrame from '{worksheet_name}': {len(df_copy)} rows")
                        except Exception as df_error:
                            print(f"[ERROR] Failed to process DataFrame from worksheet '{worksheet_name}': {df_error}")
                            continue
                    else:
                        missing_columns = mapped_purchase_columns - available_columns
                        print(f"[DEBUG COGS ALL] Worksheet '{worksheet_name}' missing purchase analytics columns: {missing_columns}")
                    
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
                    print(f"[DEBUG COGS ALL] Attempting to combine {len(combined_dataframes)} DataFrames...")
                    # Check for column compatibility before concatenating
                    if len(combined_dataframes) > 1:
                        first_cols = set(combined_dataframes[0].columns)
                        for i, df in enumerate(combined_dataframes[1:], 1):
                            current_cols = set(df.columns)
                            if first_cols != current_cols:
                                print(f"[DEBUG COGS ALL] Column mismatch in DataFrame {i}: {first_cols.symmetric_difference(current_cols)}")
                    
                    combined_df = pd.concat(combined_dataframes, ignore_index=True, sort=False)
                    print(f"[DEBUG COGS ALL] Combined DataFrame: {len(combined_df)} rows from {len(combined_dataframes)} worksheets")
                except Exception as concat_error:
                    print(f"[ERROR] Failed to concatenate DataFrames: {concat_error}")
                    # Fall back to using just the first DataFrame
                    if combined_dataframes:
                        combined_df = combined_dataframes[0].copy()
                        print(f"[DEBUG COGS ALL] Using first DataFrame as fallback: {len(combined_df)} rows")
                    else:
                        combined_df = pd.DataFrame()
            else:
                combined_df = pd.DataFrame()
                print(f"[DEBUG COGS ALL] No worksheets with purchase analytics columns found")
            
            return combined_cogs_data, combined_df
            
        except Exception as e:
            print(f"[ERROR] Failed to fetch COGS data from all worksheets: {e}")
            return {}, pd.DataFrame()
    
    def extract_hyperlinks_from_batch_data(self, batch_data):
        """Extract hyperlinks from Google Sheets batchGet response"""
        hyperlinks = {}
        try:
            sheets = batch_data.get('sheets', [])
            if not sheets:
                return hyperlinks
                
            sheet = sheets[0]  # First sheet in the response
            data = sheet.get('data', [])
            if not data:
                return hyperlinks
                
            grid_data = data[0]  # First data range
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
                        for run in cell['textFormatRuns']:
                            if 'format' in run and 'link' in run['format']:
                                link_info = run['format']['link']
                                if 'uri' in link_info:
                                    cell_links.append(link_info['uri'])
                    
                    if cell_links:
                        hyperlinks[f"{row_idx},{col_idx}"] = cell_links
                        
            return hyperlinks
        except Exception as e:
            print(f"[ERROR] Failed to extract hyperlinks: {e}")
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
                        
                        if hyperlink_key in hyperlinks:
                            hyperlink_sources = hyperlinks[hyperlink_key]
                            print(f"[DEBUG COGS] Found hyperlinks for ASIN {asin} at row {original_row_idx}, col {col_idx}: {hyperlink_sources}")
                    except Exception as e:
                        print(f"[DEBUG COGS] Error getting hyperlinks for ASIN {asin}: {e}")
                
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
        
        print(f"[DEBUG] Checking COGS settings - user_settings: {user_settings}")
        print(f"[DEBUG] enable_source_links: {user_settings.get('enable_source_links') if user_settings else None}")
        print(f"[DEBUG] sheet_id: {user_settings.get('sheet_id') if user_settings else None}")
        print(f"[DEBUG] worksheet_title: {user_settings.get('worksheet_title') if user_settings else None}")
        print(f"[DEBUG] google_tokens: {bool(user_settings.get('google_tokens')) if user_settings else None}")
        print(f"[DEBUG] search_all_worksheets: {user_settings.get('search_all_worksheets') if user_settings else None}")
        
        if user_settings and user_settings.get('enable_source_links'):
            print(f"[DEBUG] Source links enabled, attempting to fetch COGS data and purchase analytics...")
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
                        print(f"[DEBUG] Searching all worksheets in Google Sheet...")
                        print(f"[DEBUG] Using user's column mapping: {column_mapping}")
                        cogs_data, sheet_data = self.fetch_google_sheet_cogs_data_all_worksheets(
                            access_token, sheet_id, column_mapping
                        )
                        # Use the user's column mapping for purchase analytics
                        column_mapping_for_purchase = column_mapping
                        
                        # If all worksheets search failed and we have a specific worksheet, try that instead
                        if not cogs_data and worksheet_title:
                            print(f"[DEBUG] All worksheets search found no data, trying specific worksheet: {worksheet_title}")
                            print(f"[DEBUG] Using column mapping: {column_mapping}")
                            cogs_data, sheet_data = self.fetch_google_sheet_data(
                                access_token, sheet_id, worksheet_title, column_mapping
                            )
                            column_mapping_for_purchase = column_mapping
                            print(f"[DEBUG] Fallback result: {len(cogs_data)} COGS records, {len(sheet_data)} sheet rows")
                            
                    elif worksheet_title:
                        print(f"[DEBUG] Searching specific worksheet: {worksheet_title}")
                        cogs_data, sheet_data = self.fetch_google_sheet_data(
                            access_token, sheet_id, worksheet_title, column_mapping
                        )
                        column_mapping_for_purchase = column_mapping
                    else:
                        print(f"[DEBUG] No worksheet specified and search all worksheets disabled")
                        cogs_data = {}
                        sheet_data = pd.DataFrame()
                        column_mapping_for_purchase = {}
                    
                    print(f"[DEBUG] Successfully fetched COGS data for {len(cogs_data)} products")
                    
                    # Generate purchase analytics if we have sheet data
                    if not sheet_data.empty:
                        print(f"[DEBUG] Generating purchase analytics from {len(sheet_data)} sheet records...")
                        purchase_insights = self.purchase_analytics.analyze_purchase_data(
                            sheet_data, column_mapping_for_purchase
                        )
                        print(f"[DEBUG] Purchase analytics generated successfully")
                    else:
                        print(f"[DEBUG] No sheet data available for purchase analytics")
                        
                else:
                    print("[DEBUG] Missing Google Sheet settings for COGS data")
            except Exception as e:
                print(f"[ERROR] Failed to fetch COGS data and purchase analytics: {e}")
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
            
            # Calculate optimal restock quantity
            restock_data = self.calculate_optimal_restock_quantity(asin, velocity_data, stock_info[asin])
            
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
            print(f"Enhanced analytics initialization failed: {e}")
            # Fall back to basic implementation
            self.orders_url = orders_url
            self.stock_url = stock_url
            self.is_fallback = True
    
    def analyze(self, for_date: date, prev_date: Optional[date] = None, user_timezone: str = None, user_settings: dict = None) -> dict:
        if hasattr(self, 'is_fallback') and self.is_fallback:
            return BasicOrdersAnalysis(self.orders_url, self.stock_url).analyze(for_date)
        else:
            return super().analyze(for_date, prev_date, user_timezone, user_settings)