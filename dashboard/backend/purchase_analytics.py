"""
Purchase Analytics Module
Analyzes Google Sheets purchase data to generate intelligent restocking insights
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import math

class PurchaseAnalytics:
    """Analyzes purchase data from Google Sheets to generate restocking insights"""
    
    def __init__(self):
        self.purchase_data = {}
        self.current_month = datetime.now().month
        self.current_year = datetime.now().year
    
    def analyze_purchase_data(self, sheet_data: pd.DataFrame, column_mapping: dict) -> Dict:
        """
        Analyze purchase data from Google Sheets to generate restocking insights
        
        Args:
            sheet_data: DataFrame containing Google Sheets data
            column_mapping: Mapping of column names to actual sheet columns
            
        Returns:
            Dictionary containing purchase-based insights
        """
        try:
            # Get column mappings
            date_field = column_mapping.get("Date", "Date")
            asin_field = column_mapping.get("ASIN", "ASIN")
            amount_purchased_field = column_mapping.get("Amount Purchased", "Amount Purchased")
            cogs_field = column_mapping.get("COGS", "COGS")
            sale_price_field = column_mapping.get("Sale Price", "Sale Price")
            units_field = column_mapping.get("# Units in Bundle", "# Units in Bundle")
            
            # Clean and prepare data
            df = self._clean_purchase_data(sheet_data, {
                'date': date_field,
                'asin': asin_field,
                'amount_purchased': amount_purchased_field,
                'cogs': cogs_field,
                'sale_price': sale_price_field,
                'units': units_field
            })
            
            if df.empty:
                return self._empty_analytics_response()
            
            # Generate insights
            insights = {
                'purchase_velocity_analysis': self._analyze_purchase_velocity(df),
                'restock_urgency_scoring': self._calculate_restock_urgency(df),
                'purchase_pattern_insights': self._analyze_purchase_patterns(df),
                'roi_based_recommendations': self._generate_roi_recommendations(df),
                'seasonal_purchase_trends': self._analyze_seasonal_trends(df),
                'cash_flow_optimization': self._analyze_cash_flow_impact(df),
                'summary_metrics': self._generate_summary_metrics(df),
                'recent_2_months_purchases': self._analyze_recent_2_months_purchases(df)
            }
            
            return insights
            
        except Exception as e:
            pass  # Debug print removed
            return self._empty_analytics_response()
    
    def _clean_purchase_data(self, df: pd.DataFrame, field_mapping: dict) -> pd.DataFrame:
        """Clean and standardize purchase data"""
        try:
            # Create working copy
            clean_df = df.copy()
            
            # Clean ASIN field
            if field_mapping['asin'] in clean_df.columns:
                clean_df['asin'] = clean_df[field_mapping['asin']].astype(str).str.strip()
                clean_df = clean_df[clean_df['asin'].notna() & (clean_df['asin'] != '') & (clean_df['asin'] != 'nan')]
            
            # Clean and convert numeric fields
            numeric_fields = ['amount_purchased', 'cogs', 'sale_price', 'units']
            for field in numeric_fields:
                if field_mapping[field] in clean_df.columns:
                    clean_df[field] = pd.to_numeric(
                        clean_df[field_mapping[field]].astype(str).replace(r"[\$,]", "", regex=True), 
                        errors="coerce"
                    )
            
            # Clean date field
            if field_mapping['date'] in clean_df.columns:
                clean_df['date'] = pd.to_datetime(clean_df[field_mapping['date']], errors='coerce')
                clean_df = clean_df[clean_df['date'].notna()]
                
                # Filter to last 12 months for relevant analysis
                cutoff_date = datetime.now() - timedelta(days=365)
                clean_df = clean_df[clean_df['date'] >= cutoff_date]
            
            # Remove rows with invalid core data
            clean_df = clean_df[
                clean_df['asin'].notna() & 
                clean_df['amount_purchased'].notna() & 
                (clean_df['amount_purchased'] > 0)
            ]
            
            pass  # Debug print removed
            return clean_df
            
        except Exception as e:
            pass  # Debug print removed
            return pd.DataFrame()
    
    def _analyze_purchase_velocity(self, df: pd.DataFrame) -> Dict:
        """Analyze how frequently and in what quantities items are purchased"""
        velocity_analysis = {}
        
        for asin in df['asin'].unique():
            asin_data = df[df['asin'] == asin].copy()
            
            # Sort by date to analyze purchase patterns
            asin_data = asin_data.sort_values('date')
            
            # Calculate purchase frequency
            total_purchases = len(asin_data)
            date_span = (asin_data['date'].max() - asin_data['date'].min()).days
            avg_days_between_purchases = date_span / max(1, total_purchases - 1) if total_purchases > 1 else None
            
            # Calculate quantity trends
            total_quantity_purchased = asin_data['amount_purchased'].sum()
            avg_quantity_per_purchase = asin_data['amount_purchased'].mean()
            last_purchase_date = asin_data['date'].max()
            days_since_last_purchase = (datetime.now() - last_purchase_date).days
            
            # Calculate purchase acceleration/deceleration
            if len(asin_data) >= 3:
                recent_half = asin_data.tail(len(asin_data)//2)
                older_half = asin_data.head(len(asin_data)//2)
                
                recent_avg_qty = recent_half['amount_purchased'].mean()
                older_avg_qty = older_half['amount_purchased'].mean()
                
                purchase_trend = (recent_avg_qty - older_avg_qty) / older_avg_qty if older_avg_qty > 0 else 0
            else:
                purchase_trend = 0
            
            velocity_analysis[asin] = {
                'total_purchases': total_purchases,
                'total_quantity_purchased': total_quantity_purchased,
                'avg_quantity_per_purchase': avg_quantity_per_purchase,
                'avg_days_between_purchases': avg_days_between_purchases,
                'days_since_last_purchase': days_since_last_purchase,
                'purchase_trend': purchase_trend,  # Positive = increasing, Negative = decreasing
                'last_purchase_date': last_purchase_date.isoformat() if pd.notna(last_purchase_date) else None,
                'purchase_frequency_score': self._calculate_frequency_score(avg_days_between_purchases, days_since_last_purchase)
            }
        
        return velocity_analysis
    
    def _calculate_restock_urgency(self, df: pd.DataFrame) -> Dict:
        """Calculate urgency scores for restocking based on purchase patterns"""
        urgency_scores = {}
        
        velocity_data = self._analyze_purchase_velocity(df)
        
        for asin, velocity in velocity_data.items():
            asin_data = df[df['asin'] == asin]
            
            # Factors for urgency calculation
            frequency_score = velocity['purchase_frequency_score']
            days_since_last = velocity['days_since_last_purchase']
            avg_days_between = velocity['avg_days_between_purchases'] or 30
            trend_score = max(-1, min(1, velocity['purchase_trend']))  # Normalize between -1 and 1
            
            # Calculate base urgency (0-100)
            if days_since_last > avg_days_between * 1.5:
                time_urgency = 100  # Overdue
            elif days_since_last > avg_days_between:
                time_urgency = 70 + (days_since_last - avg_days_between) / (avg_days_between * 0.5) * 30
            else:
                time_urgency = (days_since_last / avg_days_between) * 70
            
            # Adjust for purchase trend
            trend_adjustment = trend_score * 20  # Up to ±20 points for trending
            
            # Final urgency score
            urgency_score = min(100, max(0, time_urgency + trend_adjustment))
            
            # Categorize urgency
            if urgency_score >= 80:
                urgency_level = "CRITICAL"
                urgency_color = "red"
            elif urgency_score >= 60:
                urgency_level = "HIGH"
                urgency_color = "orange"
            elif urgency_score >= 40:
                urgency_level = "MEDIUM"
                urgency_color = "yellow"
            else:
                urgency_level = "LOW"
                urgency_color = "green"
            
            urgency_scores[asin] = {
                'urgency_score': round(urgency_score, 1),
                'urgency_level': urgency_level,
                'urgency_color': urgency_color,
                'days_since_last_purchase': days_since_last,
                'expected_restock_date': velocity['last_purchase_date'],
                'recommended_quantity': self._calculate_recommended_purchase_quantity(asin_data, velocity)
            }
        
        return urgency_scores
    
    def _analyze_purchase_patterns(self, df: pd.DataFrame) -> Dict:
        """Analyze purchasing patterns to identify trends and insights"""
        patterns = {
            'monthly_spending_trend': {},
            'seasonal_patterns': {},  
            'asin_performance_insights': {},
            'cost_efficiency_analysis': {}
        }
        
        # Monthly spending analysis
        df['year_month'] = df['date'].dt.to_period('M')
        monthly_data = df.groupby('year_month').agg({
            'amount_purchased': 'sum',
            'cogs': lambda x: (x * df.loc[x.index, 'amount_purchased']).sum(),
            'asin': 'nunique'
        }).reset_index()
        
        monthly_data['year_month_str'] = monthly_data['year_month'].astype(str)
        patterns['monthly_spending_trend'] = monthly_data.to_dict('records')
        
        # ASIN performance insights
        asin_performance = df.groupby('asin').agg({
            'amount_purchased': ['sum', 'count', 'mean'],
            'cogs': ['mean', lambda x: (x * df.loc[x.index, 'amount_purchased']).sum()],
            'date': ['min', 'max']
        }).reset_index()
        
        # Flatten column names
        asin_performance.columns = ['asin', 'total_qty', 'purchase_count', 'avg_qty_per_purchase', 
                                  'avg_cogs', 'total_cost', 'first_purchase', 'last_purchase']
        
        patterns['asin_performance_insights'] = asin_performance.to_dict('records')
        
        return patterns
    
    def _generate_roi_recommendations(self, df: pd.DataFrame) -> Dict:
        """Generate recommendations based on ROI and profitability analysis"""
        roi_data = {}
        
        for asin in df['asin'].unique():
            asin_data = df[df['asin'] == asin]
            
            # Skip if missing pricing data
            if asin_data['sale_price'].isna().all() or asin_data['cogs'].isna().all():
                continue
            
            avg_sale_price = asin_data['sale_price'].mean()
            avg_cogs = asin_data['cogs'].mean()
            total_quantity = asin_data['amount_purchased'].sum()
            
            if avg_cogs > 0:
                roi_per_unit = (avg_sale_price - avg_cogs) / avg_cogs * 100
                total_profit_potential = (avg_sale_price - avg_cogs) * total_quantity
                
                # Recommendation based on ROI
                if roi_per_unit >= 50:
                    recommendation = "HIGH_PRIORITY"
                    reason = f"Excellent ROI ({roi_per_unit:.1f}%) - prioritize restocking"
                elif roi_per_unit >= 25:
                    recommendation = "MEDIUM_PRIORITY" 
                    reason = f"Good ROI ({roi_per_unit:.1f}%) - maintain regular restocking"
                elif roi_per_unit >= 10:
                    recommendation = "LOW_PRIORITY"
                    reason = f"Moderate ROI ({roi_per_unit:.1f}%) - monitor closely"
                else:
                    recommendation = "REVIEW_REQUIRED"
                    reason = f"Low ROI ({roi_per_unit:.1f}%) - review pricing or supplier"
                
                roi_data[asin] = {
                    'roi_percentage': round(roi_per_unit, 1),
                    'avg_sale_price': round(avg_sale_price, 2),
                    'avg_cogs': round(avg_cogs, 2),
                    'profit_per_unit': round(avg_sale_price - avg_cogs, 2),
                    'total_quantity_purchased': int(total_quantity),
                    'total_profit_potential': round(total_profit_potential, 2),
                    'recommendation': recommendation,
                    'reason': reason
                }
        
        return roi_data
    
    def _analyze_seasonal_trends(self, df: pd.DataFrame) -> Dict:
        """Analyze seasonal purchasing patterns"""
        df['month'] = df['date'].dt.month
        df['quarter'] = df['date'].dt.quarter
        
        monthly_patterns = df.groupby(['asin', 'month'])['amount_purchased'].sum().reset_index()
        quarterly_patterns = df.groupby(['asin', 'quarter'])['amount_purchased'].sum().reset_index()
        
        seasonal_insights = {}
        for asin in df['asin'].unique():
            asin_monthly = monthly_patterns[monthly_patterns['asin'] == asin]
            asin_quarterly = quarterly_patterns[quarterly_patterns['asin'] == asin]
            
            if len(asin_monthly) > 1:
                peak_month = asin_monthly.loc[asin_monthly['amount_purchased'].idxmax(), 'month']
                low_month = asin_monthly.loc[asin_monthly['amount_purchased'].idxmin(), 'month']
                
                seasonal_insights[asin] = {
                    'peak_month': int(peak_month),
                    'low_month': int(low_month),
                    'seasonal_variation': float(asin_monthly['amount_purchased'].std()),
                    'monthly_data': asin_monthly.to_dict('records'),
                    'quarterly_data': asin_quarterly.to_dict('records')
                }
        
        return seasonal_insights
    
    def _analyze_cash_flow_impact(self, df: pd.DataFrame) -> Dict:
        """Analyze cash flow impact of purchase decisions"""
        cash_flow_analysis = {}
        
        # Group by month to analyze cash flow patterns
        monthly_cash_flow = df.groupby(df['date'].dt.to_period('M')).agg({
            'amount_purchased': 'sum',
            'cogs': lambda x: (x * df.loc[x.index, 'amount_purchased']).sum()
        }).reset_index()
        
        monthly_cash_flow['period'] = monthly_cash_flow['date'].astype(str)
        monthly_cash_flow['total_investment'] = monthly_cash_flow['cogs']
        
        # Current month analysis
        current_month_data = df[df['date'].dt.month == self.current_month]
        if not current_month_data.empty:
            current_month_investment = (current_month_data['cogs'] * current_month_data['amount_purchased']).sum()
            current_month_units = current_month_data['amount_purchased'].sum()
        else:
            current_month_investment = 0
            current_month_units = 0
        
        cash_flow_analysis = {
            'monthly_trends': monthly_cash_flow.to_dict('records'),
            'current_month_investment': float(current_month_investment),
            'current_month_units': int(current_month_units),
            'avg_monthly_investment': float(monthly_cash_flow['total_investment'].mean()),
            'cash_flow_recommendations': self._generate_cash_flow_recommendations(monthly_cash_flow)
        }
        
        return cash_flow_analysis
    
    def _generate_summary_metrics(self, df: pd.DataFrame) -> Dict:
        """Generate high-level summary metrics"""
        total_asins = df['asin'].nunique()
        total_purchases = len(df)
        total_units = df['amount_purchased'].sum()
        total_investment = (df['cogs'] * df['amount_purchased']).sum()
        avg_purchase_value = total_investment / total_purchases if total_purchases > 0 else 0
        
        # Recent activity (last 30 days)
        recent_cutoff = datetime.now() - timedelta(days=30)
        recent_data = df[df['date'] >= recent_cutoff]
        recent_asins = recent_data['asin'].nunique()
        recent_investment = (recent_data['cogs'] * recent_data['amount_purchased']).sum()
        
        return {
            'total_asins_tracked': int(total_asins),
            'total_purchase_records': int(total_purchases),
            'total_units_purchased': int(total_units),
            'total_investment': float(total_investment),
            'avg_purchase_value': float(avg_purchase_value),
            'recent_30d_asins': int(recent_asins),
            'recent_30d_investment': float(recent_investment),
            'analysis_date_range': {
                'start': df['date'].min().isoformat() if not df.empty else None,
                'end': df['date'].max().isoformat() if not df.empty else None
            }
        }
    
    def _calculate_frequency_score(self, avg_days_between: Optional[float], days_since_last: int) -> float:
        """Calculate a frequency score (0-100) based on purchase patterns"""
        if avg_days_between is None:
            return 50  # Default score for single purchases
        
        if avg_days_between == 0:
            return 100
            
        # Score based on how overdue the next purchase is
        ratio = days_since_last / avg_days_between
        if ratio >= 2:
            return 100  # Severely overdue
        elif ratio >= 1.5:
            return 80 + (ratio - 1.5) * 40  # 80-100
        elif ratio >= 1:
            return 50 + (ratio - 1) * 60  # 50-80
        else:
            return ratio * 50  # 0-50
    
    def _calculate_recommended_purchase_quantity(self, asin_data: pd.DataFrame, velocity_data: Dict) -> int:
        """Calculate recommended purchase quantity based on historical patterns"""
        avg_qty = velocity_data['avg_quantity_per_purchase']
        trend = velocity_data['purchase_trend']
        
        # Base recommendation on historical average
        base_qty = avg_qty
        
        # Adjust for trend
        if trend > 0.2:  # Strong positive trend
            recommended_qty = base_qty * 1.5
        elif trend > 0:  # Moderate positive trend
            recommended_qty = base_qty * 1.2
        elif trend < -0.2:  # Strong negative trend
            recommended_qty = base_qty * 0.7
        elif trend < 0:  # Moderate negative trend
            recommended_qty = base_qty * 0.9
        else:
            recommended_qty = base_qty
        
        # Round to reasonable number
        return max(1, int(round(recommended_qty)))
    
    def _generate_cash_flow_recommendations(self, monthly_data: pd.DataFrame) -> List[str]:
        """Generate cash flow optimization recommendations"""
        recommendations = []
        
        if len(monthly_data) < 2:
            return ["Need more historical data for cash flow analysis"]
        
        # Analyze spending trend
        recent_avg = monthly_data.tail(3)['total_investment'].mean()
        overall_avg = monthly_data['total_investment'].mean()
        
        if recent_avg > overall_avg * 1.2:
            recommendations.append("Recent spending is 20% above average - consider budget review")
        elif recent_avg < overall_avg * 0.8:
            recommendations.append("Recent spending is below average - opportunity to increase profitable inventory")
        
        # Analyze spending volatility
        std_dev = monthly_data['total_investment'].std()
        cv = std_dev / overall_avg if overall_avg > 0 else 0
        
        if cv > 0.5:
            recommendations.append("High spending volatility detected - consider more consistent purchasing schedule")
        
        if not recommendations:
            recommendations.append("Cash flow appears stable and well-managed")
        
        return recommendations
    
    def _analyze_recent_2_months_purchases(self, df: pd.DataFrame) -> Dict:
        """Analyze purchases from the last 2 worksheets (representing last 2 months due to Amazon lead time)"""
        recent_purchases_data = {}
        
        try:
            # Check if we have worksheet source information
            if '_worksheet_source' not in df.columns:
                pass  # Debug print removed
                return self._analyze_by_date_fallback(df)
            
            # Get the list of unique worksheets, sorted to identify the most recent ones
            worksheets = df['_worksheet_source'].unique()
            
            # Try to identify the last 2 worksheets by sorting (assuming chronological naming)
            # Sort worksheets to get the most recent ones (assuming they're named chronologically)
            sorted_worksheets = sorted(worksheets, reverse=True)
            last_2_worksheets = sorted_worksheets[:2]
            
            
            # Filter to only data from the last 2 worksheets
            recent_df = df[df['_worksheet_source'].isin(last_2_worksheets)]
            
            if recent_df.empty:
                pass  # Debug print removed
                return {}
            
            # Group by ASIN and sum amounts purchased from last 2 worksheets
            recent_purchases = recent_df.groupby('asin').agg({
                'amount_purchased': 'sum',
                'date': ['count', 'max', 'min'],  # count, most recent, and earliest date
                'cogs': 'mean',  # average COGS for recent purchases
                '_worksheet_source': lambda x: list(x.unique())  # which worksheets this ASIN appears in
            }).reset_index()
            
            # Flatten column names
            recent_purchases.columns = ['asin', 'total_qty_purchased', 'purchase_count', 'last_purchase_date', 'first_purchase_date', 'avg_cogs', 'source_worksheets']
            
            # Convert to dictionary format
            for _, row in recent_purchases.iterrows():
                asin = row['asin']
                recent_purchases_data[asin] = {
                    'total_quantity_purchased': int(row['total_qty_purchased']),
                    'purchase_count': int(row['purchase_count']),
                    'last_purchase_date': row['last_purchase_date'].isoformat() if pd.notna(row['last_purchase_date']) else None,
                    'first_purchase_date': row['first_purchase_date'].isoformat() if pd.notna(row['first_purchase_date']) else None,
                    'avg_cogs_recent': float(row['avg_cogs']) if pd.notna(row['avg_cogs']) else 0,
                    'source_worksheets': row['source_worksheets'],
                    'analysis_period': f"Last 2 worksheets: {', '.join(last_2_worksheets)}",
                    'worksheets_analyzed': last_2_worksheets
                }
            
            pass  # Debug print removed
            return recent_purchases_data
            
        except Exception as e:
            pass  # Debug print removed
            # Fallback to date-based analysis
            return self._analyze_by_date_fallback(df)
    
    def _analyze_by_date_fallback(self, df: pd.DataFrame) -> Dict:
        """Fallback method using date-based analysis when worksheet info is not available"""
        recent_purchases_data = {}
        
        try:
            # Filter to last 2 months (approximately 60 days) as fallback
            current_date = datetime.now()
            two_months_ago = current_date - timedelta(days=60)
            recent_df = df[df['date'] >= two_months_ago]
            
            if recent_df.empty:
                pass  # Debug print removed
                return {}
            
            # Group by ASIN and sum amounts purchased in last 2 months
            recent_purchases = recent_df.groupby('asin').agg({
                'amount_purchased': 'sum',
                'date': ['count', 'max', 'min'],  # count, most recent, and earliest date
                'cogs': 'mean'  # average COGS for recent purchases
            }).reset_index()
            
            # Flatten column names
            recent_purchases.columns = ['asin', 'total_qty_purchased', 'purchase_count', 'last_purchase_date', 'first_purchase_date', 'avg_cogs']
            
            # Convert to dictionary format
            for _, row in recent_purchases.iterrows():
                asin = row['asin']
                recent_purchases_data[asin] = {
                    'total_quantity_purchased': int(row['total_qty_purchased']),
                    'purchase_count': int(row['purchase_count']),
                    'last_purchase_date': row['last_purchase_date'].isoformat() if pd.notna(row['last_purchase_date']) else None,
                    'first_purchase_date': row['first_purchase_date'].isoformat() if pd.notna(row['first_purchase_date']) else None,
                    'avg_cogs_recent': float(row['avg_cogs']) if pd.notna(row['avg_cogs']) else 0,
                    'analysis_period': f"{two_months_ago.strftime('%Y-%m-%d')} to {current_date.strftime('%Y-%m-%d')} (date fallback)",
                    'days_analyzed': 60
                }
            
            pass  # Debug print removed
            return recent_purchases_data
            
        except Exception as e:
            pass  # Debug print removed
            return {}
    
    def _empty_analytics_response(self) -> Dict:
        """Return empty analytics response when no data is available"""
        return {
            'purchase_velocity_analysis': {},
            'restock_urgency_scoring': {},
            'purchase_pattern_insights': {
                'monthly_spending_trend': [],
                'seasonal_patterns': {},
                'asin_performance_insights': [],
                'cost_efficiency_analysis': {}
            },
            'roi_based_recommendations': {},
            'seasonal_purchase_trends': {},
            'cash_flow_optimization': {
                'monthly_trends': [],
                'current_month_investment': 0,
                'current_month_units': 0,
                'avg_monthly_investment': 0,
                'cash_flow_recommendations': ["No purchase data available for analysis"]
            },
            'summary_metrics': {
                'total_asins_tracked': 0,
                'total_purchase_records': 0,
                'total_units_purchased': 0,
                'total_investment': 0,
                'avg_purchase_value': 0,
                'recent_30d_asins': 0,
                'recent_30d_investment': 0,
                'analysis_date_range': {'start': None, 'end': None}
            },
            'recent_2_months_purchases': {},
            'error': 'No purchase data available for analysis'
        }