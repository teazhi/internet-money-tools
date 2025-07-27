import React from 'react';
import { 
  AlertTriangle, 
  TrendingUp, 
  TrendingDown, 
  Minus,
  Package,
  Clock,
  BarChart3,
  Zap,
  Target
} from 'lucide-react';

const SmartRestockAlerts = ({ analytics }) => {
  // Add error handling for null/undefined analytics
  if (!analytics) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Smart Restock Alerts</h3>
        <p className="text-gray-500">Loading analytics data...</p>
      </div>
    );
  }

  if (!analytics.enhanced_analytics) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Smart Restock Alerts</h3>
        <p className="text-gray-500">No enhanced analytics data available</p>
      </div>
    );
  }

  const { enhanced_analytics, restock_alerts, critical_alerts, high_priority_count } = analytics || {};

  // Sort alerts by priority score - handle null/undefined restock_alerts
  const sortedAlerts = restock_alerts ? Object.values(restock_alerts).sort((a, b) => b.priority_score - a.priority_score) : [];

  const getCategoryStyle = (category) => {
    switch (category) {
      case 'critical_high_velocity':
        return 'bg-red-50 border-red-200 border-l-red-500';
      case 'critical_low_velocity':
        return 'bg-red-50 border-red-200 border-l-red-400';
      case 'warning_high_velocity':
        return 'bg-builders-50 border-builders-200 border-l-builders-500';
      case 'warning_moderate':
        return 'bg-yellow-50 border-yellow-200 border-l-yellow-500';
      case 'opportunity_high_velocity':
        return 'bg-green-50 border-green-200 border-l-green-500';
      default:
        return 'bg-gray-50 border-gray-200 border-l-gray-400';
    }
  };

  const getCategoryLabel = (category) => {
    switch (category) {
      case 'critical_high_velocity':
        return 'CRITICAL - High Velocity';
      case 'critical_low_velocity':
        return 'CRITICAL - Low Velocity';
      case 'warning_high_velocity':
        return 'HIGH PRIORITY';
      case 'warning_moderate':
        return 'MODERATE PRIORITY';
      case 'opportunity_high_velocity':
        return 'OPPORTUNITY';
      default:
        return 'MONITOR';
    }
  };

  const getTrendIcon = (trend) => {
    switch (trend) {
      case 'accelerating':
        return <TrendingUp className="h-4 w-4 text-green-500" />;
      case 'declining':
        return <TrendingDown className="h-4 w-4 text-red-500" />;
      default:
        return <Minus className="h-4 w-4 text-gray-400" />;
    }
  };

  const formatDaysLeft = (daysLeft) => {
    if (typeof daysLeft === 'number') {
      if (daysLeft < 1) return '< 1 day';
      if (daysLeft < 7) return `${daysLeft.toFixed(1)} days`;
      return `${Math.round(daysLeft)} days`;
    }
    return daysLeft || 'Unknown';
  };

  // Helper function to get days left value from stock_info (matching backend logic)
  const getDaysLeftFromStock = (stockInfo) => {
    if (!stockInfo) return 'Unknown';
    
    // List of possible column name patterns for days left
    const possiblePatterns = [
      'Days of stock left',
      'Days Left',
      'Days of Stock Left', 
      'Days Of Stock Left',
      'DaysLeft',
      'Days_Left',
      'Days Stock Left',
      'Stock Days Left',
      'Inventory Days Left',
      'Days Until Out of Stock'
    ];
    
    // First try exact matches (case insensitive)
    for (const pattern of possiblePatterns) {
      for (const key of Object.keys(stockInfo)) {
        if (key.toLowerCase() === pattern.toLowerCase()) {
          const value = stockInfo[key];
          if (value !== null && value !== undefined && String(value).trim() !== '') {
            try {
              return parseFloat(value);
            } catch {
              return value;
            }
          }
        }
      }
    }
    
    // Then try partial matches
    for (const key of Object.keys(stockInfo)) {
      const keyLower = key.toLowerCase().replace(/\s+/g, '').replace(/_/g, '');
      if ((keyLower.includes('days') && keyLower.includes('stock') && keyLower.includes('left')) ||
          (keyLower.includes('days') && keyLower.includes('left')) ||
          (keyLower.includes('stock') && keyLower.includes('days'))) {
        const value = stockInfo[key];
        if (value !== null && value !== undefined && String(value).trim() !== '') {
          try {
            return parseFloat(value);
          } catch {
            return value;
          }
        }
      }
    }
    
    return 'Unknown';
  };

  try {
    return (
      <div className="space-y-6">
        {/* Summary Stats */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center">
            <AlertTriangle className="h-8 w-8 text-red-500" />
            <div className="ml-3">
              <p className="text-sm font-medium text-gray-600">Critical Alerts</p>
              <p className="text-2xl font-bold text-gray-900">{critical_alerts?.length || 0}</p>
            </div>
          </div>
        </div>
        
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center">
            <Target className="h-8 w-8 text-builders-500" />
            <div className="ml-3">
              <p className="text-sm font-medium text-gray-600">High Priority</p>
              <p className="text-2xl font-bold text-gray-900">{high_priority_count || 0}</p>
            </div>
          </div>
        </div>
        
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center">
            <BarChart3 className="h-8 w-8 text-blue-500" />
            <div className="ml-3">
              <p className="text-sm font-medium text-gray-600">Products Analyzed</p>
              <p className="text-2xl font-bold text-gray-900">{analytics.total_products_analyzed || 0}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Restock Alerts */}
      <div className="bg-white rounded-lg shadow">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-medium text-gray-900">Smart Restock Recommendations</h3>
          <p className="text-sm text-gray-600">AI-powered restocking suggestions based on velocity, trends, and seasonality</p>
        </div>
        
        <div className="h-96 overflow-y-auto divide-y divide-gray-200">
          {sortedAlerts.length > 0 ? (
            sortedAlerts.map((alert) => (
              <div key={alert.asin} className={`p-4 border-l-4 ${getCategoryStyle(alert.category)}`}>
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <div className="flex items-center space-x-2 mb-1">
                      <span className="text-lg">{alert.emoji}</span>
                      <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                        {getCategoryLabel(alert.category)}
                      </span>
                    </div>
                    
                    <h4 className="text-base font-medium text-gray-900 mb-1">
                      {alert.product_name.length > 80 ? alert.product_name.substring(0, 80) + '...' : alert.product_name}
                    </h4>
                    
                    <p className="text-sm text-gray-600 mb-2">
                      ASIN: {alert.asin}
                      {(enhanced_analytics?.[alert.asin]?.stock_info?.Source || 
                        enhanced_analytics?.[alert.asin]?.stock_info?.source ||
                        enhanced_analytics?.[alert.asin]?.stock_info?.['Source Link'] ||
                        enhanced_analytics?.[alert.asin]?.stock_info?.['source link'] ||
                        enhanced_analytics?.[alert.asin]?.stock_info?.Link ||
                        enhanced_analytics?.[alert.asin]?.stock_info?.link ||
                        enhanced_analytics?.[alert.asin]?.stock_info?.URL ||
                        enhanced_analytics?.[alert.asin]?.stock_info?.url ||
                        alert.asin) && (
                        <>
                          {' • '}
                          <a 
                            href={enhanced_analytics[alert.asin]?.stock_info?.Source ||
                                  enhanced_analytics[alert.asin]?.stock_info?.source ||
                                  enhanced_analytics[alert.asin]?.stock_info?.['Source Link'] ||
                                  enhanced_analytics[alert.asin]?.stock_info?.['source link'] ||
                                  enhanced_analytics[alert.asin]?.stock_info?.Link ||
                                  enhanced_analytics[alert.asin]?.stock_info?.link ||
                                  enhanced_analytics[alert.asin]?.stock_info?.URL ||
                                  enhanced_analytics[alert.asin]?.stock_info?.url ||
                                  `https://www.amazon.com/dp/${alert.asin}`} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            className="text-blue-600 hover:text-blue-800 underline"
                          >
                            {enhanced_analytics[alert.asin]?.stock_info?.Source ||
                             enhanced_analytics[alert.asin]?.stock_info?.source ||
                             enhanced_analytics[alert.asin]?.stock_info?.['Source Link'] ||
                             enhanced_analytics[alert.asin]?.stock_info?.['source link'] ||
                             enhanced_analytics[alert.asin]?.stock_info?.Link ||
                             enhanced_analytics[alert.asin]?.stock_info?.link ||
                             enhanced_analytics[alert.asin]?.stock_info?.URL ||
                             enhanced_analytics[alert.asin]?.stock_info?.url 
                             ? 'View Source' : 'View on Amazon'}
                          </a>
                        </>
                      )}
                    </p>
                    
                    <p className="text-sm text-gray-700 mb-3">
                      {alert.reasoning}
                    </p>
                    
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                      <div className="flex items-center space-x-1">
                        <Package className="h-4 w-4 text-gray-400" />
                        <span className="text-gray-600">Current:</span>
                        <span className="font-medium">{Math.round(alert.current_stock)}</span>
                      </div>
                      
                      <div className="flex items-center space-x-1">
                        <Clock className="h-4 w-4 text-gray-400" />
                        <span className="text-gray-600">Days left:</span>
                        <span className="font-medium">{formatDaysLeft(alert.days_left)}</span>
                      </div>
                      
                      <div className="flex items-center space-x-1">
                        <Zap className="h-4 w-4 text-gray-400" />
                        <span className="text-gray-600">Velocity:</span>
                        <span className="font-medium">{alert.velocity.toFixed(1)}/day</span>
                      </div>
                      
                      <div className="flex items-center space-x-1">
                        {getTrendIcon(alert.trend)}
                        <span className="text-gray-600">Trend:</span>
                        <span className="font-medium capitalize">{alert.trend}</span>
                      </div>
                    </div>
                  </div>
                  
                  <div className="ml-6 text-right">
                    <div className="text-xl font-bold text-builders-600 mb-1">
                      {alert.suggested_quantity}
                    </div>
                    <div className="text-xs text-gray-500 mb-2">
                      units to order
                    </div>
                    <div className="text-xs text-gray-400">
                      Priority: {alert.priority_score.toFixed(2)}
                    </div>
                  </div>
                </div>
              </div>
            ))
          ) : (
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                <Package className="h-12 w-12 text-gray-400 mx-auto mb-3" />
                <h3 className="text-sm font-medium text-gray-900 mb-1">No Priority Alerts</h3>
                <p className="text-sm text-gray-500">
                  All products have adequate stock levels or sufficient lead time
                </p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Enhanced Analytics Summary */}
      {enhanced_analytics && Object.keys(enhanced_analytics).length > 0 && (
        <div className="bg-white rounded-lg shadow">
          <div className="px-6 py-4 border-b border-gray-200">
            <h3 className="text-lg font-medium text-gray-900">All Products Analytics</h3>
            <p className="text-sm text-gray-600">Complete analysis of your inventory</p>
          </div>
          
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Product
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Current Stock
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Velocity
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Trend
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Days Left
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Suggested Order
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Priority
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {enhanced_analytics ? Object.entries(enhanced_analytics)
                  .sort(([,a], [,b]) => b.priority.score - a.priority.score)
                  .slice(0, 20) // Show top 20
                  .map(([asin, data]) => (
                    <tr key={asin} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div>
                          <div className="text-sm font-medium text-gray-900">
                            {data.product_name.length > 50 
                              ? data.product_name.substring(0, 50) + '...'
                              : data.product_name
                            }
                          </div>
                          <div className="text-sm text-gray-500">{asin}</div>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {Math.round(data.restock.current_stock)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {data.velocity.weighted_velocity.toFixed(1)}/day
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center space-x-1">
                          {getTrendIcon(data.velocity.trend_direction)}
                          <span className="text-sm text-gray-900 capitalize">
                            {data.velocity.trend_direction}
                          </span>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {formatDaysLeft(getDaysLeftFromStock(data.stock_info))}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-builders-600">
                        {data.restock.suggested_quantity}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          data.priority.category.includes('critical') 
                            ? 'bg-red-100 text-red-800'
                            : data.priority.category.includes('warning')
                            ? 'bg-builders-100 text-builders-800'
                            : data.priority.category.includes('opportunity')
                            ? 'bg-green-100 text-green-800'
                            : 'bg-gray-100 text-gray-800'
                        }`}>
                          {data.priority.emoji} {getCategoryLabel(data.priority.category)}
                        </span>
                      </td>
                    </tr>
                  )) : []}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
  } catch (error) {
    console.error('Error in SmartRestockAlerts:', error);
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Smart Restock Alerts</h3>
        <p className="text-red-500">Error loading analytics data. Please try refreshing the page.</p>
        <details className="mt-2">
          <summary className="text-sm text-gray-500 cursor-pointer">Error details</summary>
          <pre className="text-xs text-gray-400 mt-1">{error.toString()}</pre>
        </details>
      </div>
    );
  }
};

export default SmartRestockAlerts;