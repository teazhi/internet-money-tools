import React, { useState, useEffect } from 'react';
import { 
  AlertTriangle, 
  TrendingUp, 
  TrendingDown, 
  DollarSign,
  Package,
  Zap,
  AlertCircle,
  Target,
  BarChart3,
  PieChart as PieChartIcon
} from 'lucide-react';
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
  Cell,
  ScatterChart,
  Scatter,
  ComposedChart,
  Area,
  AreaChart
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
      console.log('Analytics data received:', response.data);
      console.log('Enhanced analytics count:', Object.keys(response.data?.enhanced_analytics || {}).length);
      console.log('Today sales count:', Object.keys(response.data?.today_sales || {}).length);
      console.log('Available data keys:', Object.keys(response.data || {}));
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

  // 1. Stock Risk Dashboard - Velocity vs Days Remaining
  const getStockRiskData = () => {
    // Fallback to basic analytics if enhanced analytics is empty
    if (!analytics?.enhanced_analytics || Object.keys(analytics.enhanced_analytics).length === 0) {
      console.log('Using fallback basic analytics for stock risk data');
      if (!analytics?.today_sales || !analytics?.velocity) return [];
      
      return Object.entries(analytics.today_sales)
        .map(([asin, sales]) => {
          const velocityData = analytics.velocity[asin];
          const stockData = analytics.stockout_30d?.[asin];
          
          if (!velocityData || !stockData) return null;
          
          return {
            asin: asin.substring(0, 8),
            velocity: sales, // Use daily sales as velocity
            daysLeft: Math.min(stockData.days_left || 999, 60),
            revenueImpact: sales * 10, // Rough estimate
            category: stockData.days_left < 7 ? 'critical' : stockData.days_left < 14 ? 'warning' : 'monitor',
            fullAsin: asin,
            productName: stockData.title || asin,
            priority: stockData.days_left < 7 ? 1.0 : 0.5
          };
        })
        .filter(Boolean)
        .sort((a, b) => b.revenueImpact - a.revenueImpact);
    }
    
    return Object.entries(analytics.enhanced_analytics)
      .map(([asin, data]) => {
        const velocity = data.velocity?.weighted_velocity || 0;
        const daysLeft = data.stock_info?.['Days left'] || data.stock_info?.['Days of stock left'] || 999;
        const roi = parseFloat(data.stock_info?.['ROI %'] || data.stock_info?.['ROI'] || 0);
        const category = data.priority?.category || 'monitor';
        
        // Calculate potential revenue impact (velocity * ROI * potential lost days)
        const revenueImpact = velocity * roi * Math.min(daysLeft, 30);
        
        return {
          asin: asin.substring(0, 8),
          velocity: velocity,
          daysLeft: Math.min(daysLeft, 60), // Cap for chart visibility
          revenueImpact: revenueImpact,
          category: category,
          fullAsin: asin,
          productName: data.product_name,
          priority: data.priority?.score || 0
        };
      })
      .filter(item => item.velocity > 0) // Only show products with sales
      .sort((a, b) => b.revenueImpact - a.revenueImpact);
  };

  // 2. Revenue Opportunity Analysis - ROI vs Velocity
  const getRevenueOpportunityData = () => {
    if (!analytics?.enhanced_analytics) return [];
    
    return Object.entries(analytics.enhanced_analytics)
      .map(([asin, data]) => {
        const velocity = data.velocity?.weighted_velocity || 0;
        const roi = parseFloat(data.stock_info?.['ROI %'] || data.stock_info?.['ROI'] || 0);
        const margin = parseFloat(data.stock_info?.['Margin'] || 0);
        const revenueOpportunity = velocity * roi;
        
        return {
          asin: asin.substring(0, 8),
          velocity: velocity,
          roi: roi,
          margin: margin,
          opportunity: revenueOpportunity,
          category: data.priority?.category || 'monitor',
          fullAsin: asin,
          productName: data.product_name
        };
      })
      .filter(item => item.velocity > 0)
      .sort((a, b) => b.opportunity - a.opportunity);
  };

  // 3. Velocity Trend Analysis - Multi-period comparison
  const getVelocityTrendData = () => {
    if (!analytics?.enhanced_analytics) return [];
    
    return Object.entries(analytics.enhanced_analytics)
      .slice(0, 12) // Top 12 products
      .map(([asin, data]) => ({
        asin: asin.substring(0, 8),
        '7d': data.velocity?.['7d'] || 0,
        '14d': data.velocity?.['14d'] || 0,
        '30d': data.velocity?.['30d'] || 0,
        '60d': data.velocity?.['60d'] || 0,
        weighted: data.velocity?.weighted_velocity || 0,
        trend: data.velocity?.trend_direction || 'stable'
      }))
      .filter(item => item.weighted > 0)
      .sort((a, b) => b.weighted - a.weighted);
  };

  // 4. Priority Action Matrix
  const getPriorityDistribution = () => {
    if (!analytics?.enhanced_analytics) return [];
    
    const categories = {};
    Object.values(analytics.enhanced_analytics).forEach(data => {
      const category = data.priority?.category || 'monitor';
      categories[category] = (categories[category] || 0) + 1;
    });

    const categoryMapping = {
      'critical_high_velocity': { name: 'Critical High Velocity', color: '#dc2626' },
      'critical_low_velocity': { name: 'Critical Low Velocity', color: '#ea580c' },
      'warning_high_velocity': { name: 'Warning High Velocity', color: '#d97706' },
      'warning_moderate': { name: 'Warning Moderate', color: '#ca8a04' },
      'opportunity_high_velocity': { name: 'Growth Opportunity', color: '#16a34a' },
      'monitor': { name: 'Monitor', color: '#6b7280' }
    };

    return Object.entries(categories).map(([key, value]) => ({
      name: categoryMapping[key]?.name || key,
      value: value,
      color: categoryMapping[key]?.color || '#6b7280'
    }));
  };

  // 5. Restock Financial Impact
  const getRestockImpactData = () => {
    if (!analytics?.enhanced_analytics) return [];
    
    return Object.entries(analytics.enhanced_analytics)
      .map(([asin, data]) => {
        const suggestedQty = data.restock?.suggested_quantity || 0;
        const currentStock = parseFloat(data.stock_info?.['FBA/FBM Stock'] || 0);
        const roi = parseFloat(data.stock_info?.['ROI %'] || data.stock_info?.['ROI'] || 0);
        const velocity = data.velocity?.weighted_velocity || 0;
        
        // Calculate investment required and potential return
        const investment = suggestedQty * (roi > 0 ? 100 / (roi / 100 + 1) : 0); // Rough cost basis
        const potentialReturn = suggestedQty * roi;
        
        return {
          asin: asin.substring(0, 8),
          investment: investment,
          potentialReturn: potentialReturn,
          suggestedQty: suggestedQty,
          currentStock: currentStock,
          velocity: velocity,
          roi: roi,
          paybackDays: velocity > 0 ? suggestedQty / velocity : 999,
          fullAsin: asin,
          productName: data.product_name
        };
      })
      .filter(item => item.suggestedQty > 0)
      .sort((a, b) => b.potentialReturn - a.potentialReturn)
      .slice(0, 15);
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
          <h1 className="text-2xl font-bold text-gray-900">Business Intelligence Dashboard</h1>
          <p className="text-gray-600">
            Comprehensive analytics for {getReportDate()} {analytics?.is_yesterday && '(Yesterday)'}
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
            max={new Date(Date.now() - 86400000).toISOString().split('T')[0]}
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

      {/* Executive Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-gradient-to-br from-blue-500 to-blue-600 rounded-lg p-6 text-white">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-blue-100 text-sm">Total Products</p>
              <p className="text-2xl font-bold">{analytics?.total_products_analyzed || 0}</p>
            </div>
            <Package className="h-8 w-8 text-blue-200" />
          </div>
        </div>
        
        <div className="bg-gradient-to-br from-red-500 to-red-600 rounded-lg p-6 text-white">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-red-100 text-sm">Critical Actions</p>
              <p className="text-2xl font-bold">{analytics?.critical_alerts?.length || 0}</p>
            </div>
            <AlertTriangle className="h-8 w-8 text-red-200" />
          </div>
        </div>
        
        <div className="bg-gradient-to-br from-green-500 to-green-600 rounded-lg p-6 text-white">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-green-100 text-sm">High Priority</p>
              <p className="text-2xl font-bold">{analytics?.high_priority_count || 0}</p>
            </div>
            <Zap className="h-8 w-8 text-green-200" />
          </div>
        </div>
        
        <div className="bg-gradient-to-br from-purple-500 to-purple-600 rounded-lg p-6 text-white">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-purple-100 text-sm">Active Alerts</p>
              <p className="text-2xl font-bold">{analytics?.restock_alerts ? Object.keys(analytics.restock_alerts).length : 0}</p>
            </div>
            <Target className="h-8 w-8 text-purple-200" />
          </div>
        </div>
      </div>

      {/* Stock Risk Dashboard - Scatter Plot */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Stock Risk Analysis</h3>
            <p className="text-sm text-gray-600">Velocity vs Days Remaining (bubble size = revenue impact)</p>
          </div>
          <BarChart3 className="h-5 w-5 text-gray-400" />
        </div>
        <ResponsiveContainer width="100%" height={400}>
          <ScatterChart data={getStockRiskData()}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis 
              dataKey="velocity" 
              name="Daily Velocity" 
              label={{ value: 'Daily Sales Velocity', position: 'insideBottom', offset: -10 }}
            />
            <YAxis 
              dataKey="daysLeft" 
              name="Days Remaining" 
              label={{ value: 'Days of Stock Remaining', angle: -90, position: 'insideLeft' }}
            />
            <Tooltip 
              formatter={(value, name, props) => {
                if (name === 'Daily Velocity') return [value.toFixed(2), 'Velocity'];
                if (name === 'Days Remaining') return [value.toFixed(0), 'Days Left'];
                return [value, name];
              }}
              labelFormatter={(label, payload) => {
                if (payload && payload[0]) {
                  return `${payload[0].payload.fullAsin}: ${payload[0].payload.productName}`;
                }
                return label;
              }}
            />
            <Scatter 
              dataKey="revenueImpact" 
              fill={(entry) => {
                const category = entry?.category;
                if (category?.includes('critical')) return '#dc2626';
                if (category?.includes('warning')) return '#d97706'; 
                if (category?.includes('opportunity')) return '#16a34a';
                return '#6b7280';
              }}
            />
          </ScatterChart>
        </ResponsiveContainer>
      </div>

      {/* Revenue Opportunity vs Priority Distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Revenue Opportunity Analysis */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-lg font-semibold text-gray-900">Revenue Opportunity Matrix</h3>
              <p className="text-sm text-gray-600">ROI vs Velocity performance</p>
            </div>
            <DollarSign className="h-5 w-5 text-gray-400" />
          </div>
          <ResponsiveContainer width="100%" height={300}>
            <ScatterChart data={getRevenueOpportunityData().slice(0, 15)}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis 
                dataKey="velocity" 
                name="Velocity"
                label={{ value: 'Daily Velocity', position: 'insideBottom', offset: -10 }}
              />
              <YAxis 
                dataKey="roi" 
                name="ROI"
                label={{ value: 'ROI %', angle: -90, position: 'insideLeft' }}
              />
              <Tooltip 
                formatter={(value, name, props) => {
                  if (name === 'Velocity') return [value.toFixed(2), 'Daily Velocity'];
                  if (name === 'ROI') return [value.toFixed(1) + '%', 'ROI'];
                  return [value, name];
                }}
                labelFormatter={(label, payload) => {
                  if (payload && payload[0]) {
                    return `${payload[0].payload.fullAsin}`;
                  }
                  return label;
                }}
              />
              <Scatter dataKey="opportunity" fill="#8884d8" />
            </ScatterChart>
          </ResponsiveContainer>
        </div>

        {/* Priority Action Distribution */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-lg font-semibold text-gray-900">Action Priority Distribution</h3>
              <p className="text-sm text-gray-600">Products by urgency category</p>
            </div>
            <PieChartIcon className="h-5 w-5 text-gray-400" />
          </div>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={getPriorityDistribution()}
                cx="50%"
                cy="50%"
                innerRadius={60}
                outerRadius={120}
                paddingAngle={5}
                dataKey="value"
              >
                {getPriorityDistribution().map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Velocity Trend Analysis */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Multi-Period Velocity Analysis</h3>
            <p className="text-sm text-gray-600">Top performers across different time periods</p>
          </div>
          <TrendingUp className="h-5 w-5 text-gray-400" />
        </div>
        <ResponsiveContainer width="100%" height={350}>
          <ComposedChart data={getVelocityTrendData()}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="asin" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Bar dataKey="7d" fill="#ef4444" name="7 Day Avg" />
            <Bar dataKey="14d" fill="#f97316" name="14 Day Avg" />
            <Bar dataKey="30d" fill="#eab308" name="30 Day Avg" />
            <Line type="monotone" dataKey="weighted" stroke="#16a34a" strokeWidth={3} name="Weighted Average" />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Financial Impact Analysis */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Restock Investment Analysis</h3>
            <p className="text-sm text-gray-600">Required investment vs potential returns</p>
          </div>
          <DollarSign className="h-5 w-5 text-gray-400" />
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">ASIN</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Suggested Qty</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Investment</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Potential Return</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">ROI %</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Payback (Days)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {getRestockImpactData().slice(0, 10).map((item) => (
                <tr key={item.fullAsin} className="hover:bg-gray-50">
                  <td className="px-4 py-4 text-sm font-medium text-gray-900">{item.asin}</td>
                  <td className="px-4 py-4 text-sm text-gray-900">{item.suggestedQty}</td>
                  <td className="px-4 py-4 text-sm text-gray-900">${item.investment.toFixed(0)}</td>
                  <td className="px-4 py-4 text-sm text-green-600">${item.potentialReturn.toFixed(0)}</td>
                  <td className="px-4 py-4 text-sm text-blue-600">{item.roi.toFixed(1)}%</td>
                  <td className="px-4 py-4 text-sm text-gray-600">
                    {item.paybackDays < 999 ? Math.round(item.paybackDays) : '∞'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Critical Alerts Table */}
      {analytics?.critical_alerts && analytics.critical_alerts.length > 0 && (
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-lg font-semibold text-gray-900">🚨 Critical Actions Required</h3>
              <p className="text-sm text-gray-600">Immediate attention needed</p>
            </div>
            <AlertCircle className="h-5 w-5 text-red-500" />
          </div>
          <div className="space-y-3">
            {analytics.critical_alerts.slice(0, 8).map((alert, index) => (
              <div key={index} className="flex items-center justify-between p-4 bg-red-50 border border-red-200 rounded-lg">
                <div className="flex items-center space-x-3">
                  <span className="text-2xl">{alert.emoji}</span>
                  <div>
                    <p className="font-medium text-gray-900">{alert.asin}</p>
                    <p className="text-sm text-gray-600">{alert.reasoning}</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-sm font-medium text-gray-900">Velocity: {alert.velocity.toFixed(2)}/day</p>
                  <p className="text-sm text-gray-600">Priority: {alert.priority_score.toFixed(2)}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default Analytics;