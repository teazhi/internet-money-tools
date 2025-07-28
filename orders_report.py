import requests
import pandas as pd
from io import StringIO
from datetime import datetime, date, timezone
from typing import Dict, Optional

REPORT_URL = "https://app.sellerboard.com/en/automation/reports?id=e0989fcf9a9e40b8a116318d4fd7ee84&format=csv&t=51d64bf0615c47c69cc99b166f8e6beb"

class OrdersReport:
    def __init__(self, report_url: Optional[str] = None):
        self.report_url = report_url or REPORT_URL

    def _parse_datetime_robust(self, series: pd.Series, column_name: str) -> pd.Series:
        """Robust datetime parsing that tries multiple formats"""
        print(f"[DEBUG] Parsing datetime column '{column_name}' with {len(series)} values")
        
        # Common datetime formats from Sellerboard and other sources
        formats_to_try = [
            "%m/%d/%Y %I:%M:%S %p",  # 07/28/2025 02:30:45 PM (current format)
            "%m/%d/%Y %H:%M:%S",     # 07/28/2025 14:30:45 (24-hour)
            "%Y-%m-%d %H:%M:%S",     # 2025-07-28 14:30:45 (ISO-like)
            "%Y-%m-%d %I:%M:%S %p",  # 2025-07-28 02:30:45 PM
            "%m/%d/%Y",              # 07/28/2025 (date only)  
            "%Y-%m-%d",              # 2025-07-28 (ISO date)
            "%d/%m/%Y %I:%M:%S %p",  # 28/07/2025 02:30:45 PM (EU format)
            "%d/%m/%Y %H:%M:%S",     # 28/07/2025 14:30:45 (EU 24-hour)
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

    def download_csv_report(self) -> pd.DataFrame:
        response = requests.get(self.report_url, timeout=30)
        response.raise_for_status()
        df = pd.read_csv(StringIO(response.text))
        return df

    def process_orders(self, df: pd.DataFrame, for_date: Optional[date] = None) -> Dict[str, int]:
        if for_date is None:
            for_date = date.today()
        date_columns = [col for col in df.columns if 'date' in col.lower() or 'time' in col.lower()]
        if not date_columns:
            filtered_df = df
        else:
            date_col = date_columns[0]
            # Specify format for PurchaseDate(UTC)
            if date_col == 'PurchaseDate(UTC)':
                # Try multiple datetime formats for PurchaseDate(UTC)
                df[date_col] = self._parse_datetime_robust(df[date_col], date_col)
            else:
                df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
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
        product_col = None
        for col in df.columns:
            if 'product' in col.lower() or 'asin' in col.lower():
                product_col = col
                break
        if not product_col:
            raise ValueError("Products column not found in CSV.")
        asin_counts = filtered_df[product_col].value_counts().to_dict()
        return asin_counts

    def make_summary_embed(self, asin_counts: Dict[str, int], for_date: date) -> dict:
        if not asin_counts:
            description = "No orders found for this date with Shipped/Unshipped status."
            color = 0xFF6B6B
        else:
            total_orders = sum(asin_counts.values())
            asin_list = [f"• **{asin}**: {count} orders" for asin, count in sorted(asin_counts.items(), key=lambda x: x[1], reverse=True)]
            description = f"**Total Orders**: {total_orders}\n\n**ASIN Breakdown**:\n" + "\n".join(asin_list)
            color = 0x4CAF50
        return {
            "title": f"📊 Orders Summary - {for_date.strftime('%Y-%m-%d')}",
            "description": description,
            "color": color
        } 