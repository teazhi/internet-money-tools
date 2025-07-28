import React, { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { 
  TrendingUp, 
  TrendingDown,
  Minus,
  AlertTriangle, 
  Package, 
  Target,
  BarChart3,
  RefreshCw,
  Clock,
  Zap,
  Filter,
  Download
} from 'lucide-react';
import axios from 'axios';
import SmartRestockAlerts from '../SmartRestockAlerts';
import { API_ENDPOINTS } from '../../config/api';

const EnhancedAnalytics = () => {
  const { user } = useAuth();
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedDate, setSelectedDate] = useState('');
  const [filterCategory, setFilterCategory] = useState('all');
  const [sortBy, setSortBy] = useState('priority');

  useEffect(() => {
    fetchAnalytics();
  }, [selectedDate]);

  const fetchAnalytics = async () => {
    try {
      setError(null);
      setLoading(true);
      const url = selectedDate ? 
        `${API_ENDPOINTS.ANALYTICS_ORDERS}?date=${selectedDate}` : 
        API_ENDPOINTS.ANALYTICS_ORDERS;
      
      const response = await axios.get(url, { withCredentials: true });
      setAnalytics(response.data);
      
      if (response.data.error) {
        setError(response.data.error);
      }
    } catch (error) {
      console.error('Error fetching analytics:', error);
      
      // Check if this is a setup requirement error
      if (error.response?.status === 400 && error.response?.data?.requires_setup) {
        setError({
          type: 'setup_required',
          message: error.response.data.message || 'Please configure your report URLs in Settings before accessing analytics.',
          title: 'Setup Required'
        });
      } else if (error.response?.status === 401) {
        setError({
          type: 'auth_required',
          message: 'Please log in with Discord to access your analytics dashboard.',
          title: 'Authentication Required'
        });
      } else {
        setError({
          type: 'general',
          message: 'Failed to fetch analytics data',
          title: 'Error'
        });
      }
    } finally {
      setLoading(false);
    }
  };

  const getReportDate = () => {
    if (analytics?.report_date) {
      const date = new Date(analytics.report_date);
      return date.toLocaleDateString('en-US', { 
        weekday: 'long', 
        year: 'numeric', 
        month: 'long', 
        day: 'numeric' 
      });
    }
    return 'Unknown Date';
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

  const getFilteredProducts = () => {
    if (!analytics?.enhanced_analytics || analytics.enhanced_analytics === null) return [];
    
    let products = Object.entries(analytics.enhanced_analytics);
    
    // Filter by category
    if (filterCategory !== 'all') {
      products = products.filter(([asin, data]) => {
        const category = data?.priority?.category || '';
        switch (filterCategory) {
          case 'critical':
            return category.includes('critical');
          case 'warning':
            return category.includes('warning');
          case 'opportunity':
            return category.includes('opportunity');
          default:
            return true;
        }
      });
    }
    
    // Sort products
    products.sort(([,a], [,b]) => {
      switch (sortBy) {
        case 'priority':
          return (b?.priority?.score || 0) - (a?.priority?.score || 0);
        case 'velocity':
          return (b?.velocity?.weighted_velocity || 0) - (a?.velocity?.weighted_velocity || 0);
        case 'stock':
          return (a?.restock?.current_stock || 0) - (b?.restock?.current_stock || 0);
        case 'name':
          return (a?.product_name || '').localeCompare(b?.product_name || '');
        default:
          return 0;
      }
    });
    
    return products;
  };

  const exportAnalytics = () => {
    if (!analytics) return;
    
    const exportData = {
      report_date: analytics.report_date,
      enhanced_analytics: analytics.enhanced_analytics,
      summary: {
        total_products: analytics.total_products_analyzed,
        high_priority_count: analytics.high_priority_count,
        critical_alerts: analytics.critical_alerts?.length || 0
      }
    };
    
    const dataStr = JSON.stringify(exportData, null, 2);
    const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);
    const exportFileDefaultName = `analytics-${analytics.report_date || 'latest'}.json`;
    
    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', dataUri);
    linkElement.setAttribute('download', exportFileDefaultName);
    linkElement.click();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-builders-500"></div>
      </div>
    );
  }

  // Show setup required alert
  if (error?.type === 'setup_required') {
    return (
      <div className="space-y-6">
        <div className="bg-red-50 border border-red-200 rounded-lg p-6">
          <div className="flex">
            <div className="flex-shrink-0">
              <AlertTriangle className="h-5 w-5 text-red-400" />
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-red-800">
                {error.title}
              </h3>
              <div className="mt-2 text-sm text-red-700">
                <p>{error.message}</p>
              </div>
              <div className="mt-4">
                <div className="flex space-x-2">
                  <a
                    href="/dashboard/settings"
                    className="bg-red-100 hover:bg-red-200 text-red-800 text-sm font-medium py-2 px-3 rounded-md transition-colors duration-200"
                  >
                    Go to Settings
                  </a>
                  <button
                    onClick={fetchAnalytics}
                    className="bg-white hover:bg-gray-50 text-red-800 text-sm font-medium py-2 px-3 rounded-md border border-red-300 transition-colors duration-200"
                  >
                    Try Again
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Show auth required alert
  if (error?.type === 'auth_required') {
    return (
      <div className="space-y-6">
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
          <div className="flex">
            <div className="flex-shrink-0">
              <AlertTriangle className="h-5 w-5 text-blue-400" />
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-blue-800">
                {error.title}
              </h3>
              <div className="mt-2 text-sm text-blue-700">
                <p>{error.message}</p>
              </div>
              <div className="mt-4">
                <div className="flex space-x-2">
                  <a
                    href="/auth/discord"
                    className="bg-blue-100 hover:bg-blue-200 text-blue-800 text-sm font-medium py-2 px-3 rounded-md transition-colors duration-200"
                  >
                    Login with Discord
                  </a>
                  <button
                    onClick={fetchAnalytics}
                    className="bg-white hover:bg-gray-50 text-blue-800 text-sm font-medium py-2 px-3 rounded-md border border-blue-300 transition-colors duration-200"
                  >
                    Try Again
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Show general error
  if (error?.type === 'general') {
    return (
      <div className="space-y-6">
        <div className="bg-red-50 border border-red-200 rounded-lg p-6">
          <div className="flex">
            <div className="flex-shrink-0">
              <AlertTriangle className="h-5 w-5 text-red-400" />
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-red-800">
                {error.title}
              </h3>
              <div className="mt-2 text-sm text-red-700">
                <p>{error.message}</p>
              </div>
              <div className="mt-4">
                <button
                  onClick={fetchAnalytics}
                  className="bg-red-100 hover:bg-red-200 text-red-800 text-sm font-medium py-2 px-3 rounded-md transition-colors duration-200"
                >
                  Try Again
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const filteredProducts = getFilteredProducts();

  return (
    <div className="space-y-6">
      {/* Header with Date Selector */}
      <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center space-y-4 sm:space-y-0">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Enhanced Analytics</h1>
          <p className="text-gray-600">
            AI-powered inventory insights for {getReportDate()} {analytics?.is_yesterday && '(Yesterday)'}
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <input
            type="date"
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
            max={(() => {
              // Get maximum date based on user's timezone
              const userTimezone = analytics?.user_timezone;
              if (userTimezone) {
                try {
                  const now = new Date();
                  const userNow = new Date(now.toLocaleString("en-US", {timeZone: userTimezone}));
                  // Allow up to yesterday in user's timezone
                  const yesterday = new Date(userNow);
                  yesterday.setDate(userNow.getDate() - 1);
                  return yesterday.toISOString().split('T')[0];
                } catch (e) {
                  // Fallback to system timezone
                  return new Date(Date.now() - 86400000).toISOString().split('T')[0];
                }
              }
              return new Date(Date.now() - 86400000).toISOString().split('T')[0];
            })()}
            className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-builders-500 focus:border-transparent"
            title={analytics?.user_timezone ? `Dates shown in ${analytics.user_timezone}` : 'Dates shown in system timezone'}
          />
          <button
            onClick={fetchAnalytics}
            disabled={loading}
            className="flex items-center px-3 py-2 bg-builders-500 text-white rounded-md hover:bg-builders-600 disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          <button
            onClick={exportAnalytics}
            className="flex items-center px-3 py-2 bg-gray-500 text-white rounded-md hover:bg-gray-600"
          >
            <Download className="h-4 w-4 mr-2" />
            Export
          </button>
        </div>
      </div>

      {/* Enhanced Analytics Stats */}
      {analytics?.enhanced_analytics && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center">
              <BarChart3 className="h-8 w-8 text-blue-500" />
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-600">Products Analyzed</p>
                <p className="text-2xl font-bold text-gray-900">{analytics.total_products_analyzed}</p>
              </div>
            </div>
          </div>
          
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center">
              <AlertTriangle className="h-8 w-8 text-red-500" />
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-600">Critical Alerts</p>
                <p className="text-2xl font-bold text-gray-900">{analytics.critical_alerts?.length || 0}</p>
              </div>
            </div>
          </div>
          
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center">
              <Target className="h-8 w-8 text-builders-500" />
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-600">High Priority</p>
                <p className="text-2xl font-bold text-gray-900">{analytics.high_priority_count}</p>
              </div>
            </div>
          </div>
          
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center">
              <Zap className="h-8 w-8 text-green-500" />
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-600">Avg Velocity</p>
                <p className="text-2xl font-bold text-gray-900">
                  {filteredProducts && filteredProducts.length > 0 
                    ? (filteredProducts.reduce((sum, [,data]) => sum + (data?.velocity?.weighted_velocity || 0), 0) / filteredProducts.length).toFixed(1)
                    : '0'
                  }
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Smart Restock Alerts */}
      <SmartRestockAlerts analytics={analytics} />

      {/* Detailed Analytics Table */}
      {analytics?.enhanced_analytics && (
        <div className="bg-white rounded-lg shadow">
          <div className="px-6 py-4 border-b border-gray-200">
            <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center space-y-4 sm:space-y-0">
              <h3 className="text-lg font-medium text-gray-900">Detailed Product Analytics</h3>
              
              <div className="flex items-center space-x-4">
                <select
                  value={filterCategory}
                  onChange={(e) => setFilterCategory(e.target.value)}
                  className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-builders-500"
                >
                  <option value="all">All Categories</option>
                  <option value="critical">Critical Only</option>
                  <option value="warning">Warning Only</option>
                  <option value="opportunity">Opportunities</option>
                </select>
                
                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value)}
                  className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-builders-500"
                >
                  <option value="priority">Sort by Priority</option>
                  <option value="velocity">Sort by Velocity</option>
                  <option value="stock">Sort by Stock Level</option>
                  <option value="name">Sort by Name</option>
                </select>
              </div>
            </div>
          </div>
          
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Product
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Velocity Analysis
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Stock Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Restock Recommendation
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Priority
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {filteredProducts.map(([asin, data]) => (
                  <tr key={asin} className="hover:bg-gray-50">
                    <td className="px-6 py-4">
                      <div>
                        <div className="text-sm font-medium text-gray-900">
                          {data?.product_name && data.product_name.length > 60 
                            ? data.product_name.substring(0, 60) + '...'
                            : data?.product_name || 'Unknown Product'
                          }
                        </div>
                        <div className="text-sm text-gray-500">{asin}</div>
                        {(data?.stock_info?.Source || 
                          data?.stock_info?.source ||
                          data?.stock_info?.['Source Link'] ||
                          data?.stock_info?.['source link'] ||
                          data?.stock_info?.Link ||
                          data?.stock_info?.link ||
                          data?.stock_info?.URL ||
                          data?.stock_info?.url ||
                          asin) && (
                          <div className="mt-1">
                            <a 
                              href={data.stock_info.Source ||
                                    data.stock_info.source ||
                                    data.stock_info['Source Link'] ||
                                    data.stock_info['source link'] ||
                                    data.stock_info.Link ||
                                    data.stock_info.link ||
                                    data.stock_info.URL ||
                                    data.stock_info.url ||
                                    `https://www.amazon.com/dp/${asin}`} 
                              target="_blank" 
                              rel="noopener noreferrer"
                              className="text-xs text-blue-600 hover:text-blue-800 underline"
                            >
                              {data.stock_info.Source ||
                               data.stock_info.source ||
                               data.stock_info['Source Link'] ||
                               data.stock_info['source link'] ||
                               data.stock_info.Link ||
                               data.stock_info.link ||
                               data.stock_info.URL ||
                               data.stock_info.url 
                               ? 'View Source' : 'View on Amazon'}
                            </a>
                          </div>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="space-y-1">
                        <div className="flex items-center space-x-2">
                          <span className="text-sm font-medium text-gray-900">
                            {data?.velocity?.weighted_velocity?.toFixed(1) || '0'}/day
                          </span>
                          {getTrendIcon(data?.velocity?.trend_direction)}
                          <span className="text-xs text-gray-500 capitalize">
                            {data?.velocity?.trend_direction || 'stable'}
                          </span>
                        </div>
                        <div className="text-xs text-gray-500">
                          7d: {data?.velocity?.period_data?.['7d']?.toFixed(1) || '0'} | 
                          30d: {data?.velocity?.period_data?.['30d']?.toFixed(1) || '0'} |
                          Confidence: {(data?.velocity?.confidence ? (data.velocity.confidence * 100).toFixed(0) : '0')}%
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="space-y-1">
                        <div className="text-sm font-medium text-gray-900">
                          {Math.round(data?.restock?.current_stock || 0)} units
                        </div>
                        <div className="text-xs text-gray-500">
                          {(() => {
                            // Find the days left column (handle spacing variations)
                            const daysLeftValue = data?.stock_info?.['Days of stock left'] || 
                                                 data?.stock_info?.['Days  of stock  left'] || 
                                                 data?.stock_info?.['Days of stock  left'] ||
                                                 data?.stock_info?.['Days  of stock left'];
                            return typeof daysLeftValue === 'number' 
                              ? `${daysLeftValue.toFixed(1)} days left`
                              : daysLeftValue || 'Unknown';
                          })()}
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="space-y-1">
                        <div className="text-sm font-medium text-builders-600">
                          {data?.restock?.suggested_quantity || 0} units
                        </div>
                        <div className="text-xs text-gray-500">
                          {data?.restock?.estimated_coverage_days?.toFixed(1) || '0'} days coverage
                        </div>
                        <div className="text-xs text-gray-400">
                          {data?.restock?.reasoning || 'No data'}
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="space-y-1">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          data?.priority?.category?.includes('critical') 
                            ? 'bg-red-100 text-red-800'
                            : data?.priority?.category?.includes('warning')
                            ? 'bg-builders-100 text-builders-800'
                            : data?.priority?.category?.includes('opportunity')
                            ? 'bg-green-100 text-green-800'
                            : 'bg-gray-100 text-gray-800'
                        }`}>
                          {data?.priority?.emoji || '📊'} {data?.priority?.category?.replace('_', ' ')?.toUpperCase() || 'UNKNOWN'}
                        </span>
                        <div className="text-xs text-gray-500">
                          Score: {data?.priority?.score?.toFixed(2) || '0.00'}
                        </div>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          
          {filteredProducts.length === 0 && (
            <div className="text-center py-12">
              <Package className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-sm font-medium text-gray-900 mb-1">No products found</h3>
              <p className="text-sm text-gray-500">
                Try adjusting your filter criteria
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default EnhancedAnalytics;