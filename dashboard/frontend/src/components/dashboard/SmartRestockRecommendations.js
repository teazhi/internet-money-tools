import React, { useState, useEffect, useMemo, useCallback } from 'react';
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

// Skeleton component for Smart Restock Alerts
const SmartRestockAlertsSkeleton = () => {
  return (
    <div className="bg-white rounded-lg shadow">
      <div className="px-6 py-4">
        <div className="h-4 bg-gray-300 rounded w-96 mb-3 animate-pulse"></div>
        
        {/* Filter Controls Skeleton */}
        <div className="flex flex-col sm:flex-row gap-4 mb-6">
          <div className="flex-1">
            <div className="h-8 bg-gray-300 rounded animate-pulse"></div>
          </div>
          <div className="flex gap-2">
            <div className="h-8 bg-gray-300 rounded w-24 animate-pulse"></div>
            <div className="h-8 bg-gray-300 rounded w-20 animate-pulse"></div>
          </div>
        </div>
        
        {/* Table Headers Skeleton */}
        <div className="overflow-x-auto">
          <div className="min-w-full">
            <div className="border-b border-gray-200">
              <div className="flex bg-gray-50 py-2 px-3">
                <div className="h-4 bg-gray-300 rounded w-20 mx-2 animate-pulse"></div>
                <div className="h-4 bg-gray-300 rounded w-16 mx-2 animate-pulse"></div>
                <div className="h-4 bg-gray-300 rounded w-20 mx-2 animate-pulse"></div>
                <div className="h-4 bg-gray-300 rounded w-16 mx-2 animate-pulse"></div>
                <div className="h-4 bg-gray-300 rounded w-16 mx-2 animate-pulse"></div>
                <div className="h-4 bg-gray-300 rounded w-12 mx-2 animate-pulse"></div>
                <div className="h-4 bg-gray-300 rounded w-16 mx-2 animate-pulse"></div>
                <div className="h-4 bg-gray-300 rounded w-20 mx-2 animate-pulse"></div>
                <div className="h-4 bg-gray-300 rounded w-20 mx-2 animate-pulse"></div>
                <div className="h-4 bg-gray-300 rounded w-16 mx-2 animate-pulse"></div>
              </div>
            </div>
            
            {/* Table Rows Skeleton */}
            <div className="divide-y divide-gray-200">
              {[1, 2, 3, 4, 5, 6, 7, 8].map(i => (
                <div key={i} className="flex py-3 px-3 animate-pulse">
                  {/* Product column */}
                  <div className="flex-1 px-2">
                    <div className="h-4 bg-gray-300 rounded w-32 mb-1"></div>
                    <div className="h-3 bg-gray-300 rounded w-24"></div>
                  </div>
                  
                  {/* Priority column */}
                  <div className="w-20 px-2">
                    <div className="h-5 bg-gray-300 rounded w-16"></div>
                  </div>
                  
                  {/* Stock column */}
                  <div className="w-20 px-2">
                    <div className="h-4 bg-gray-300 rounded w-8"></div>
                  </div>
                  
                  {/* Days left column */}
                  <div className="w-16 px-2">
                    <div className="h-4 bg-gray-300 rounded w-12"></div>
                  </div>
                  
                  {/* Velocity column */}
                  <div className="w-16 px-2">
                    <div className="h-4 bg-gray-300 rounded w-12"></div>
                  </div>
                  
                  {/* Trend column */}
                  <div className="w-12 px-2">
                    <div className="h-4 w-4 bg-gray-300 rounded mx-auto"></div>
                  </div>
                  
                  {/* COGS column */}
                  <div className="w-16 px-2">
                    <div className="h-4 bg-gray-300 rounded w-12 mb-1"></div>
                    <div className="h-3 bg-gray-300 rounded w-10"></div>
                  </div>
                  
                  {/* Already ordered column */}
                  <div className="w-20 px-2">
                    <div className="h-4 bg-gray-300 rounded w-8"></div>
                  </div>
                  
                  {/* Suggested order column */}
                  <div className="w-20 px-2">
                    <div className="h-5 bg-gray-300 rounded w-8 mb-1"></div>
                    <div className="h-3 bg-gray-300 rounded w-12"></div>
                  </div>
                  
                  {/* Actions column */}
                  <div className="w-16 px-2">
                    <div className="h-6 bg-gray-300 rounded w-14"></div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
        
        {/* Loading indicator */}
        <div className="text-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-builders-500 mx-auto mb-2"></div>
          <p className="text-gray-600 text-sm">Loading smart restock recommendations...</p>
          <p className="text-gray-500 text-xs mt-1">Analyzing inventory levels and sales velocity</p>
        </div>
      </div>
    </div>
  );
};

const SmartRestockRecommendations = () => {
  const { user } = useAuth();
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedDate, setSelectedDate] = useState('');

  const fetchAnalytics = useCallback(async () => {
    let url;
    try {
      setError(null);
      setLoading(true);
      
      url = selectedDate ? 
        `${API_ENDPOINTS.ANALYTICS_ORDERS}?date=${selectedDate}` : 
        API_ENDPOINTS.ANALYTICS_ORDERS;
      
      let response;
      try {
        response = await axios.get(url, { withCredentials: true });
      } catch (axiosError) {
        // Re-throw with better error handling
        throw axiosError;
      }
      
      setAnalytics(response.data);
      
      if (response.data.error) {
        setError(response.data.error);
      }
    } catch (error) {
      // Handle the TypeError first
      if (error.message && error.message.includes('isCheckout')) {
        // This might be an error from middleware or interceptor
        // Try to extract the actual error
        if (error.response) {
          error = error.response;
        }
      }
      
      
      // Check if this is a setup requirement error
      if (error.response?.status === 400 && error.response?.data?.requires_setup) {
        setError({
          type: 'setup_required',
          message: error.response.data.message || 'Please configure your report URLs in Settings before accessing analytics.',
          title: 'Setup Required'
        });
      } else if (error.response?.status === 401 || error.status === 401) {
        setError({
          type: 'auth_required',
          message: 'Please log in with Discord to access your analytics dashboard.',
          title: 'Authentication Required'
        });
      } else {
        // Show more detailed error information
        const errorMessage = error.response?.data?.message || 
                           error.response?.data?.error || 
                           error.data?.message ||
                           error.data?.error ||
                           error.message || 
                           'Failed to fetch analytics data';
        const statusText = error.response?.status || error.status ? ` (Status: ${error.response?.status || error.status})` : '';
        
        setError({
          type: 'general',
          message: `${errorMessage}${statusText}`,
          title: 'Error'
        });
      }
    } finally {
      setLoading(false);
    }
  }, [selectedDate]);

  useEffect(() => {
    fetchAnalytics();
  }, [fetchAnalytics]);

  const getReportDate = () => {
    if (analytics?.report_date) {
      // Parse the date string as local time to avoid timezone issues
      const reportDateStr = analytics.report_date; // YYYY-MM-DD format
      const [year, month, day] = reportDateStr.split('-').map(Number);
      const date = new Date(year, month - 1, day); // month is 0-based in JS
      
      // Use user's timezone from analytics if available
      const userTimezone = analytics?.user_timezone;
      
      const options = {
        weekday: 'long', 
        year: 'numeric', 
        month: 'long', 
        day: 'numeric',
        ...(userTimezone && { timeZone: userTimezone })
      };
      
      return date.toLocaleDateString('en-US', options);
    }
    return 'Unknown Date';
  };

  const getTrendIcon = useCallback((trend) => {
    switch (trend) {
      case 'accelerating':
        return <TrendingUp className="h-4 w-4 text-green-500" />;
      case 'declining':
        return <TrendingDown className="h-4 w-4 text-red-500" />;
      default:
        return <Minus className="h-4 w-4 text-gray-400" />;
    }
  }, []);


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

  // Don't show full page skeleton - show header immediately and skeleton only the data

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

  // Show timeout error
  if (error?.type === 'timeout') {
    return (
      <div className="space-y-6">
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6">
          <div className="flex">
            <div className="flex-shrink-0">
              <AlertTriangle className="h-5 w-5 text-yellow-400" />
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-yellow-800">
                {error.title}
              </h3>
              <div className="mt-2 text-sm text-yellow-700">
                <p>{error.message}</p>
                <p className="mt-1">Enhanced analytics processes large amounts of data and may take longer than usual.</p>
              </div>
              <div className="mt-4">
                <button
                  onClick={fetchAnalytics}
                  disabled={loading}
                  className="bg-yellow-100 hover:bg-yellow-200 text-yellow-800 text-sm font-medium py-2 px-3 rounded-md transition-colors duration-200 disabled:opacity-50"
                >
                  {loading ? 'Retrying...' : 'Try Again'}
                </button>
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
                  disabled={loading}
                  className="bg-red-100 hover:bg-red-200 text-red-800 text-sm font-medium py-2 px-3 rounded-md transition-colors duration-200 disabled:opacity-50"
                >
                  {loading ? 'Retrying...' : 'Try Again'}
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
      {/* Header with Date Selector */}
      <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center space-y-3 sm:space-y-0">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Smart Restock Recommendations</h1>
          <p className="text-xs text-gray-600">
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
            className="px-2 py-1.5 text-xs border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-builders-500 focus:border-transparent"
            title={analytics?.user_timezone ? `Dates shown in ${analytics.user_timezone}` : 'Dates shown in system timezone'}
          />
          <button
            onClick={fetchAnalytics}
            disabled={loading}
            className="flex items-center px-2 py-1.5 text-xs bg-builders-500 text-white rounded-md hover:bg-builders-600 disabled:opacity-50"
          >
            <RefreshCw className={`h-3 w-3 mr-1 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          <button
            onClick={exportAnalytics}
            className="flex items-center px-2 py-1.5 text-xs bg-gray-500 text-white rounded-md hover:bg-gray-600"
          >
            <Download className="h-3 w-3 mr-1" />
            Export
          </button>
        </div>
      </div>


      {/* Smart Restock Alerts */}
      {loading && !analytics ? (
        <SmartRestockAlertsSkeleton />
      ) : (
        <SmartRestockAlerts analytics={analytics} loading={loading} />
      )}

    </div>
  );
};

export default SmartRestockRecommendations;