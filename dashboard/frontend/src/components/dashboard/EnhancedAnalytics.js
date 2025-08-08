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

const EnhancedAnalytics = () => {
  const { user } = useAuth();
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedDate, setSelectedDate] = useState('');

  const fetchAnalytics = useCallback(async () => {
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

  if (loading && !analytics) {
    return (
      <div className="space-y-6">
        {/* Header Skeleton */}
        <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center space-y-4 sm:space-y-0">
          <div>
            <div className="h-8 bg-gray-300 rounded w-48 mb-2 animate-pulse"></div>
            <div className="h-4 bg-gray-300 rounded w-96 animate-pulse"></div>
          </div>
          <div className="flex items-center space-x-3">
            <div className="h-10 bg-gray-300 rounded w-32 animate-pulse"></div>
            <div className="h-10 bg-gray-300 rounded w-20 animate-pulse"></div>
            <div className="h-10 bg-gray-300 rounded w-20 animate-pulse"></div>
          </div>
        </div>

        {/* Stats Grid Skeleton */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="bg-white rounded-lg shadow p-6 animate-pulse">
              <div className="flex items-center">
                <div className="h-8 w-8 bg-gray-300 rounded"></div>
                <div className="ml-4 flex-1">
                  <div className="h-4 bg-gray-300 rounded w-20 mb-2"></div>
                  <div className="h-8 bg-gray-300 rounded w-12"></div>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Restock Alerts Skeleton */}
        <div className="bg-white rounded-lg shadow">
          <div className="px-6 py-4 border-b border-gray-200">
            <div className="h-6 bg-gray-300 rounded w-64 mb-2 animate-pulse"></div>
            <div className="h-4 bg-gray-300 rounded w-96 animate-pulse"></div>
          </div>
          <div className="p-6 space-y-4">
            {[1, 2, 3, 4, 5].map(i => (
              <div key={i} className="border-l-4 border-gray-200 p-4 animate-pulse">
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <div className="h-4 bg-gray-300 rounded w-32 mb-2"></div>
                    <div className="h-6 bg-gray-300 rounded w-80 mb-2"></div>
                    <div className="h-4 bg-gray-300 rounded w-64 mb-3"></div>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                      {[1, 2, 3, 4].map(j => (
                        <div key={j} className="h-4 bg-gray-300 rounded w-16"></div>
                      ))}
                    </div>
                  </div>
                  <div className="ml-6 text-right">
                    <div className="h-8 bg-gray-300 rounded w-12 mb-1"></div>
                    <div className="h-3 bg-gray-300 rounded w-16 mb-2"></div>
                    <div className="h-3 bg-gray-300 rounded w-12"></div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Loading indicator */}
        <div className="text-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-builders-500 mx-auto mb-2"></div>
          <p className="text-gray-600 text-sm">Loading enhanced analytics and restock recommendations...</p>
          <p className="text-gray-500 text-xs mt-1">This may take a moment to process all your data</p>
        </div>
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
          <h1 className="text-lg font-bold text-gray-900">Enhanced Analytics</h1>
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

      {/* Enhanced Analytics Stats */}
      {analytics?.enhanced_analytics && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="bg-white rounded-lg shadow p-4">
            <div className="flex items-center">
              <BarChart3 className="h-6 w-6 text-blue-500" />
              <div className="ml-3">
                <p className="text-xs font-medium text-gray-600">Products Analyzed</p>
                <p className="text-lg font-bold text-gray-900">{analytics.total_products_analyzed}</p>
              </div>
            </div>
          </div>
          
          <div className="bg-white rounded-lg shadow p-4">
            <div className="flex items-center">
              <AlertTriangle className="h-6 w-6 text-red-500" />
              <div className="ml-3">
                <p className="text-xs font-medium text-gray-600">Critical Alerts</p>
                <p className="text-lg font-bold text-gray-900">{analytics.critical_alerts?.length || 0}</p>
              </div>
            </div>
          </div>
          
          <div className="bg-white rounded-lg shadow p-4">
            <div className="flex items-center">
              <Target className="h-6 w-6 text-builders-500" />
              <div className="ml-3">
                <p className="text-xs font-medium text-gray-600">High Priority</p>
                <p className="text-lg font-bold text-gray-900">{analytics.high_priority_count}</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Smart Restock Alerts */}
      <SmartRestockAlerts analytics={analytics} />

    </div>
  );
};

export default EnhancedAnalytics;