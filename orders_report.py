import requests
import pandas as pd
from io import StringIO
from datetime import datetime, date, timezone
from typing import Dict, Optional

REPORT_URL = "https://app.sellerboard.com/en/automation/reports?id=e0989fcf9a9e40b8a116318d4fd7ee84&format=csv&t=51d64bf0615c47c69cc99b166f8e6beb"

class OrdersReport:
    def __init__(self, report_url: Optional[str] = None):
        self.report_url = report_url or REPORT_URL

    def download_csv_report(self) -> pd.DataFrame:
        response = requests.get(self.report_url, timeout=30)
        response.raise_for_status()
        df = pd.read_csv(StringIO(response.text))
        return df

    def process_orders(self, df: pd.DataFrame, for_date: Optional[date] = None) -> Dict[str, int]:
        # Use today's date if not specified
        if for_date is None:
            for_date = date.today()
        # Find the date column
        date_columns = [col for col in df.columns if 'date' in col.lower() or 'time' in col.lower()]
        if not date_columns:
            filtered_df = df
        else:
            date_col = date_columns[0]
            df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
            filtered_df = df[df[date_col].dt.date == for_date]
        # Find the order status column
        status_col = None
        for col in df.columns:
            if col.lower().replace(' ', '') == 'orderstatus':
                status_col = col
                break
        if not status_col:
            raise ValueError("OrderStatus column not found in CSV.")
        filtered_df = filtered_df[filtered_df[status_col].isin(['Shipped', 'Unshipped'])]
        # Find the products/ASIN column
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