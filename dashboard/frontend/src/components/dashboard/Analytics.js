import React, { useState, useEffect } from 'react';
import { AlertTriangle } from 'lucide-react';
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  Legend, 
  ResponsiveContainer,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell
} from 'recharts';
import axios from 'axios';

const Analytics = () => {
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedDate, setSelectedDate] = useState('');
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchAnalytics();
  }, [selectedDate]);

  const fetchAnalytics = async () => {
    try {
      setError(null);
      setLoading(true);
      const url = selectedDate ? 
        `/api/analytics/orders?date=${selectedDate}` : 
        '/api/analytics/orders';
      
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

  // Prepare chart data
  const getSalesChartData = () => {
    if (!analytics || !analytics.today_sales) return [];
    
    return Object.entries(analytics.today_sales)
      .sort(([,a], [,b]) => b - a)
      .slice(0, 10)
      .map(([asin, sales]) => ({
        asin: asin.substring(0, 8) + '...',
        sales,
        velocity: analytics.velocity?.[asin]?.pct || 0
      }));
  };

  const getVelocityChartData = () => {
    if (!analytics || !analytics.velocity) return [];
    
    return Object.entries(analytics.velocity)
      .filter(([, data]) => data.today > 0)
      .sort(([,a], [,b]) => b.pct - a.pct)
      .slice(0, 10)
      .map(([asin, data]) => ({
        asin: asin.substring(0, 8) + '...',
        today: data.today,
        yesterday: data.yesterday,
        change: data.pct
      }));
  };

  const getStockLevelData = () => {
    if (!analytics || !analytics.stockout_30d) return [];
    
    const categories = {
      'Critical (< 7 days)': 0,
      'Low (7-14 days)': 0,
      'Medium (14-30 days)': 0,
      'Good (> 30 days)': 0
    };

    Object.values(analytics.stockout_30d).forEach(item => {
      if (item.days_left < 7) categories['Critical (< 7 days)']++;
      else if (item.days_left < 14) categories['Low (7-14 days)']++;
      else if (item.days_left < 30) categories['Medium (14-30 days)']++;
      else categories['Good (> 30 days)']++;
    });

    return Object.entries(categories).map(([name, value]) => ({ name, value }));
  };

  const COLORS = ['#ef4444', '#f97316', '#eab308', '#22c55e'];

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
      {/* Header with Date Selector */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Sales Analytics</h1>
          <p className="text-gray-600">
            Data for {getReportDate()} {analytics?.is_yesterday && '(Yesterday)'}
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <label htmlFor="date-select" className="text-sm font-medium text-gray-700">
            Select Date:
          </label>
          <input
            id="date-select"
            type="date"
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
            max={new Date(Date.now() - 86400000).toISOString().split('T')[0]} // Yesterday max
            className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-builders-500 focus:border-transparent"
          />
          <button
            onClick={fetchAnalytics}
            disabled={loading}
            className="btn-primary disabled:opacity-50"
          >
            {loading ? 'Loading...' : 'Refresh'}
          </button>
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-md p-4">
          <p className="text-red-800">{error}</p>
        </div>
      )}

      {/* Sales Performance Chart */}
      <div className="card">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Top Products by Sales Volume</h3>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={getSalesChartData()}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="asin" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Bar dataKey="sales" fill="#5865f2" name="Units Sold" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Velocity Analysis */}
      <div className="card">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Sales Velocity Comparison</h3>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={getVelocityChartData()}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="asin" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Bar dataKey="today" fill="#5865f2" name="Today" />
            <Bar dataKey="yesterday" fill="#94a3b8" name="Yesterday" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Stock Level Distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Stock Level Distribution</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={getStockLevelData()}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                outerRadius={80}
                fill="#8884d8"
                dataKey="value"
              >
                {getStockLevelData().map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Key Metrics</h3>
          <div className="space-y-4">
            <div className="flex justify-between items-center py-3 border-b border-gray-200">
              <span className="text-sm font-medium text-gray-600">Total Units Sold Today</span>
              <span className="text-lg font-semibold text-gray-900">
                {analytics && analytics.today_sales ? Object.values(analytics.today_sales).reduce((a, b) => a + b, 0) : 0}
              </span>
            </div>
            <div className="flex justify-between items-center py-3 border-b border-gray-200">
              <span className="text-sm font-medium text-gray-600">Active SKUs</span>
              <span className="text-lg font-semibold text-gray-900">
                {analytics && analytics.today_sales ? Object.keys(analytics.today_sales).length : 0}
              </span>
            </div>
            <div className="flex justify-between items-center py-3 border-b border-gray-200">
              <span className="text-sm font-medium text-gray-600">Products with Low Stock</span>
              <span className="text-lg font-semibold text-red-600">
                {analytics && analytics.low_stock ? Object.keys(analytics.low_stock).length : 0}
              </span>
            </div>
            <div className="flex justify-between items-center py-3 border-b border-gray-200">
              <span className="text-sm font-medium text-gray-600">High Priority Restocks</span>
              <span className="text-lg font-semibold text-orange-600">
                {analytics && analytics.restock_priority ? Object.keys(analytics.restock_priority).length : 0}
              </span>
            </div>
            <div className="flex justify-between items-center py-3">
              <span className="text-sm font-medium text-gray-600">30-Day Stockout Risk</span>
              <span className="text-lg font-semibold text-red-600">
                {analytics && analytics.stockout_30d ? Object.keys(analytics.stockout_30d).length : 0}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Detailed Tables */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Velocity Leaders */}
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Velocity Leaders</h3>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">ASIN</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Today</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Change</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {analytics && analytics.velocity && Object.entries(analytics.velocity)
                  .filter(([, data]) => data.pct > 0)
                  .sort(([,a], [,b]) => b.pct - a.pct)
                  .slice(0, 5)
                  .map(([asin, data]) => (
                    <tr key={asin}>
                      <td className="px-4 py-4 text-sm font-medium text-gray-900">{asin}</td>
                      <td className="px-4 py-4 text-sm text-gray-900">{data.today}</td>
                      <td className="px-4 py-4 text-sm text-green-600">+{data.pct.toFixed(1)}%</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Stock Alerts */}
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Critical Stock Alerts</h3>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">ASIN</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Days Left</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Reorder Qty</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {analytics && analytics.low_stock && Object.entries(analytics.low_stock)
                  .slice(0, 5)
                  .map(([asin, info]) => (
                    <tr key={asin}>
                      <td className="px-4 py-4 text-sm font-medium text-gray-900">{asin}</td>
                      <td className="px-4 py-4 text-sm text-red-600">{info.days_left}</td>
                      <td className="px-4 py-4 text-sm text-gray-900">{info.reorder_qty}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Analytics;