import requests
import pandas as pd
from io import StringIO
from datetime import datetime, date, timedelta
import json
import os
from typing import Dict, Optional

ORDERS_REPORT_URL = "https://app.sellerboard.com/en/automation/reports?id=e0989fcf9a9e40b8a116318d4fd7ee84&format=csv&t=c3c41a4645fa4003ab1254d06820b076"
STOCK_REPORT_URL = "https://app.sellerboard.com/en/automation/reports?id=b1e7d7e73f72404588b44df0839067dc&format=csv&t=c3c41a4645fa4003ab1254d06820b076"
YESTERDAY_SALES_FILE = "yesterday_sales.json"

class OrdersAnalysis:
    def __init__(self, orders_url: Optional[str] = None, stock_url: Optional[str] = None):
        self.orders_url = orders_url or ORDERS_REPORT_URL
        self.stock_url = stock_url or STOCK_REPORT_URL

    def _parse_datetime_robust(self, series: pd.Series, column_name: str) -> pd.Series:
        """Robust datetime parsing that tries multiple formats"""
        print(f"[DEBUG] Parsing datetime column '{column_name}' with {len(series)} values")
        
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
                    print(f"[DEBUG] Format '{fmt}' parsed {valid_count}/{len(series)} values successfully")
                    successful_format = fmt
                    break
            except Exception as e:
                continue
        
        # If no specific format worked, try pandas' flexible parsing as fallback
        if parsed_series is None or parsed_series.notna().sum() == 0:
            print(f"[DEBUG] All specific formats failed, trying flexible parsing")
            parsed_series = pd.to_datetime(series, errors='coerce')
        
        # Log results
        final_valid_count = parsed_series.notna().sum()
        nat_count = parsed_series.isna().sum()
        
        print(f"[DEBUG] Final parsing results: {final_valid_count} valid, {nat_count} NaT values")
        if successful_format:
            print(f"[DEBUG] Best format was: '{successful_format}'")
        
        # Show sample of unparseable values for debugging
        if nat_count > 0:
            invalid_mask = parsed_series.isna() & series.notna()
            if invalid_mask.any():
                sample_invalid = series[invalid_mask].head(3).tolist()
                print(f"[DEBUG] Sample unparseable values: {sample_invalid}")
        
        return parsed_series

    def download_csv(self, url: str) -> pd.DataFrame:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        df = pd.read_csv(StringIO(response.text))
        return df

    def get_orders_for_date(self, df: pd.DataFrame, for_date: date, user_timezone: str = None) -> pd.DataFrame:
        date_columns = [col for col in df.columns if 'date' in col.lower() or 'time' in col.lower()]
        if not date_columns:
            filtered_df = df
        else:
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
            
            # Convert for_date to pandas datetime for comparison
            for_date_pd = pd.to_datetime(for_date)
            # Filter out NaT values before comparison to avoid TypeError
            valid_dates_mask = df[date_col].notna()
            filtered_df = df[valid_dates_mask & (df[date_col].dt.date == for_date_pd.date())]
        status_col = None
        for col in df.columns:
            if col.lower().replace(' ', '') == 'orderstatus':
                status_col = col
                break
        if not status_col:
            raise ValueError("OrderStatus column not found in CSV.")
        filtered_df = filtered_df[filtered_df[status_col].isin(['Shipped', 'Unshipped'])]
        return filtered_df

    def asin_sales_count(self, orders_df: pd.DataFrame) -> Dict[str, int]:
        product_col = None
        for col in orders_df.columns:
            if 'product' in col.lower() or 'asin' in col.lower():
                product_col = col
                break
        if not product_col:
            raise ValueError("Products column not found in CSV.")
        return orders_df[product_col].value_counts().to_dict()

    def load_yesterday_sales(self) -> Dict[str, int]:
        if os.path.exists(YESTERDAY_SALES_FILE):
            with open(YESTERDAY_SALES_FILE, 'r') as f:
                return json.load(f)
        return {}

    def save_today_sales_as_yesterday(self, today_sales: Dict[str, int]):
        with open(YESTERDAY_SALES_FILE, 'w') as f:
            json.dump(today_sales, f)

    def get_stock_info(self, stock_df: pd.DataFrame) -> Dict[str, dict]:
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

    def analyze(self, for_date: date, prev_date: Optional[date] = None, user_timezone: str = None) -> dict:
        # Download and filter orders
        orders_df = self.download_csv(self.orders_url)
        today_orders = self.get_orders_for_date(orders_df, for_date, user_timezone)
        today_sales = self.asin_sales_count(today_orders)

        # Download stock report
        stock_df = self.download_csv(self.stock_url)
        stock_info = self.get_stock_info(stock_df)

        # Load yesterday's sales
        if prev_date is None:
            prev_date = for_date - timedelta(days=1)
        yesterday_sales = self.load_yesterday_sales()

        # Velocity change calculation
        velocity = {}
        for asin, today_count in today_sales.items():
            yest_count = yesterday_sales.get(asin, 0)
            change = today_count - yest_count
            pct = (change / yest_count * 100) if yest_count else (100 if today_count else 0)
            velocity[asin] = {"today": today_count, "yesterday": yest_count, "change": change, "pct": pct}

        # Low stock warning and restock recommendation
        low_stock = {}
        restock_priority = {}
        for asin, sales in today_sales.items():
            stock = stock_info.get(asin)
            if not stock:
                continue
            try:
                days_left = float(stock.get('Days of stock left', 9999))
            except Exception:
                days_left = 9999
            running_out = str(stock.get('Running out of stock', '')).strip().upper()
            reorder_qty = stock.get('Recommended quantity for reordering', None)
            time_to_reorder = str(stock.get('Time to reorder', '')).strip().upper()
            if days_left < 7 or running_out in ("SOON", "YES"):
                low_stock[asin] = {
                    "days_left": days_left,
                    "running_out": running_out,
                    "reorder_qty": reorder_qty,
                    "time_to_reorder": time_to_reorder,
                    "title": stock.get('Title', '')
                }
            # Restock priority: fast mover + low stock
            if (sales >= 3 or velocity[asin]["pct"] > 20) and (days_left < 7 or running_out in ("SOON", "YES")):
                restock_priority[asin] = low_stock[asin]

        # 30-day stockout risk and reorder suggestion
        stockout_30d = {}
        for asin, sold_today in today_sales.items():
            stock = stock_info.get(asin)
            if not stock:
                continue
            try:
                current_stock = float(stock.get('FBA/FBM Stock', 0))
            except Exception:
                current_stock = 0
            days_left = current_stock / max(sold_today, 1)
            if days_left < 30:
                suggested_reorder = max(0, int((30 * sold_today) - current_stock))
                stockout_30d[asin] = {
                    "title": stock.get('Title', ''),
                    "sold_today": sold_today,
                    "current_stock": current_stock,
                    "days_left": round(days_left, 1),
                    "suggested_reorder": suggested_reorder
                }

        return {
            "today_sales": today_sales,
            "velocity": velocity,
            "low_stock": low_stock,
            "restock_priority": restock_priority,
            "stock_info": stock_info,
            "orders_df": today_orders,
            "stockout_30d": stockout_30d,
        } 