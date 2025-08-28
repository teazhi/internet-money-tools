#!/usr/bin/env python3
"""
Test the full flow of stock extraction without authentication
"""
from orders_analysis import OrdersAnalysis
import requests
import pandas as pd
from io import StringIO

def test_full_stock_flow():
    """Test the complete stock extraction flow"""
    
    print("🔍 Testing Full Stock Extraction Flow")
    print("=" * 60)
    
    # Test URLs
    stock_url = "https://app.sellerboard.com/en/automation/reports?id=171f0ae5a4a449b88e0449ffacfe2499&format=csv&t=be4a1dbeb5e949d1a0f750f569db4362"
    
    try:
        # Create OrdersAnalysis instance
        analyzer = OrdersAnalysis(orders_url="dummy", stock_url=stock_url)
        
        # Test 1: Download CSV
        print("📥 Step 1: Download CSV...")
        stock_df = analyzer.download_csv(stock_url)
        print(f"✅ Downloaded CSV: {stock_df.shape[0]} rows, {stock_df.shape[1]} columns")
        
        # Test 2: Get stock info (convert DataFrame to dict)
        print("\n📋 Step 2: Convert to stock_info dict...")
        stock_info = analyzer.get_stock_info(stock_df)
        print(f"✅ Created stock_info dict with {len(stock_info)} products")
        
        # Test 3: Check a few products for stock values
        print("\n🧪 Step 3: Test stock extraction for specific ASINs...")
        
        # Get sample ASINs from the data
        sample_asins = list(stock_info.keys())[:5]
        
        for asin in sample_asins:
            product_info = stock_info[asin]
            extracted_stock = analyzer.extract_current_stock(product_info, debug_asin=asin)
            
            # Also check what's in the raw data
            raw_fba_fbm = product_info.get('FBA/FBM Stock', 'NOT FOUND')
            
            print(f"  ASIN: {asin}")
            print(f"    Raw FBA/FBM Stock: {raw_fba_fbm} (type: {type(raw_fba_fbm)})")
            print(f"    Extracted stock: {extracted_stock}")
            print(f"    Title: {product_info.get('Title', 'No title')[:50]}...")
            print()
        
        # Test 4: Check the stock_info structure for FBA/FBM Stock key
        print("\n🔍 Step 4: Verify FBA/FBM Stock key exists...")
        sample_product = stock_info[list(stock_info.keys())[0]]
        print(f"📋 Keys in sample product: {list(sample_product.keys())[:10]}")
        
        has_fba_fbm = 'FBA/FBM Stock' in sample_product
        print(f"✅ Has 'FBA/FBM Stock' key: {has_fba_fbm}")
        
        if has_fba_fbm:
            sample_stock_value = sample_product['FBA/FBM Stock']
            print(f"📊 Sample stock value: {sample_stock_value} (type: {type(sample_stock_value)})")
        
        # Test 5: Check if there are any products with stock > 0
        print(f"\n📈 Step 5: Count products with stock...")
        products_with_stock = 0
        total_stock = 0
        
        for asin, info in stock_info.items():
            stock = analyzer.extract_current_stock(info)
            if stock > 0:
                products_with_stock += 1
                total_stock += stock
        
        print(f"📊 Products with stock > 0: {products_with_stock}/{len(stock_info)}")
        print(f"📊 Total stock across all products: {total_stock}")
        
        if products_with_stock > 0:
            print(f"📊 Average stock per product with inventory: {total_stock/products_with_stock:.1f}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_full_stock_flow()