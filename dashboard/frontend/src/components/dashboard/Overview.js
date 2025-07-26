import React, { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { 
  TrendingUp, 
  AlertTriangle, 
  Package, 
  ShoppingCart,
  Calendar,
  DollarSign,
  BarChart3,
  ArrowUp,
  ArrowDown,
  Minus,
  RefreshCw
} from 'lucide-react';
import axios from 'axios';
import SmartRestockAlerts from '../SmartRestockAlerts';

const Overview = () => {
  const { user } = useAuth();
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchAnalytics();
    // Auto-refresh every 5 minutes
    const interval = setInterval(fetchAnalytics, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  const fetchAnalytics = async () => {
    try {
      console.log('Fetching analytics data...');
      setError(null);
      const response = await axios.get('/api/analytics/orders', { 
        withCredentials: true,
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json'
        }
      });
      
      // Ensure proper JSON parsing
      let data = response.data;
      if (typeof data === 'string') {
        console.log('Response received as string, parsing JSON...');
        data = JSON.parse(data);
      }
      
      console.log('Analytics response:', data);
      console.log('Response type:', typeof data);
      console.log('Response keys:', Object.keys(data || {}));
      console.log('Today sales data:', data?.today_sales);
      console.log('Today sales type:', typeof data?.today_sales);
      console.log('Today sales keys count:', Object.keys(data?.today_sales || {}).length);
      console.log('Report date:', data?.report_date);
      setAnalytics(data);
      setLastUpdated(new Date());
      
      if (response.data.error) {
        console.error('Analytics API returned error:', response.data.error);
        setError(response.data.error);
      }
    } catch (error) {
      console.error('Error fetching analytics:', error);
      console.error('Full error details:', {
        message: error.message,
        status: error.response?.status,
        statusText: error.response?.statusText,
        data: error.response?.data,
        hasResponse: !!error.response,
        errorType: typeof error
      });
      
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
    console.log('Getting report date, analytics:', analytics);
    console.log('Report date value:', analytics?.report_date);
    if (analytics?.report_date) {
      const date = new Date(analytics.report_date);
      console.log('Parsed date:', date);
      const formatted = date.toLocaleDateString('en-US', { 
        weekday: 'long', 
        year: 'numeric', 
        month: 'long', 
        day: 'numeric' 
      });
      console.log('Formatted date:', formatted);
      return formatted;
    }
    return 'Unknown Date';
  };

  const getSetupProgress = () => {
    let progress = 0;
    let steps = [];
    
    if (user?.profile_configured) {
      progress += 25;
      steps.push({ name: 'Profile Setup', completed: true });
    } else {
      steps.push({ name: 'Profile Setup', completed: false });
    }
    
    if (user?.google_linked) {
      progress += 25;
      steps.push({ name: 'Google Account Linked', completed: true });
    } else {
      steps.push({ name: 'Google Account Linked', completed: false });
    }
    
    if (user?.sheet_configured) {
      progress += 25;
      steps.push({ name: 'Sheet Configuration', completed: true });
    } else {
      steps.push({ name: 'Sheet Configuration', completed: false });
    }
    
    if (user?.user_record?.run_scripts) {
      progress += 25;
      steps.push({ name: 'Scripts Active', completed: true });
    } else {
      steps.push({ name: 'Scripts Active', completed: false });
    }
    
    return { progress, steps };
  };

  const { progress, steps } = getSetupProgress();

  const formatTrendIcon = (pct) => {
    if (pct > 0) return <ArrowUp className="h-4 w-4 text-green-500" />;
    if (pct < 0) return <ArrowDown className="h-4 w-4 text-red-500" />;
    return <Minus className="h-4 w-4 text-gray-400" />;
  };

  const formatTrendColor = (pct) => {
    if (pct > 0) return 'text-green-600';
    if (pct < 0) return 'text-red-600';
    return 'text-gray-500';
  };

  // Check if user is authenticated (after all hooks)
  if (user === null) {
    return (
      <div className="space-y-6">
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
          <div className="flex">
            <div className="flex-shrink-0">
              <AlertTriangle className="h-5 w-5 text-blue-400" />
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-blue-800">
                Authentication Required
              </h3>
              <div className="mt-2 text-sm text-blue-700">
                <p>Please log in with Discord to access your analytics dashboard.</p>
              </div>
              <div className="mt-4">
                <a
                  href="/auth/discord"
                  className="bg-blue-100 hover:bg-blue-200 text-blue-800 text-sm font-medium py-2 px-3 rounded-md transition-colors duration-200"
                >
                  Login with Discord
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

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

  return (
    <div className="space-y-6">
      {/* Welcome Header */}
      <div className="bg-gradient-to-r from-builders-500 to-builders-600 rounded-lg shadow-sm p-6 text-white">
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-2xl font-bold mb-2">
              Welcome back, {user?.discord_username}!
            </h1>
            <p className="text-builders-100">
              {analytics?.is_yesterday ? 
                `Here's your business overview for ${getReportDate()}` :
                `Here's your business overview for ${getReportDate()}`
              }
            </p>
            {lastUpdated && (
              <p className="text-builders-200 text-sm mt-1">
                Last updated: {lastUpdated.toLocaleTimeString()}
              </p>
            )}
          </div>
          <button
            onClick={fetchAnalytics}
            disabled={loading}
            className="bg-white/20 hover:bg-white/30 p-2 rounded-lg transition-colors duration-200 disabled:opacity-50"
            title="Refresh Data"
          >
            <RefreshCw className={`h-5 w-5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
        {error && (
          <div className="mt-3 p-3 bg-red-500/20 border border-red-400/30 rounded-md">
            <p className="text-red-100 text-sm">{error}</p>
          </div>
        )}
        {analytics?.fallback_mode && (
          <div className="mt-3 p-3 bg-yellow-500/20 border border-yellow-400/30 rounded-md">
            <p className="text-yellow-100 text-sm">⚠️ Running in basic mode. Some features may be limited.</p>
          </div>
        )}
        {analytics?.basic_mode && (
          <div className="mt-3 p-3 bg-blue-500/20 border border-blue-400/30 rounded-md">
            <p className="text-blue-100 text-sm">📊 {analytics.message}</p>
          </div>
        )}
      </div>

      {/* Setup Progress Card (only show if not fully configured) */}
      {progress < 100 && (
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">Setup Progress</h2>
            <span className="text-sm text-gray-500">{progress}% Complete</span>
          </div>
          <div className="mb-4">
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div 
                className="bg-builders-500 h-2 rounded-full transition-all duration-300"
                style={{ width: `${progress}%` }}
              ></div>
            </div>
          </div>
          <div className="space-y-2">
            {steps.map((step, index) => (
              <div key={index} className="flex items-center space-x-2">
                <div className={`w-4 h-4 rounded-full ${step.completed ? 'bg-green-500' : 'bg-gray-300'}`}></div>
                <span className={`text-sm ${step.completed ? 'text-gray-700' : 'text-gray-500'}`}>
                  {step.name}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="card">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <ShoppingCart className="h-8 w-8 text-blue-500" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">
                {analytics?.is_yesterday ? "Yesterday's Orders" : "Today's Orders"}
              </p>
              <p className="text-2xl font-semibold text-gray-900">
                {analytics && analytics.today_sales ? 
                  Object.values(analytics.today_sales).reduce((a, b) => a + b, 0) : 
                  '—'
                }
              </p>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <Package className="h-8 w-8 text-green-500" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Active Products</p>
              <p className="text-2xl font-semibold text-gray-900">
                {analytics && analytics.today_sales ? Object.keys(analytics.today_sales).length : '—'}
              </p>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <AlertTriangle className="h-8 w-8 text-red-500" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Low Stock Alerts</p>
              <p className="text-2xl font-semibold text-gray-900">
                {analytics && analytics.low_stock ? Object.keys(analytics.low_stock).length : '—'}
              </p>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <TrendingUp className="h-8 w-8 text-purple-500" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Restock Priority</p>
              <p className="text-2xl font-semibold text-gray-900">
                {analytics && analytics.restock_priority ? Object.keys(analytics.restock_priority).length : '—'}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Yesterday's Top Sellers */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Yesterday's Top Products</h3>
          <div className="space-y-3">
            {analytics && analytics.today_sales && Object.keys(analytics.today_sales).length > 0 ? 
              Object.entries(analytics.today_sales)
                .sort(([,a], [,b]) => b - a)
                .slice(0, 5)
                .map(([asin, count], index) => (
                  <div key={asin} className="flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      <span className="flex-shrink-0 w-6 h-6 bg-builders-100 text-builders-600 rounded-full flex items-center justify-center text-sm font-medium">
                        {index + 1}
                      </span>
                      <span className="text-sm font-medium text-gray-900">{asin}</span>
                    </div>
                    <div className="flex items-center space-x-2">
                      <span className="text-sm text-gray-600">{count} units</span>
                      {analytics?.velocity?.[asin] && (
                        <div className="flex items-center space-x-1">
                          {formatTrendIcon(analytics.velocity[asin].pct)}
                          <span className={`text-xs ${formatTrendColor(analytics.velocity[asin].pct)}`}>
                            {analytics.velocity[asin].pct > 0 ? '+' : ''}{analytics.velocity[asin].pct.toFixed(1)}%
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                )) : (
              <div className="text-center py-8">
                <Package className="h-12 w-12 text-gray-300 mx-auto mb-4" />
                <p className="text-gray-500 text-sm">
                  {error ? 'Error loading sales data' : 'No sales data available for this date'}
                </p>
                {analytics?.report_date && (
                  <p className="text-gray-400 text-xs mt-1">
                    Showing data for {getReportDate()}
                  </p>
                )}
              </div>
            )}
          </div>
        </div>

        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Stock Alerts</h3>
          <div className="space-y-3">
            {analytics && analytics.low_stock && Object.entries(analytics.low_stock)
              .slice(0, 5)
              .map(([asin, info]) => (
                <div key={asin} className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-900">{asin}</p>
                    <p className="text-xs text-gray-500 truncate max-w-xs">{info.title}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-red-600 font-medium">{info.days_left} days left</p>
                    <p className="text-xs text-gray-500">Reorder: {info.reorder_qty}</p>
                  </div>
                </div>
              ))}
            {(!analytics || !analytics.low_stock || Object.keys(analytics.low_stock).length === 0) && (
              <p className="text-gray-500 text-sm">No stock alerts</p>
            )}
          </div>
        </div>
      </div>

      {/* 30-Day Stockout Risk */}
      {analytics && analytics.stockout_30d && Object.keys(analytics.stockout_30d).length > 0 && (
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">30-Day Stockout Risk</h3>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">ASIN</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Product</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Sold</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Current Stock</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Days Left</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Suggested Reorder</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {analytics.stockout_30d && Object.entries(analytics.stockout_30d).map(([asin, info]) => (
                  <tr key={asin}>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{asin}</td>
                    <td className="px-6 py-4 text-sm text-gray-900 max-w-xs truncate">{info.title}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{info.sold_today}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{info.current_stock}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-red-600 font-medium">{info.days_left}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{info.suggested_reorder}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Smart Restock Alerts */}
      <SmartRestockAlerts analytics={analytics} />
    </div>
  );
};

export default Overview;