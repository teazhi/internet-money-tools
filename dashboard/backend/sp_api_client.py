"""
Amazon SP-API Client for Dashboard
Provides integration with Amazon Seller Partner API to replace Sellerboard data
"""

import os
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
import logging

try:
    from sp_api.api import Orders, Inventories, Reports, CatalogItems
    from sp_api.base import Marketplaces, SellingApiForbiddenException, SellingApiException
    SP_API_AVAILABLE = True
    print("[SP-API] Successfully imported python-amazon-sp-api")
except ImportError as e:
    print(f"[SP-API] ImportError: {e}")
    print("[SP-API] python-amazon-sp-api not installed. Install with: pip install python-amazon-sp-api==1.8.22")
    SP_API_AVAILABLE = False
except Exception as e:
    print(f"[SP-API] Unexpected error importing SP-API: {e}")
    SP_API_AVAILABLE = False

logger = logging.getLogger(__name__)

# Debug: Check if the package is installed and what's available
try:
    import sp_api
    print(f"[SP-API] SP-API package location: {sp_api.__file__}")
    
    from sp_api import api
    available_apis = [attr for attr in dir(api) if not attr.startswith('_')]
    print(f"[SP-API] Available APIs: {available_apis}")
    
except Exception as debug_error:
    print(f"[SP-API] Debug error: {debug_error}")

try:
    import pkg_resources
    try:
        sp_api_version = pkg_resources.get_distribution("python-amazon-sp-api").version
        print(f"[SP-API] Found python-amazon-sp-api version: {sp_api_version}")
    except pkg_resources.DistributionNotFound:
        print("[SP-API] python-amazon-sp-api package not found in installed packages")
except ImportError:
    print("[SP-API] pkg_resources not available for version checking")

class SPAPIClient:
    """Amazon SP-API Client wrapper"""
    
    def __init__(self, refresh_token=None, marketplace='ATVPDKIKX0DER'):  # Default to US marketplace
        """
        Initialize SP-API client
        
        Args:
            refresh_token: User's Amazon refresh token (if None, will try environment)
            marketplace: Amazon marketplace ID (default: US)
        """
        if not SP_API_AVAILABLE:
            raise ImportError("python-amazon-sp-api package not installed")
            
        # Get credentials - prefer user token over environment
        self.refresh_token = refresh_token or os.getenv('SP_API_REFRESH_TOKEN')
        self.lwa_app_id = os.getenv('SP_API_LWA_APP_ID') 
        self.lwa_client_secret = os.getenv('SP_API_LWA_CLIENT_SECRET')
        self.marketplace_id = marketplace
        
        # Validate required credentials
        if not all([self.refresh_token, self.lwa_app_id, self.lwa_client_secret]):
            raise ValueError("Missing required SP-API credentials. Need refresh_token, SP_API_LWA_APP_ID, and SP_API_LWA_CLIENT_SECRET")
        
        # Initialize API clients
        self.credentials = {
            'refresh_token': self.refresh_token,
            'lwa_app_id': self.lwa_app_id,
            'lwa_client_secret': self.lwa_client_secret,
        }
        
        # Set marketplace
        if marketplace == 'ATVPDKIKX0DER':
            self.marketplace = Marketplaces.US
        elif marketplace == 'A1PA6795UKMFR9':
            self.marketplace = Marketplaces.DE
        elif marketplace == 'A1RKKUPIHCS9HS':
            self.marketplace = Marketplaces.ES
        else:
            self.marketplace = Marketplaces.US  # Default fallback
            
        print(f"[SP-API] Initialized client for marketplace: {self.marketplace}")

    def get_orders(self, start_date: datetime, end_date: datetime = None) -> List[Dict[str, Any]]:
        """
        Get orders from SP-API Orders endpoint
        
        Args:
            start_date: Start date for orders query
            end_date: End date for orders query (default: now)
            
        Returns:
            List of order dictionaries
        """
        if not end_date:
            end_date = datetime.now(timezone.utc)
            
        try:
            orders_client = Orders(credentials=self.credentials, marketplace=self.marketplace)
            
            # Convert dates to ISO format
            start_iso = start_date.isoformat()
            end_iso = end_date.isoformat()
            
            print(f"[SP-API] Fetching orders from {start_iso} to {end_iso}")
            
            # Get orders
            response = orders_client.get_orders(
                MarketplaceIds=[self.marketplace_id],
                CreatedAfter=start_iso,
                CreatedBefore=end_iso,
                OrderStatuses=['Unshipped', 'PartiallyShipped', 'Shipped', 'Canceled', 'Unfulfillable']
            )
            
            orders = []
            if hasattr(response, 'payload') and response.payload:
                orders_data = response.payload.get('Orders', [])
                
                for order in orders_data:
                    # Get order items for each order
                    try:
                        items_response = orders_client.get_order_items(order['AmazonOrderId'])
                        order_items = []
                        
                        if hasattr(items_response, 'payload') and items_response.payload:
                            order_items = items_response.payload.get('OrderItems', [])
                            
                        # Process and format order data to match expected structure
                        processed_order = self._process_order(order, order_items)
                        orders.append(processed_order)
                        
                    except Exception as e:
                        logger.warning(f"Failed to get items for order {order['AmazonOrderId']}: {e}")
                        # Add order without items as fallback
                        processed_order = self._process_order(order, [])
                        orders.append(processed_order)
            
            print(f"[SP-API] Retrieved {len(orders)} orders")
            return orders
            
        except SellingApiForbiddenException as e:
            logger.error(f"SP-API Forbidden: {e}")
            raise Exception("Access denied to SP-API. Check your seller account permissions.")
        except SellingApiException as e:
            logger.error(f"SP-API Error: {e}")
            raise Exception(f"SP-API request failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected error fetching orders: {e}")
            raise Exception(f"Failed to fetch orders: {e}")

    def get_inventory_summary(self) -> List[Dict[str, Any]]:
        """
        Get inventory summary from SP-API FBA Inventory
        
        Returns:
            List of inventory items with stock levels
        """
        try:
            inventory_client = Inventories(credentials=self.credentials, marketplace=self.marketplace)
            
            print("[SP-API] Fetching inventory summary")
            
            # Try different method signatures for different versions
            try:
                response = inventory_client.get_inventory_summaries(
                    granularityType='Marketplace',
                    granularityId=self.marketplace_id,
                    marketplaceIds=[self.marketplace_id]
                )
            except Exception as method_error:
                print(f"[SP-API] First inventory method failed: {method_error}")
                # Try alternative method signature
                response = inventory_client.get_inventory_summaries(
                    granularity_type='Marketplace',
                    granularity_id=self.marketplace_id,
                    marketplace_ids=[self.marketplace_id]
                )
            
            inventory = []
            if hasattr(response, 'payload') and response.payload:
                inventory_data = response.payload.get('inventorySummaries', [])
                
                for item in inventory_data:
                    processed_item = self._process_inventory_item(item)
                    inventory.append(processed_item)
            
            print(f"[SP-API] Retrieved {len(inventory)} inventory items")
            return inventory
            
        except SellingApiForbiddenException as e:
            logger.error(f"SP-API Inventory Forbidden: {e}")
            raise Exception("Access denied to SP-API Inventory. Check your seller account permissions.")
        except SellingApiException as e:
            logger.error(f"SP-API Inventory Error: {e}")
            raise Exception(f"SP-API inventory request failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected error fetching inventory: {e}")
            raise Exception(f"Failed to fetch inventory: {e}")

    def get_product_details(self, asin: str) -> Optional[Dict[str, Any]]:
        """
        Get product details from SP-API Catalog Items
        
        Args:
            asin: Product ASIN
            
        Returns:
            Product details dictionary or None
        """
        try:
            catalog_client = CatalogItems(credentials=self.credentials, marketplace=self.marketplace)
            
            response = catalog_client.get_catalog_item(
                asin=asin,
                MarketplaceId=self.marketplace_id,
                includedData=['attributes', 'dimensions', 'identifiers', 'images', 'productTypes', 'salesRanks', 'summaries']
            )
            
            if hasattr(response, 'payload') and response.payload:
                return self._process_catalog_item(response.payload)
                
            return None
            
        except Exception as e:
            logger.warning(f"Failed to get product details for {asin}: {e}")
            return None

    def _process_order(self, order: Dict, order_items: List[Dict]) -> Dict[str, Any]:
        """Process and format order data to match expected structure"""
        
        # Calculate total amount from order items
        total_amount = 0
        asins = []
        quantities = {}
        
        for item in order_items:
            asin = item.get('ASIN', '')
            quantity = int(item.get('QuantityOrdered', 0))
            
            if asin:
                asins.append(asin)
                quantities[asin] = quantities.get(asin, 0) + quantity
                
            # Sum up item price
            item_price = item.get('ItemPrice', {})
            if item_price and 'Amount' in item_price:
                total_amount += float(item_price['Amount']) * quantity
        
        # Format order to match Sellerboard structure
        processed_order = {
            'AmazonOrderId': order.get('AmazonOrderId', ''),
            'OrderDate': order.get('PurchaseDate', ''),
            'OrderStatus': order.get('OrderStatus', ''),
            'OrderTotalAmount': total_amount,
            'order_total_amount': total_amount,  # Alternative field name
            'Revenue': total_amount,  # Alternative field name
            'ASIN': ','.join(asins),  # Multiple ASINs combined
            'ASINs': asins,  # List of ASINs
            'Quantities': quantities,  # ASIN -> quantity mapping
            'TotalQuantity': sum(quantities.values()),
            'ShippingAddress': {
                'City': order.get('ShippingAddress', {}).get('City', ''),
                'StateOrRegion': order.get('ShippingAddress', {}).get('StateOrRegion', ''),
                'CountryCode': order.get('ShippingAddress', {}).get('CountryCode', '')
            },
            'MarketplaceId': order.get('MarketplaceId', ''),
            'Currency': order.get('OrderTotal', {}).get('CurrencyCode', 'USD'),
            'OrderItems': order_items
        }
        
        return processed_order

    def _process_inventory_item(self, item: Dict) -> Dict[str, Any]:
        """Process inventory item to match expected structure"""
        
        asin = item.get('asin', '')
        condition = item.get('condition', 'NewItem')
        
        # Get different stock levels
        total_quantity = 0
        inbound_quantity = 0
        available_quantity = 0
        
        # Parse inventory details
        inventory_details = item.get('inventoryDetails', {})
        fulfillable_quantity = inventory_details.get('fulfillableQuantity', 0)
        inbound_working_quantity = inventory_details.get('inboundWorkingQuantity', 0)
        inbound_shipped_quantity = inventory_details.get('inboundShippedQuantity', 0)
        inbound_receiving_quantity = inventory_details.get('inboundReceivingQuantity', 0)
        
        total_quantity = fulfillable_quantity + inbound_working_quantity + inbound_shipped_quantity + inbound_receiving_quantity
        available_quantity = fulfillable_quantity
        inbound_quantity = inbound_working_quantity + inbound_shipped_quantity + inbound_receiving_quantity
        
        processed_item = {
            'asin': asin,
            'ASIN': asin,  # Alternative field name
            'condition': condition,
            'totalQuantity': total_quantity,
            'total_quantity': total_quantity,  # Alternative field name
            'availableQuantity': available_quantity,
            'available_quantity': available_quantity,  # Alternative field name
            'inboundQuantity': inbound_quantity,
            'inbound_quantity': inbound_quantity,  # Alternative field name
            'fulfillableQuantity': fulfillable_quantity,
            'lastUpdatedTime': item.get('lastUpdatedTime', ''),
            'productName': item.get('productName', ''),
            'sellerSku': item.get('sellerSku', ''),
            'inventoryDetails': inventory_details
        }
        
        return processed_item

    def _process_catalog_item(self, catalog_data: Dict) -> Dict[str, Any]:
        """Process catalog item data"""
        
        attributes = catalog_data.get('attributes', {})
        summaries = catalog_data.get('summaries', [])
        
        # Get product name from summaries or attributes
        product_name = ''
        if summaries:
            product_name = summaries[0].get('itemName', '')
        
        if not product_name and 'item_name' in attributes:
            product_name = attributes['item_name'][0].get('value', '') if attributes['item_name'] else ''
        
        processed_item = {
            'asin': catalog_data.get('asin', ''),
            'productName': product_name,
            'product_name': product_name,  # Alternative field name
            'attributes': attributes,
            'summaries': summaries,
            'dimensions': catalog_data.get('dimensions', []),
            'identifiers': catalog_data.get('identifiers', []),
            'images': catalog_data.get('images', []),
            'productTypes': catalog_data.get('productTypes', []),
            'salesRanks': catalog_data.get('salesRanks', [])
        }
        
        return processed_item

def create_sp_api_client(refresh_token=None, marketplace_id: str = 'ATVPDKIKX0DER') -> Optional[SPAPIClient]:
    """
    Create and return SP-API client instance
    
    Args:
        refresh_token: User's Amazon refresh token (if None, will try environment)
        marketplace_id: Amazon marketplace ID
        
    Returns:
        SPAPIClient instance or None if unavailable
    """
    try:
        if not SP_API_AVAILABLE:
            print("[SP-API] SP-API library not available")
            return None
            
        client = SPAPIClient(refresh_token, marketplace_id)
        print("[SP-API] Client created successfully")
        return client
        
    except Exception as e:
        print(f"[SP-API] Failed to create client: {e}")
        return None

def test_sp_api_connection() -> bool:
    """
    Test SP-API connection and credentials
    
    Returns:
        True if connection successful, False otherwise
    """
    try:
        client = create_sp_api_client()
        if not client:
            return False
            
        # Try to get a small inventory sample to test connection
        inventory = client.get_inventory_summary()
        print(f"[SP-API] Connection test successful. Found {len(inventory)} inventory items.")
        return True
        
    except Exception as e:
        print(f"[SP-API] Connection test failed: {e}")
        return False

if __name__ == "__main__":
    # Test the SP-API connection
    print("Testing SP-API connection...")
    success = test_sp_api_connection()
    if success:
        print("✅ SP-API connection successful!")
    else:
        print("❌ SP-API connection failed!")