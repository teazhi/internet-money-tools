"""
Inventory Age Analysis Module
Analyzes inventory age using multiple data sources to provide comprehensive age-based insights
"""

import pandas as pd
from datetime import datetime, timedelta, date
from typing import Dict, List, Tuple, Optional, Any
import math
import statistics

class InventoryAgeAnalyzer:
    """Analyzes inventory age using multiple data sources"""
    
    def __init__(self):
        self.age_categories = {
            'fresh': {'min': 0, 'max': 30, 'label': 'Fresh (0-30 days)', 'color': '#10b981'},
            'moderate': {'min': 31, 'max': 90, 'label': 'Moderate (31-90 days)', 'color': '#f59e0b'}, 
            'aged': {'min': 91, 'max': 180, 'label': 'Aged (91-180 days)', 'color': '#f97316'},
            'old': {'min': 181, 'max': 365, 'label': 'Old (181-365 days)', 'color': '#dc2626'},
            'ancient': {'min': 366, 'max': 999999, 'label': 'Ancient (365+ days)', 'color': '#7c2d12'}
        }
    
    def analyze_inventory_age(self, enhanced_analytics: Dict, purchase_insights: Dict, 
                            stock_data: Dict, orders_data: pd.DataFrame) -> Dict:
        """
        Comprehensive inventory age analysis using all available data sources
        
        Args:
            enhanced_analytics: Current inventory analytics
            purchase_insights: Purchase analytics from Google Sheets
            stock_data: Raw stock data from Sellerboard
            orders_data: Historical orders data
            
        Returns:
            Dictionary containing age analysis results
        """
        try:
            age_analysis = {}
            
            # Debug: Check what we're receiving
            print(f"DEBUG - InventoryAgeAnalyzer: enhanced_analytics type: {type(enhanced_analytics)}")
            print(f"DEBUG - InventoryAgeAnalyzer: enhanced_analytics keys sample: {list(enhanced_analytics.keys())[:5] if hasattr(enhanced_analytics, 'keys') else 'No keys method'}")
            
            for asin, product_data in enhanced_analytics.items():
                age_info = self._calculate_product_age(
                    asin, product_data, purchase_insights, stock_data, orders_data
                )
                age_analysis[asin] = age_info
            
            # Generate summary statistics and insights
            summary = self._generate_age_summary(age_analysis)
            
            # Debug: Check final age_analysis structure
            print(f"DEBUG - InventoryAgeAnalyzer: final age_analysis keys sample: {list(age_analysis.keys())[:5]}")
            print(f"DEBUG - InventoryAgeAnalyzer: final age_analysis type: {type(age_analysis)}")
            
            # Ensure no pandas objects in the final return
            result = {
                'age_analysis': age_analysis,
                'summary': summary,
                'age_categories': self.age_categories,
                'generated_at': datetime.now().isoformat()
            }
            
            # Debug: Check for any pandas objects in the result
            def check_for_pandas_objects(obj, path=""):
                import pandas as pd
                if isinstance(obj, (pd.DataFrame, pd.Series)):
                    print(f"WARNING - Found pandas object at {path}: {type(obj)}")
                    return True
                elif isinstance(obj, dict):
                    for key, value in obj.items():
                        if check_for_pandas_objects(value, f"{path}.{key}"):
                            return True
                elif isinstance(obj, list):
                    for i, item in enumerate(obj):
                        if check_for_pandas_objects(item, f"{path}[{i}]"):
                            return True
                return False
            
            check_for_pandas_objects(result, "age_analysis_result")
            
            return result
            
        except Exception as e:
            print(f"Error in inventory age analysis: {str(e)}")
            return self._empty_age_analysis()
    
    def _calculate_product_age(self, asin: str, product_data: Dict, 
                             purchase_insights: Dict, stock_data: Dict, 
                             orders_data: pd.DataFrame) -> Dict:
        """Calculate age for a specific product using multiple data sources"""
        
        age_sources = []
        confidence_score = 0
        
        # Method 1: Google Sheets purchase data (highest confidence)
        purchase_age = self._calculate_age_from_purchases(asin, purchase_insights)
        if purchase_age:
            age_sources.append(purchase_age)
            confidence_score += 0.4
        
        # Method 2: Sellerboard stock creation dates (medium confidence) 
        stock_age = self._calculate_age_from_stock_data(asin, stock_data)
        if stock_age:
            age_sources.append(stock_age)
            confidence_score += 0.3
        
        # Method 3: Sales pattern inference (lower confidence)
        velocity_age = self._infer_age_from_velocity(asin, product_data, orders_data)
        if velocity_age:
            age_sources.append(velocity_age)
            confidence_score += 0.2
        
        # Method 4: Stock level estimation (lowest confidence)
        stock_level_age = self._estimate_age_from_stock_levels(asin, product_data)
        if stock_level_age:
            age_sources.append(stock_level_age)
            confidence_score += 0.1
        
        # Calculate weighted average age
        if age_sources:
            weighted_age = self._calculate_weighted_age(age_sources)
            category = self._get_age_category(weighted_age)
            
            return {
                'estimated_age_days': weighted_age,
                'age_category': category,
                'confidence_score': min(confidence_score, 1.0),
                'data_sources': [source['method'] for source in age_sources],
                'age_range': self._calculate_age_range(age_sources),
                'details': {
                    'purchase_based_age': purchase_age.get('age_days') if purchase_age else None,
                    'stock_based_age': stock_age.get('age_days') if stock_age else None,
                    'velocity_based_age': velocity_age.get('age_days') if velocity_age else None,
                    'stock_level_age': stock_level_age.get('age_days') if stock_level_age else None,
                },
                'recommendations': self._generate_age_recommendations(weighted_age, category, product_data)
            }
        else:
            return {
                'estimated_age_days': None,
                'age_category': 'unknown',
                'confidence_score': 0.0,
                'data_sources': [],
                'age_range': {'min': None, 'max': None},
                'details': {},
                'recommendations': ['No age data available - consider updating purchase records']
            }
    
    def _calculate_age_from_purchases(self, asin: str, purchase_insights: Dict) -> Optional[Dict]:
        """Calculate age based on Google Sheets purchase data"""
        try:
            velocity_analysis = purchase_insights.get('purchase_velocity_analysis', {})
            recent_purchases = purchase_insights.get('recent_2_months_purchases', {})
            
            # Check recent purchases first (more reliable)
            if asin in recent_purchases:
                purchase_data = recent_purchases[asin]
                last_purchase_str = purchase_data.get('last_purchase_date')
                first_purchase_str = purchase_data.get('first_purchase_date')
                
                if last_purchase_str:
                    last_purchase = datetime.fromisoformat(last_purchase_str.replace('Z', '+00:00'))
                    age_days = (datetime.now() - last_purchase).days
                    
                    return {
                        'age_days': age_days,
                        'method': 'recent_purchase_data',
                        'confidence': 0.9,
                        'source_date': last_purchase_str,
                        'purchase_count': purchase_data.get('purchase_count', 0)
                    }
            
            # Fallback to velocity analysis
            if asin in velocity_analysis:
                velocity_data = velocity_analysis[asin]
                last_purchase_str = velocity_data.get('last_purchase_date')
                
                if last_purchase_str:
                    last_purchase = datetime.fromisoformat(last_purchase_str.replace('Z', '+00:00'))
                    age_days = (datetime.now() - last_purchase).days
                    
                    return {
                        'age_days': age_days,
                        'method': 'velocity_purchase_data',
                        'confidence': 0.8,
                        'source_date': last_purchase_str,
                        'days_since_purchase': velocity_data.get('days_since_last_purchase', 0)
                    }
            
            return None
            
        except Exception as e:
            print(f"Error calculating purchase-based age for {asin}: {str(e)}")
            return None
    
    def _calculate_age_from_stock_data(self, asin: str, stock_data: Dict) -> Optional[Dict]:
        """Calculate age from Sellerboard stock data if creation dates available"""
        try:
            product_stock = stock_data.get(asin, {})
            if not product_stock:
                return None
            
            # Look for various date fields that might indicate inventory creation/received dates
            date_fields = [
                'Created Date', 'created_date', 'Created', 
                'First Received', 'first_received', 'Received Date',
                'Listing Created', 'listing_created', 'Date Added',
                'First Stock Date', 'first_stock_date'
            ]
            
            for field in date_fields:
                if field in product_stock and product_stock[field]:
                    try:
                        date_value = pd.to_datetime(product_stock[field])
                        age_days = (datetime.now() - date_value).days
                        
                        return {
                            'age_days': age_days,
                            'method': f'stock_data_{field.lower()}',
                            'confidence': 0.7,
                            'source_date': date_value.isoformat(),
                            'field_used': field
                        }
                    except:
                        continue
            
            return None
            
        except Exception as e:
            print(f"Error calculating stock-based age for {asin}: {str(e)}")
            return None
    
    def _infer_age_from_velocity(self, asin: str, product_data: Dict, 
                               orders_data: pd.DataFrame) -> Optional[Dict]:
        """Infer inventory age from sales velocity patterns"""
        try:
            velocity_data = product_data.get('velocity', {})
            current_stock = product_data.get('restock', {}).get('current_stock', 0)
            daily_velocity = velocity_data.get('weighted_velocity', 0)
            
            if current_stock <= 0 or daily_velocity <= 0:
                return None
            
            # Filter orders for this ASIN to analyze sales pattern
            asin_orders = orders_data[orders_data['ASIN'] == asin] if 'ASIN' in orders_data.columns else pd.DataFrame()
            
            if not asin_orders.empty and 'Datetime' in asin_orders.columns:
                # Find the first sale date - this gives us a minimum age
                first_sale = asin_orders['Datetime'].min()
                first_sale_age = (datetime.now() - first_sale).days
                
                # Estimate when inventory was likely received (before first sale)
                # Add buffer time for listing creation, processing, etc.
                estimated_buffer_days = 7  # Assume 1 week between receiving and first sale
                estimated_age = first_sale_age + estimated_buffer_days
                
                return {
                    'age_days': estimated_age,
                    'method': 'first_sale_inference',
                    'confidence': 0.5,
                    'source_date': first_sale.isoformat(),
                    'buffer_days': estimated_buffer_days
                }
            
            return None
            
        except Exception as e:
            print(f"Error inferring velocity-based age for {asin}: {str(e)}")
            return None
    
    def _estimate_age_from_stock_levels(self, asin: str, product_data: Dict) -> Optional[Dict]:
        """Estimate age from current stock levels and velocity patterns"""
        try:
            restock_data = product_data.get('restock', {})
            velocity_data = product_data.get('velocity', {})
            
            current_stock = restock_data.get('current_stock', 0)
            daily_velocity = velocity_data.get('weighted_velocity', 0)
            
            if current_stock <= 0 or daily_velocity <= 0:
                return None
            
            # If we have high stock but low recent sales, inventory might be older
            days_of_stock = current_stock / daily_velocity
            
            # Rough estimation: if you have more than 6 months of stock at current velocity,
            # inventory is probably older (especially for slow-moving items)
            if days_of_stock > 180:
                # Estimate that inventory is at least 50% of the days_of_stock old
                estimated_age = min(days_of_stock * 0.5, 365)  # Cap at 1 year
                
                return {
                    'age_days': estimated_age,
                    'method': 'high_stock_estimation',
                    'confidence': 0.3,
                    'days_of_stock': days_of_stock,
                    'reasoning': 'High stock level suggests older inventory'
                }
            
            return None
            
        except Exception as e:
            print(f"Error estimating stock-level age for {asin}: {str(e)}")
            return None
    
    def _calculate_weighted_age(self, age_sources: List[Dict]) -> int:
        """Calculate weighted average age from multiple sources"""
        if not age_sources:
            return 0
        
        total_weighted_age = 0
        total_weight = 0
        
        for source in age_sources:
            age = source.get('age_days', 0)
            confidence = source.get('confidence', 0.1)
            
            total_weighted_age += age * confidence
            total_weight += confidence
        
        return int(total_weighted_age / total_weight) if total_weight > 0 else 0
    
    def _calculate_age_range(self, age_sources: List[Dict]) -> Dict:
        """Calculate age range from different sources"""
        if not age_sources:
            return {'min': None, 'max': None}
        
        ages = [source.get('age_days', 0) for source in age_sources]
        return {
            'min': min(ages),
            'max': max(ages),
            'variance': max(ages) - min(ages) if len(ages) > 1 else 0
        }
    
    def _get_age_category(self, age_days: int) -> str:
        """Determine age category based on days"""
        for category, config in self.age_categories.items():
            if config['min'] <= age_days <= config['max']:
                return category
        return 'unknown'
    
    def _generate_age_recommendations(self, age_days: int, category: str, 
                                    product_data: Dict) -> List[str]:
        """Generate recommendations based on inventory age"""
        recommendations = []
        
        current_stock = product_data.get('restock', {}).get('current_stock', 0)
        velocity = product_data.get('velocity', {}).get('weighted_velocity', 0)
        
        if category == 'fresh':
            recommendations.append("✅ Fresh inventory - good restocking timing")
        elif category == 'moderate':
            recommendations.append("⚠️ Monitor closely - consider sales acceleration tactics")
        elif category == 'aged':
            recommendations.append("🟡 Consider discount promotions to move aged inventory")
            if current_stock > 30:
                recommendations.append("📦 High aged stock - prioritize liquidation")
        elif category == 'old':
            recommendations.append("🔴 Urgent: Implement aggressive pricing strategies")
            recommendations.append("💰 Consider bundling or promotional campaigns")
            if velocity < 1:
                recommendations.append("⏰ Very slow-moving - evaluate discontinuation")
        elif category == 'ancient':
            recommendations.append("🚨 Critical: Ancient inventory requires immediate action")
            recommendations.append("🏷️ Deep discount or clearance sale recommended")
            recommendations.append("📋 Evaluate storage costs vs. liquidation value")
        
        # Velocity-based recommendations
        if velocity > 0:
            days_to_sell = current_stock / velocity
            if days_to_sell > age_days:
                recommendations.append(f"📈 At current velocity, will take {days_to_sell:.0f} days to sell remaining stock")
        
        return recommendations
    
    def _generate_age_summary(self, age_analysis: Dict) -> Dict:
        """Generate summary statistics for age analysis"""
        try:
            categories_count = {category: 0 for category in self.age_categories.keys()}
            categories_count['unknown'] = 0
            
            total_products = len(age_analysis)
            products_with_age_data = 0
            age_values = []
            confidence_scores = []
            
            for asin, age_data in age_analysis.items():
                category = age_data.get('age_category', 'unknown')
                categories_count[category] += 1
                
                age_days = age_data.get('estimated_age_days')
                if age_days is not None:
                    products_with_age_data += 1
                    age_values.append(age_days)
                    confidence_scores.append(age_data.get('confidence_score', 0))
            
            # Calculate statistics
            avg_age = statistics.mean(age_values) if age_values else 0
            median_age = statistics.median(age_values) if age_values else 0
            avg_confidence = statistics.mean(confidence_scores) if confidence_scores else 0
            
            # Generate insights
            insights = []
            total_aged_old_ancient = categories_count['aged'] + categories_count['old'] + categories_count['ancient']
            
            if total_aged_old_ancient > total_products * 0.3:
                insights.append("⚠️ High percentage of aged inventory - consider liquidation strategies")
            
            if categories_count['ancient'] > 0:
                insights.append(f"🚨 {categories_count['ancient']} products with ancient inventory need immediate attention")
            
            if avg_confidence < 0.5:
                insights.append("📊 Low confidence in age estimates - consider improving purchase tracking")
            
            return {
                'total_products': total_products,
                'products_with_age_data': products_with_age_data,
                'coverage_percentage': (products_with_age_data / total_products * 100) if total_products > 0 else 0,
                'average_age_days': round(avg_age),
                'median_age_days': round(median_age),
                'average_confidence': round(avg_confidence, 2),
                'categories_breakdown': categories_count,
                'insights': insights,
                'oldest_inventory_days': max(age_values) if age_values else 0,
                'newest_inventory_days': min(age_values) if age_values else 0
            }
            
        except Exception as e:
            print(f"Error generating age summary: {str(e)}")
            return self._empty_summary()
    
    def _empty_age_analysis(self) -> Dict:
        """Return empty age analysis structure"""
        return {
            'age_analysis': {},
            'summary': self._empty_summary(),
            'age_categories': self.age_categories,
            'error': 'Failed to analyze inventory age',
            'generated_at': datetime.now().isoformat()
        }
    
    def _empty_summary(self) -> Dict:
        """Return empty summary structure"""
        return {
            'total_products': 0,
            'products_with_age_data': 0,
            'coverage_percentage': 0,
            'average_age_days': 0,
            'median_age_days': 0,
            'average_confidence': 0,
            'categories_breakdown': {cat: 0 for cat in self.age_categories.keys()},
            'insights': [],
            'oldest_inventory_days': 0,
            'newest_inventory_days': 0
        }
    
    def filter_by_age_category(self, age_analysis: Dict, categories: List[str]) -> Dict:
        """Filter products by age categories"""
        filtered = {}
        
        for asin, age_data in age_analysis.get('age_analysis', {}).items():
            if age_data.get('age_category') in categories:
                filtered[asin] = age_data
        
        return filtered
    
    def get_products_needing_action(self, age_analysis: Dict, 
                                  enhanced_analytics: Dict) -> List[Dict]:
        """Get prioritized list of products needing action based on age"""
        action_items = []
        
        for asin, age_data in age_analysis.get('age_analysis', {}).items():
            category = age_data.get('age_category')
            age_days = age_data.get('estimated_age_days', 0)
            
            # Focus on aged, old, and ancient inventory
            if category in ['aged', 'old', 'ancient']:
                product_data = enhanced_analytics.get(asin, {})
                current_stock = product_data.get('restock', {}).get('current_stock', 0)
                velocity = product_data.get('velocity', {}).get('weighted_velocity', 0)
                
                # Calculate urgency score
                urgency_score = self._calculate_action_urgency(age_days, current_stock, velocity, category)
                
                action_item = {
                    'asin': asin,
                    'product_name': product_data.get('product_name', f'Product {asin}'),
                    'age_days': age_days,
                    'age_category': category,
                    'current_stock': current_stock,
                    'velocity': velocity,
                    'urgency_score': urgency_score,
                    'estimated_value': current_stock * product_data.get('cogs_data', {}).get('cogs', 0),
                    'recommendations': age_data.get('recommendations', []),
                    'days_to_sell': current_stock / velocity if velocity > 0 else 999999
                }
                
                action_items.append(action_item)
        
        # Sort by urgency score (highest first)
        action_items.sort(key=lambda x: x['urgency_score'], reverse=True)
        
        return action_items
    
    def _calculate_action_urgency(self, age_days: int, current_stock: float, 
                                velocity: float, category: str) -> float:
        """Calculate urgency score for taking action on aged inventory"""
        base_score = 0
        
        # Age-based scoring
        age_scores = {
            'aged': 0.3,
            'old': 0.6, 
            'ancient': 1.0
        }
        base_score += age_scores.get(category, 0)
        
        # Stock level multiplier (more stock = higher urgency)
        stock_multiplier = min(current_stock / 100, 2.0)  # Cap at 2x
        base_score *= (1 + stock_multiplier)
        
        # Velocity factor (slower moving = higher urgency for aged inventory)
        if velocity <= 0:
            velocity_factor = 1.5
        elif velocity < 1:
            velocity_factor = 1.2
        else:
            velocity_factor = 1.0
        
        base_score *= velocity_factor
        
        # Time pressure (older = more urgent)
        if age_days > 365:
            base_score *= 1.5
        elif age_days > 270:
            base_score *= 1.3
        elif age_days > 180:
            base_score *= 1.1
        
        return round(base_score, 2)