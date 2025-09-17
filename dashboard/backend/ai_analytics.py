"""
AI Analytics Integration Module using Keywords.ai
Provides intelligent insights for e-commerce analytics
"""

import os
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# Keywords.ai integration with import error handling
KeywordsAI = None
import_status = "unknown"

# Strategy 1: Fix the import error by pre-patching missing Evaluator
try:
    # Pre-patch the missing Evaluator class to fix import error
    import sys
    import types
    
    # Create the missing module structure if it doesn't exist
    if 'keywordsai_sdk' not in sys.modules:
        keywordsai_sdk = types.ModuleType('keywordsai_sdk')
        sys.modules['keywordsai_sdk'] = keywordsai_sdk
    
    if 'keywordsai_sdk.keywordsai_types' not in sys.modules:
        keywordsai_types = types.ModuleType('keywordsai_sdk.keywordsai_types')
        sys.modules['keywordsai_sdk.keywordsai_types'] = keywordsai_types
    
    if 'keywordsai_sdk.keywordsai_types.dataset_types' not in sys.modules:
        dataset_types = types.ModuleType('keywordsai_sdk.keywordsai_types.dataset_types')
        
        # Add the missing Evaluator class
        class Evaluator:
            pass
        
        dataset_types.Evaluator = Evaluator
        sys.modules['keywordsai_sdk.keywordsai_types.dataset_types'] = dataset_types
    
    # Now try importing
    from keywordsai import KeywordsAI
    print("✅ Keywords.ai SDK imported successfully (with patch)")
    import_status = "success_patched"
    
except ImportError as e:
    print(f"❌ Patched import still failed: {e}")
    import_status = f"patch_failed: {e}"
    
    # Strategy 2: Try importing just the core client
    try:
        # Try importing the minimal client directly
        import requests
        
        class SimpleKeywordsAI:
            def __init__(self, api_key):
                self.api_key = api_key
                self.base_url = "https://api.keywordsai.co"
                
            def generate(self, messages, model="gpt-4-turbo-preview", **kwargs):
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                
                data = {
                    "model": model,
                    "messages": messages,
                    **kwargs
                }
                
                response = requests.post(
                    f"{self.base_url}/v1/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=30
                )
                response.raise_for_status()
                return response.json()
        
        KeywordsAI = SimpleKeywordsAI
        print("✅ Using simplified Keywords.ai client")
        import_status = "success_simple"
        
    except Exception as e2:
        print(f"❌ Simplified client also failed: {e2}")
        import_status = f"all_failed: {e} | {e2}"
        
except Exception as e:
    print(f"❌ Unexpected error with patch approach: {e}")
    import_status = f"patch_error: {e}"

class AIAnalytics:
    def _parse_response(self, response, as_json=True):
        """Parse response from either official SDK or simplified client"""
        try:
            # Get the content from response
            content = None
            if hasattr(response, 'choices'):
                # Official SDK response format
                content = response.choices[0].message.content
            elif isinstance(response, dict) and 'choices' in response:
                # Simplified client response format
                content = response['choices'][0]['message']['content']
            else:
                print(f"Unexpected response format: {response}")
                return {} if as_json else ""
            
            if as_json:
                return json.loads(content)
            else:
                return content
                
        except Exception as e:
            print(f"Error parsing AI response: {e}")
            return {} if as_json else ""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize AI Analytics with Keywords.ai"""
        self.api_key = api_key or os.getenv('KEYWORDS_AI_API_KEY')
        self.client = None
        
        # Debug information
        print(f"AI Analytics initialization:")
        print(f"  - KeywordsAI SDK available: {KeywordsAI is not None}")
        print(f"  - API key provided: {'Yes' if self.api_key else 'No'}")
        if self.api_key:
            print(f"  - API key starts with: {self.api_key[:8]}...")
        
        if KeywordsAI and self.api_key:
            try:
                self.client = KeywordsAI(api_key=self.api_key)
                print("  ✅ AI Analytics enabled successfully")
            except Exception as e:
                print(f"  ❌ Failed to initialize Keywords.ai client: {e}")
        else:
            reasons = []
            if not KeywordsAI:
                reasons.append("KeywordsAI SDK not available")
            if not self.api_key:
                reasons.append("No API key found")
            print(f"  ❌ AI Analytics disabled - {', '.join(reasons)}")
    
    def generate_order_insights(self, orders_df: pd.DataFrame, cogs_data: Dict[str, dict]) -> Dict[str, Any]:
        """Generate AI-powered insights from order data"""
        if not self.client or orders_df.empty:
            return {"insights": [], "recommendations": []}
        
        # Prepare data summary for AI analysis
        summary = self._prepare_data_summary(orders_df, cogs_data)
        
        try:
            prompt = f"""
            Analyze this e-commerce sales data and provide actionable insights:
            
            Sales Summary:
            {json.dumps(summary['sales_metrics'], indent=2)}
            
            Top Products:
            {json.dumps(summary['top_products'][:10], indent=2)}
            
            Profit Analysis:
            {json.dumps(summary['profit_metrics'], indent=2)}
            
            Time Patterns:
            {json.dumps(summary['time_patterns'], indent=2)}
            
            Please provide:
            1. 3-5 key insights about the business performance
            2. 3 specific recommendations for improving profitability
            3. Any concerning trends or anomalies
            4. Opportunities for growth
            
            Format as JSON with keys: insights, recommendations, warnings, opportunities
            """
            
            response = self.client.generate(
                messages=[{"role": "user", "content": prompt}],
                model="gpt-4-turbo-preview",
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            
            return self._parse_response(response, as_json=True)
            
        except Exception as e:
            print(f"AI insights generation failed: {e}")
            return {"insights": [], "recommendations": []}
    
    def predict_restocking_needs(self, orders_df: pd.DataFrame, stock_levels: Dict[str, int], 
                                lead_time_days: int = 90) -> List[Dict[str, Any]]:
        """AI-powered predictive restocking recommendations"""
        if not self.client or orders_df.empty:
            return []
        
        # Calculate sales velocity and trends
        velocity_data = self._calculate_sales_velocity(orders_df)
        
        try:
            prompt = f"""
            Based on this sales and inventory data, provide restocking recommendations:
            
            Sales Velocity (units/day):
            {json.dumps(velocity_data[:20], indent=2)}
            
            Current Stock Levels:
            {json.dumps(stock_levels, indent=2)}
            
            Lead Time: {lead_time_days} days
            
            Consider:
            - Historical sales patterns
            - Current velocity trends
            - Seasonal factors
            - Stock runout risk
            
            Provide recommendations as JSON array with:
            - asin
            - product_name
            - recommended_order_quantity
            - urgency (critical/high/medium/low)
            - reasoning
            - estimated_runout_days
            """
            
            response = self.client.generate(
                messages=[{"role": "user", "content": prompt}],
                model="gpt-4-turbo-preview",
                temperature=0.5,
                response_format={"type": "json_object"}
            )
            
            result = self._parse_response(response, as_json=True)
            return result.get('recommendations', [])
            
        except Exception as e:
            print(f"Restocking prediction failed: {e}")
            return []
    
    def analyze_profit_optimization(self, orders_df: pd.DataFrame, cogs_data: Dict[str, dict]) -> Dict[str, Any]:
        """AI analysis for profit optimization opportunities"""
        if not self.client:
            return {"opportunities": []}
        
        # Calculate detailed profit metrics
        profit_analysis = self._analyze_profit_margins(orders_df, cogs_data)
        
        try:
            prompt = f"""
            Analyze these profit margins and suggest optimization strategies:
            
            Product Profit Analysis:
            {json.dumps(profit_analysis[:15], indent=2)}
            
            Identify:
            1. Products with declining margins
            2. High-volume, low-margin items that could be optimized
            3. Pricing opportunities
            4. Product mix recommendations
            5. Cost reduction opportunities
            
            Format as JSON with detailed, actionable recommendations.
            """
            
            response = self.client.generate(
                messages=[{"role": "user", "content": prompt}],
                model="gpt-4-turbo-preview",
                temperature=0.6,
                response_format={"type": "json_object"}
            )
            
            return self._parse_response(response, as_json=True)
            
        except Exception as e:
            print(f"Profit optimization analysis failed: {e}")
            return {"opportunities": []}
    
    def generate_weekly_summary(self, orders_df: pd.DataFrame, previous_week_df: pd.DataFrame) -> str:
        """Generate natural language weekly performance summary"""
        if not self.client:
            return "AI summaries not available"
        
        # Calculate week-over-week changes
        wow_metrics = self._calculate_wow_metrics(orders_df, previous_week_df)
        
        try:
            prompt = f"""
            Write a concise, professional weekly performance summary:
            
            This Week's Metrics:
            {json.dumps(wow_metrics, indent=2)}
            
            Create a 3-4 paragraph summary that:
            1. Highlights key performance indicators
            2. Explains significant changes
            3. Identifies top performers and concerns
            4. Provides context and actionable next steps
            
            Write in a friendly but professional tone.
            """
            
            response = self.client.generate(
                messages=[{"role": "user", "content": prompt}],
                model="gpt-4-turbo-preview",
                temperature=0.7
            )
            
            return self._parse_response(response, as_json=False)
            
        except Exception as e:
            print(f"Weekly summary generation failed: {e}")
            return "Unable to generate summary"
    
    def detect_anomalies(self, orders_df: pd.DataFrame, sensitivity: float = 2.0) -> List[Dict[str, Any]]:
        """AI-powered anomaly detection in sales data"""
        if not self.client or orders_df.empty:
            return []
        
        # Statistical anomaly detection
        anomalies = self._detect_statistical_anomalies(orders_df, sensitivity)
        
        if not anomalies:
            return []
        
        try:
            prompt = f"""
            Analyze these potential anomalies in sales data:
            
            {json.dumps(anomalies, indent=2)}
            
            For each anomaly:
            1. Determine if it's significant
            2. Identify possible causes
            3. Suggest investigation steps
            4. Rate severity (high/medium/low)
            
            Return as JSON array with detailed analysis.
            """
            
            response = self.client.generate(
                messages=[{"role": "user", "content": prompt}],
                model="gpt-4-turbo-preview",
                temperature=0.5,
                response_format={"type": "json_object"}
            )
            
            result = self._parse_response(response, as_json=True)
            return result.get('anomalies', [])
            
        except Exception as e:
            print(f"Anomaly analysis failed: {e}")
            return []
    
    # Helper methods
    def _prepare_data_summary(self, orders_df: pd.DataFrame, cogs_data: Dict[str, dict]) -> Dict[str, Any]:
        """Prepare comprehensive data summary for AI analysis"""
        # Calculate profit for each order
        orders_df['profit'] = orders_df.apply(
            lambda row: self._calculate_profit(row, cogs_data), axis=1
        )
        
        # Sales metrics
        sales_metrics = {
            'total_revenue': float(orders_df['Sale Price'].sum()),
            'total_orders': len(orders_df),
            'average_order_value': float(orders_df['Sale Price'].mean()),
            'unique_products': orders_df['ASIN'].nunique(),
            'total_units': int(orders_df['Amount Purchased'].sum())
        }
        
        # Top products by revenue
        top_products = (orders_df.groupby(['ASIN', 'Name'])
                       .agg({
                           'Sale Price': 'sum',
                           'Amount Purchased': 'sum',
                           'profit': 'sum'
                       })
                       .sort_values('Sale Price', ascending=False)
                       .head(20)
                       .to_dict('records'))
        
        # Profit metrics
        profit_metrics = {
            'total_profit': float(orders_df['profit'].sum()),
            'average_profit_margin': float((orders_df['profit'] / orders_df['Sale Price']).mean() * 100),
            'high_margin_products': len(orders_df[orders_df['profit'] / orders_df['Sale Price'] > 0.3]),
            'negative_margin_products': len(orders_df[orders_df['profit'] < 0])
        }
        
        # Time patterns
        orders_df['date'] = pd.to_datetime(orders_df['Date'])
        daily_sales = orders_df.groupby(orders_df['date'].dt.date)['Sale Price'].sum()
        
        time_patterns = {
            'daily_average': float(daily_sales.mean()),
            'peak_day': str(daily_sales.idxmax()),
            'peak_revenue': float(daily_sales.max()),
            'trend': 'increasing' if daily_sales.iloc[-7:].mean() > daily_sales.iloc[:7].mean() else 'decreasing'
        }
        
        return {
            'sales_metrics': sales_metrics,
            'top_products': top_products,
            'profit_metrics': profit_metrics,
            'time_patterns': time_patterns
        }
    
    def _calculate_profit(self, row: pd.Series, cogs_data: Dict[str, dict]) -> float:
        """Calculate profit for a single order row"""
        asin = row.get('ASIN', '')
        sale_price = row.get('Sale Price', 0)
        
        if asin in cogs_data:
            cogs = cogs_data[asin].get('cogs', 0)
            return sale_price - cogs
        return sale_price * 0.5  # Default 50% margin if no COGS data
    
    def _calculate_sales_velocity(self, orders_df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Calculate sales velocity for each product"""
        if orders_df.empty:
            return []
        
        # Group by product and calculate daily velocity
        orders_df['date'] = pd.to_datetime(orders_df['Date'])
        date_range = (orders_df['date'].max() - orders_df['date'].min()).days + 1
        
        velocity = (orders_df.groupby(['ASIN', 'Name'])
                   .agg({
                       'Amount Purchased': 'sum',
                       'Sale Price': 'mean'
                   })
                   .reset_index())
        
        velocity['daily_velocity'] = velocity['Amount Purchased'] / date_range
        velocity = velocity.sort_values('daily_velocity', ascending=False)
        
        return velocity.to_dict('records')
    
    def _analyze_profit_margins(self, orders_df: pd.DataFrame, cogs_data: Dict[str, dict]) -> List[Dict[str, Any]]:
        """Analyze profit margins by product"""
        profit_analysis = []
        
        for asin in orders_df['ASIN'].unique():
            product_orders = orders_df[orders_df['ASIN'] == asin]
            total_revenue = product_orders['Sale Price'].sum()
            total_units = product_orders['Amount Purchased'].sum()
            
            if asin in cogs_data:
                cogs = cogs_data[asin].get('cogs', 0)
                total_cost = cogs * total_units
                profit = total_revenue - total_cost
                margin = (profit / total_revenue * 100) if total_revenue > 0 else 0
            else:
                profit = total_revenue * 0.5
                margin = 50.0
            
            profit_analysis.append({
                'asin': asin,
                'name': product_orders.iloc[0]['Name'],
                'total_revenue': float(total_revenue),
                'total_profit': float(profit),
                'profit_margin': float(margin),
                'units_sold': int(total_units)
            })
        
        return sorted(profit_analysis, key=lambda x: x['total_profit'], reverse=True)
    
    def _calculate_wow_metrics(self, current_df: pd.DataFrame, previous_df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate week-over-week metrics"""
        current_revenue = current_df['Sale Price'].sum()
        previous_revenue = previous_df['Sale Price'].sum() if not previous_df.empty else 0
        
        current_orders = len(current_df)
        previous_orders = len(previous_df) if not previous_df.empty else 0
        
        return {
            'current_week': {
                'revenue': float(current_revenue),
                'orders': current_orders,
                'aov': float(current_revenue / current_orders) if current_orders > 0 else 0
            },
            'previous_week': {
                'revenue': float(previous_revenue),
                'orders': previous_orders,
                'aov': float(previous_revenue / previous_orders) if previous_orders > 0 else 0
            },
            'changes': {
                'revenue_change': float((current_revenue - previous_revenue) / previous_revenue * 100) if previous_revenue > 0 else 0,
                'orders_change': float((current_orders - previous_orders) / previous_orders * 100) if previous_orders > 0 else 0
            }
        }
    
    def _detect_statistical_anomalies(self, orders_df: pd.DataFrame, sensitivity: float) -> List[Dict[str, Any]]:
        """Detect statistical anomalies in the data"""
        anomalies = []
        
        # Check for unusual price points
        for asin in orders_df['ASIN'].unique():
            product_prices = orders_df[orders_df['ASIN'] == asin]['Sale Price']
            if len(product_prices) > 3:
                mean_price = product_prices.mean()
                std_price = product_prices.std()
                
                for idx, price in product_prices.items():
                    if abs(price - mean_price) > sensitivity * std_price:
                        anomalies.append({
                            'type': 'price_anomaly',
                            'asin': asin,
                            'expected_price': float(mean_price),
                            'actual_price': float(price),
                            'deviation': float((price - mean_price) / mean_price * 100)
                        })
        
        return anomalies[:10]  # Limit to top 10 anomalies

    def generate_insights_from_analytics(self, analytics_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate AI insights from structured analytics data instead of raw DataFrame"""
        if not self.client:
            return {
                "insights": ["AI insights not available - Keywords.ai not configured"],
                "recommendations": [],
                "warnings": [],
                "opportunities": [],
                "ai_enabled": False
            }
        
        try:
            # Extract key metrics from analytics data
            today_sales = analytics_data.get('today_sales', {})
            stock_info = analytics_data.get('enhanced_analytics', {})
            low_stock = analytics_data.get('low_stock', {})
            
            # Calculate summary statistics
            total_orders = sum(today_sales.values())
            total_products = len(today_sales)
            top_products = sorted(today_sales.items(), key=lambda x: x[1], reverse=True)[:10]
            
            # Build context for AI
            prompt = f"""
            Analyze this e-commerce performance data and provide actionable insights:
            
            Sales Performance:
            - Total Orders: {total_orders}
            - Active Products: {total_products}
            - Top Sellers: {json.dumps(dict(top_products[:5]), indent=2)}
            
            Inventory Alerts:
            - Low Stock Items: {len(low_stock)}
            - Stock Alerts: {json.dumps(list(low_stock.keys())[:5]) if low_stock else 'None'}
            
            Enhanced Analytics Available: {bool(stock_info)}
            
            Provide insights in JSON format with:
            - insights: array of key observations
            - recommendations: array of actionable suggestions
            - warnings: array of urgent issues
            - opportunities: array of growth opportunities
            
            Focus on practical, specific advice for an Amazon seller.
            """
            
            response = self.client.generate(
                messages=[{"role": "user", "content": prompt}],
                model="gpt-4-turbo-preview", 
                temperature=0.5,
                response_format={"type": "json_object"}
            )
            
            result = self._parse_response(response, as_json=True)
            result['ai_enabled'] = True
            return result
            
        except Exception as e:
            print(f"AI insights generation failed: {e}")
            return {
                "insights": [f"AI analysis encountered an error: {str(e)[:100]}"],
                "recommendations": ["Review your data sources and try again"],
                "warnings": [],
                "opportunities": [],
                "ai_enabled": True,
                "error": str(e)
            }

    def predict_restocking_from_analytics(self, sales_data: Dict[str, int], stock_info: Dict[str, dict], lead_time_days: int = 90) -> List[Dict[str, Any]]:
        """Predict restocking needs from structured analytics data"""
        if not self.client:
            return []
        
        try:
            # Build velocity data from sales 
            velocity_data = []
            for asin, total_sales in sales_data.items():
                # Estimate daily velocity (30-day period)
                daily_velocity = total_sales / 30.0
                
                # Get stock info if available
                stock_data = stock_info.get(asin, {})
                current_stock = stock_data.get('restock', {}).get('current_stock', 50)  # Default fallback
                
                velocity_data.append({
                    'asin': asin,
                    'daily_velocity': daily_velocity,
                    'current_stock': current_stock,
                    'total_sales_30d': total_sales
                })
            
            # Sort by urgency (high velocity, low stock)
            velocity_data.sort(key=lambda x: x['daily_velocity'] / max(x['current_stock'], 1), reverse=True)
            
            prompt = f"""
            Based on this sales velocity and stock data, provide restocking recommendations:
            
            Sales & Stock Analysis (Top 20 products):
            {json.dumps(velocity_data[:20], indent=2)}
            
            Lead Time: {lead_time_days} days
            
            For each product that needs restocking, provide:
            - asin
            - product_name (use ASIN if unknown)
            - recommended_order_quantity 
            - urgency (critical/high/medium/low)
            - reasoning (why this quantity and urgency)
            - estimated_runout_days
            
            Focus on products with high velocity or low stock relative to demand.
            Respond with JSON: {{"recommendations": [...]}}
            """
            
            response = self.client.generate(
                messages=[{"role": "user", "content": prompt}],
                model="gpt-4-turbo-preview",
                temperature=0.5,
                response_format={"type": "json_object"}
            )
            
            result = self._parse_response(response, as_json=True)
            return result.get('recommendations', [])
            
        except Exception as e:
            print(f"Restocking prediction from analytics failed: {e}")
            return []