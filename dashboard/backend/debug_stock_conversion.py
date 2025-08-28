#!/usr/bin/env python3
"""
Debug script to test the stock conversion process in get_stock_info
"""
import requests
import pandas as pd
import numpy as np
from io import StringIO

def debug_stock_conversion():
    """Debug the stock conversion process"""
    url = "https://app.sellerboard.com/en/automation/reports?id=171f0ae5a4a449b88e0449ffacfe2499&format=csv&t=be4a1dbeb5e949d1a0f750f569db4362"
    
    print("🔍 Debugging Stock Conversion Process")
    print("=" * 60)
    
    try:
        # Download and parse CSV
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        df = pd.read_csv(StringIO(response.text))
        
        # Test the conversion logic with first product that has stock
        non_zero_stock = df[df['FBA/FBM Stock'] > 0]
        if non_zero_stock.empty:
            print("❌ No products with stock > 0 found")
            return
            
        test_row = non_zero_stock.iloc[0]
        asin = test_row['ASIN']
        original_stock = test_row['FBA/FBM Stock']
        
        print(f"🧪 Testing with ASIN: {asin}")
        print(f"📊 Original stock value: {original_stock} (type: {type(original_stock)})")
        
        # Simulate the get_stock_info conversion process
        row_dict = test_row.to_dict()
        print(f"🔄 After to_dict(): {row_dict['FBA/FBM Stock']} (type: {type(row_dict['FBA/FBM Stock'])})")
        
        # Test the serialization logic
        value = row_dict['FBA/FBM Stock']
        serialized_value = value
        
        if hasattr(value, 'item'):  # numpy scalar
            serialized_value = value.item()
            print(f"🔄 After .item(): {serialized_value} (type: {type(serialized_value)})")
        elif hasattr(value, 'to_pydatetime'):  # pandas timestamp
            serialized_value = value.to_pydatetime().isoformat()
            print(f"🔄 After to_pydatetime(): {serialized_value}")
        elif str(type(value)).startswith('<class \'pandas.'):  # other pandas types
            serialized_value = str(value)
            print(f"🔄 After str() (pandas): {serialized_value} (type: {type(serialized_value)})")
        elif str(type(value)).startswith('<class \'numpy.'):  # other numpy types
            serialized_value = str(value)
            print(f"🔄 After str() (numpy): {serialized_value} (type: {type(serialized_value)})")
        
        print(f"✅ Final serialized value: {serialized_value} (type: {type(serialized_value)})")
        
        # Test the extract_current_stock logic on the serialized value
        stock_info = {'FBA/FBM Stock': serialized_value}
        print(f"\n🧪 Testing extract_current_stock logic:")
        print(f"📋 stock_info: {stock_info}")
        
        # Simulate extract_current_stock
        if 'FBA/FBM Stock' in stock_info:
            try:
                stock_val = str(stock_info['FBA/FBM Stock']).replace(',', '').strip()
                print(f"🔄 After string processing: '{stock_val}'")
                
                if stock_val and stock_val.lower() not in ['nan', 'none', '', 'null', '']:
                    current_stock = float(stock_val)
                    print(f"🔄 After float(): {current_stock}")
                    
                    if current_stock >= 0:
                        print(f"✅ Final extracted stock: {current_stock}")
                    else:
                        print(f"❌ Negative stock: {current_stock}")
                else:
                    print(f"❌ Invalid stock value: '{stock_val}'")
            except (ValueError, TypeError) as e:
                print(f"❌ Parse error: {e}")
        else:
            print("❌ FBA/FBM Stock key not found in stock_info")
            
        # Test with multiple products to make sure conversion is consistent
        print(f"\n📊 Testing multiple products:")
        print("-" * 40)
        
        for i in range(min(5, len(non_zero_stock))):
            row = non_zero_stock.iloc[i]
            asin = row['ASIN']
            original = row['FBA/FBM Stock']
            
            # Simulate full conversion
            row_dict = row.to_dict()
            value = row_dict['FBA/FBM Stock']
            
            if hasattr(value, 'item'):
                final_value = value.item()
            else:
                final_value = value
                
            print(f"  {asin}: {original} → {final_value} (types: {type(original).__name__} → {type(final_value).__name__})")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_stock_conversion()