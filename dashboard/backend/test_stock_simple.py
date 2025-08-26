#!/usr/bin/env python3
"""
Simple test to verify stock extraction from Sellerboard CSV
"""
import requests
import pandas as pd
from io import StringIO

def test_stock_extraction(stock_url, test_asins):
    """Test direct stock extraction from Sellerboard URL"""
    
    print(f"Testing stock extraction from: {stock_url}")
    print(f"Testing ASINs: {test_asins}")
    print("-" * 50)
    
    # Download CSV
    response = requests.get(stock_url, timeout=30)
    response.raise_for_status()
    
    # Parse CSV
    df = pd.read_csv(StringIO(response.text))
    
    print(f"CSV has {len(df)} rows and {len(df.columns)} columns")
    print(f"Columns: {list(df.columns)}")
    print("-" * 50)
    
    # Find ASIN column
    asin_col = None
    for col in df.columns:
        if 'ASIN' in col.upper():
            asin_col = col
            break
    
    if not asin_col:
        print("ERROR: No ASIN column found!")
        return
    
    print(f"Using ASIN column: '{asin_col}'")
    
    # Find stock columns
    stock_cols = []
    for col in df.columns:
        if any(keyword in col.lower() for keyword in ['stock', 'inventory', 'qty', 'quantity']):
            stock_cols.append(col)
    
    print(f"Stock-related columns found: {stock_cols}")
    print("-" * 50)
    
    # Test each ASIN
    for asin in test_asins:
        print(f"\nTesting ASIN: {asin}")
        
        # Find row
        asin_rows = df[df[asin_col].astype(str).str.strip() == asin]
        
        if asin_rows.empty:
            print(f"  NOT FOUND in CSV")
        else:
            row = asin_rows.iloc[0]
            print(f"  Found in row {asin_rows.index[0]}")
            
            # Show stock values
            for col in stock_cols:
                value = row[col]
                print(f"  {col}: {value}")
            
            # Try to extract numeric stock
            stock_value = 0
            for col in ['FBA/FBM Stock', 'Stock', 'Inventory']:
                if col in df.columns:
                    try:
                        val = str(row[col]).replace(',', '')
                        stock_value = float(val)
                        print(f"  => Extracted stock: {stock_value} from column '{col}'")
                        break
                    except:
                        pass
            
            if stock_value == 0:
                print(f"  => Could not extract numeric stock value")

if __name__ == "__main__":
    # Example usage
    stock_url = "YOUR_SELLERBOARD_STOCK_URL_HERE"
    test_asins = ["B01ABC123", "B02XYZ456"]  # Replace with actual ASINs
    
    test_stock_extraction(stock_url, test_asins)