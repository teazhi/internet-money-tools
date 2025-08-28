#!/usr/bin/env python3
"""
Debug script to examine the actual CSV structure and stock extraction
"""
import requests
import pandas as pd
from io import StringIO

def debug_csv_structure():
    """Debug the actual CSV structure from Sellerboard"""
    url = "https://app.sellerboard.com/en/automation/reports?id=171f0ae5a4a449b88e0449ffacfe2499&format=csv&t=be4a1dbeb5e949d1a0f750f569db4362"
    
    print("🔍 Debugging Sellerboard CSV Structure")
    print("=" * 60)
    
    try:
        # Download CSV
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        # Parse CSV
        df = pd.read_csv(StringIO(response.text))
        
        print(f"✅ CSV loaded successfully")
        print(f"📊 Shape: {df.shape[0]} rows, {df.shape[1]} columns")
        print()
        
        # Show all column names
        print("📋 All Column Headers:")
        for i, col in enumerate(df.columns, 1):
            print(f"  {i:2d}. '{col}'")
        print()
        
        # Check for stock-related columns specifically
        stock_columns = [col for col in df.columns if 'stock' in col.lower()]
        print("📦 Stock-related columns found:")
        for col in stock_columns:
            print(f"  - '{col}'")
        print()
        
        # Check for ASIN column
        asin_col = None
        for col in df.columns:
            if 'asin' in col.lower():
                asin_col = col
                print(f"🎯 ASIN column found: '{col}'")
                break
        
        if not asin_col:
            print("❌ No ASIN column found!")
            return
        
        # Check for FBA/FBM Stock specifically  
        fba_fbm_col = None
        for col in df.columns:
            if col == 'FBA/FBM Stock':
                fba_fbm_col = col
                print(f"✅ FBA/FBM Stock column found: '{col}'")
                break
        
        if not fba_fbm_col:
            print("❌ FBA/FBM Stock column not found!")
            print("Available stock columns:")
            for col in stock_columns:
                print(f"  - '{col}'")
            return
        
        # Show sample data for first 5 ASINs
        print("\n📋 Sample Stock Data (first 5 products):")
        print("-" * 60)
        
        for i in range(min(5, len(df))):
            row = df.iloc[i]
            asin = row[asin_col]
            stock = row[fba_fbm_col]
            title = row.get('Title', 'No title')[:50] + '...' if len(str(row.get('Title', 'No title'))) > 50 else row.get('Title', 'No title')
            
            print(f"ASIN: {asin}")
            print(f"  Title: {title}")  
            print(f"  FBA/FBM Stock: {stock} (type: {type(stock)})")
            
            # Test the extract logic
            try:
                stock_val = str(stock).replace(',', '').strip()
                if stock_val and stock_val.lower() not in ['nan', 'none', '', 'null']:
                    current_stock = float(stock_val)
                    if current_stock >= 0:
                        print(f"  ✅ Extracted: {current_stock}")
                    else:
                        print(f"  ⚠️  Negative stock: {current_stock}")
                else:
                    print(f"  ❌ Invalid stock value: '{stock_val}'")
            except (ValueError, TypeError) as e:
                print(f"  ❌ Parse error: {e}")
            print()
        
        # Check if there are any non-zero stock values in the entire dataset
        non_zero_stock = df[df[fba_fbm_col] > 0]
        print(f"📈 Products with stock > 0: {len(non_zero_stock)}/{len(df)}")
        
        if len(non_zero_stock) > 0:
            print("Sample products with stock:")
            for i in range(min(3, len(non_zero_stock))):
                row = non_zero_stock.iloc[i]
                print(f"  {row[asin_col]}: {row[fba_fbm_col]} units")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    debug_csv_structure()