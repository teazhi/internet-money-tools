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
  PieChart as PieChartIcon,
  ExternalLink,
  X
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
  const [showModal, setShowModal] = useState(false);
  const [modalData, setModalData] = useState(null);
  const [modalTitle, setModalTitle] = useState('');

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

  // Calculate health scores
  const getHealthScores = () => {
    if (!analytics) return { overall: 0, salesMomentum: 0, inventoryRisk: 0, profitHealth: 0 };
    
    const totalProducts = analytics.enhanced_analytics ? Object.keys(analytics.enhanced_analytics).length : 0;
    const criticalItems = analytics.critical_alerts?.length || 0;
    const highPriorityItems = analytics.high_priority_count || 0;
    const todaySales = analytics.today_sales ? Object.values(analytics.today_sales).reduce((a, b) => a + b, 0) : 0;
    
    // Sales Momentum Score (0-5 stars)
    const salesMomentum = Math.min(5, Math.floor(todaySales / 5)); // 1 star per 5 units sold
    
    // Inventory Risk Score (0-5 stars, inverse of risk)
    const inventoryRisk = Math.max(0, 5 - Math.floor(criticalItems * 2)); // -2 stars per critical item
    
    // Profit Health Score (0-5 stars)
    const profitHealth = Math.max(0, 5 - Math.floor(highPriorityItems / 2)); // -1 star per 2 high priority items
    
    // Overall Score (0-100)
    const overall = Math.round(((salesMomentum + inventoryRisk + profitHealth) / 15) * 100);
    
    return { overall, salesMomentum, inventoryRisk, profitHealth };
  };

  const renderStars = (count) => {
    return Array.from({ length: 5 }, (_, i) => (
      <span key={i} className={i < count ? 'text-yellow-500' : 'text-gray-300'}>⭐</span>
    ));
  };

  const getTodoList = () => {
    const todos = [];
    
    // Critical restock items
    if (analytics?.critical_alerts) {
      analytics.critical_alerts.slice(0, 3).forEach(alert => {
        const stockData = analytics.low_stock?.[alert.asin];
        todos.push({
          type: 'critical',
          asin: alert.asin,
          action: `Reorder ${alert.asin}`,
          detail: `${alert.velocity.toFixed(0)} units/day, ${stockData?.days_left || 'few'} days left`,
          icon: '🚨'
        });
      });
    }
    
    // High velocity monitoring
    if (analytics?.enhanced_analytics) {
      Object.entries(analytics.enhanced_analytics)
        .filter(([_, data]) => data.velocity?.weighted_velocity > 5)
        .slice(0, 2)
        .forEach(([asin, data]) => {
          todos.push({
            type: 'monitor',
            asin: asin,
            action: `Monitor ${asin.substring(0, 8)}`,
            detail: `Trending up +${((data.velocity?.trend_factor - 1) * 100).toFixed(0)}%`,
            icon: '📈'
          });
        });
    }
    
    // Profit optimization opportunities
    if (analytics?.enhanced_analytics) {
      Object.entries(analytics.enhanced_analytics)
        .filter(([_, data]) => data.priority?.category === 'opportunity_high_velocity')
        .slice(0, 2)
        .forEach(([asin, data]) => {
          todos.push({
            type: 'opportunity',
            asin: asin,
            action: `Scale ${asin.substring(0, 8)}`,
            detail: `High velocity + good ROI opportunity`,
            icon: '💰'
          });
        });
    }
    
    return todos.slice(0, 6); // Limit to 6 items
  };

  const getTopMovers = () => {
    if (!analytics?.today_sales) return [];
    
    return Object.entries(analytics.today_sales)
      .sort(([,a], [,b]) => b - a)
      .slice(0, 5)
      .map(([asin, sales]) => ({
        asin: asin.substring(0, 8),
        sales,
        trend: analytics.velocity?.[asin]?.pct || 0
      }));
  };

  const getStockStatus = () => {
    if (!analytics?.enhanced_analytics) return { critical: 0, warning: 0, healthy: 0 };
    
    let critical = 0, warning = 0, healthy = 0;
    
    Object.values(analytics.enhanced_analytics).forEach(data => {
      const category = data.priority?.category || 'monitor';
      if (category.includes('critical')) critical++;
      else if (category.includes('warning')) warning++;
      else healthy++;
    });
    
    return { critical, warning, healthy };
  };

  const openModal = (title, data) => {
    setModalTitle(title);
    setModalData(data);
    setShowModal(true);
  };

  const getProductsByCategory = (category) => {
    if (!analytics?.enhanced_analytics) return [];
    
    const products = Object.entries(analytics.enhanced_analytics)
      .filter(([_, data]) => {
        if (category === 'critical') {
          return data.priority?.category?.includes('critical');
        } else if (category === 'warning') {
          return data.priority?.category?.includes('warning');
        } else if (category === 'healthy') {
          return !data.priority?.category?.includes('critical') && !data.priority?.category?.includes('warning');
        }
        return false;
      })
      .map(([asin, data]) => ({
        asin: asin,
        productName: data.product_name || asin,
        velocity: data.velocity?.weighted_velocity || 0,
        daysLeft: data.stock_info?.['Days left'] || data.stock_info?.['Days of stock left'] || 'Unknown',
        currentStock: data.stock_info?.['FBA/FBM Stock'] || 0,
        category: data.priority?.category || 'unknown',
        reasoning: data.priority?.reasoning || '',
        suggestedQty: data.restock?.suggested_quantity || 0,
        roi: data.stock_info?.['ROI %'] || data.stock_info?.['ROI'] || 0
      }))
      .sort((a, b) => b.velocity - a.velocity);
    
    return products;
  };

  const getCriticalAlerts = () => {
    return analytics?.critical_alerts || [];
  };

  const getGrowthOpportunities = () => {
    if (!analytics?.enhanced_analytics) return [];
    
    return Object.entries(analytics.enhanced_analytics)
      .filter(([_, data]) => data.priority?.category === 'opportunity_high_velocity')
      .map(([asin, data]) => ({
        asin: asin,
        productName: data.product_name || asin,
        velocity: data.velocity?.weighted_velocity || 0,
        roi: data.stock_info?.['ROI %'] || data.stock_info?.['ROI'] || 0,
        opportunity: data.priority?.opportunity || 0,
        reasoning: data.priority?.reasoning || ''
      }))
      .sort((a, b) => b.opportunity - a.opportunity);
  };

  const getMonitorProducts = () => {
    if (!analytics?.enhanced_analytics) return [];
    
    return Object.entries(analytics.enhanced_analytics)
      .filter(([_, data]) => data.priority?.category === 'monitor')
      .map(([asin, data]) => ({
        asin: asin,
        productName: data.product_name || asin,
        velocity: data.velocity?.weighted_velocity || 0,
        daysLeft: data.stock_info?.['Days left'] || data.stock_info?.['Days of stock left'] || 'Unknown',
        trend: data.velocity?.trend_direction || 'stable',
        reasoning: data.priority?.reasoning || ''
      }))
      .sort((a, b) => b.velocity - a.velocity);
  };

  const { overall, salesMomentum, inventoryRisk, profitHealth } = getHealthScores();
  const todoList = getTodoList();
  const topMovers = getTopMovers();
  const stockStatus = getStockStatus();

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Business Health Scorecard</h1>
          <p className="text-gray-600">
            Your Amazon business snapshot for {getReportDate()} {analytics?.is_yesterday && '(Yesterday)'}
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <input
            id="date-select"
            type="date"
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
            max={new Date(Date.now() - 86400000).toISOString().split('T')[0]}
            className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-builders-500"
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

      {/* Health Score Card */}
      <div className="card bg-gradient-to-br from-blue-50 to-indigo-100 border-2 border-blue-200">
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-24 h-24 bg-white rounded-full shadow-lg mb-4">
            <span className="text-3xl font-bold text-blue-600">{overall}</span>
            <span className="text-sm text-gray-500 ml-1">/100</span>
          </div>
          <h2 className="text-2xl font-bold text-gray-900 mb-2">Business Health Score</h2>
          <p className="text-gray-600">
            {overall >= 80 ? 'Excellent! Your business is performing well.' :
             overall >= 60 ? 'Good! Some areas need attention.' :
             overall >= 40 ? 'Fair. Focus on critical issues.' :
             'Needs immediate attention!'}
          </p>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="text-center">
            <div className="flex justify-center items-center mb-2">
              {renderStars(salesMomentum)}
            </div>
            <h3 className="font-semibold text-gray-900">Sales Momentum</h3>
            <p className="text-sm text-gray-600">{topMovers.length} active products</p>
          </div>
          
          <div className="text-center">
            <div className="flex justify-center items-center mb-2">
              {renderStars(inventoryRisk)}
            </div>
            <h3 className="font-semibold text-gray-900">Inventory Health</h3>
            <p className="text-sm text-gray-600">{stockStatus.critical} critical items</p>
          </div>
          
          <div className="text-center">
            <div className="flex justify-center items-center mb-2">
              {renderStars(profitHealth)}
            </div>
            <h3 className="font-semibold text-gray-900">Profit Health</h3>
            <p className="text-sm text-gray-600">Strong margins</p>
          </div>
        </div>
      </div>

      {/* Action Items */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Today's Todo List */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900">📋 Today's Action Items</h3>
            <span className="text-sm text-gray-500">{todoList.length} tasks</span>
          </div>
          <div className="space-y-3 max-h-80 overflow-y-auto">
            {todoList.length > 0 ? todoList.map((todo, index) => (
              <div key={index} className={`flex items-center justify-between p-3 rounded-lg border ${
                todo.type === 'critical' ? 'bg-red-50 border-red-200' :
                todo.type === 'monitor' ? 'bg-yellow-50 border-yellow-200' :
                'bg-green-50 border-green-200'
              }`}>
                <div className="flex items-center space-x-3">
                  <span className="text-xl">{todo.icon}</span>
                  <div>
                    <p className="font-medium text-gray-900">{todo.action}</p>
                    <p className="text-sm text-gray-600">{todo.detail}</p>
                  </div>
                </div>
                <input type="checkbox" className="h-4 w-4 text-blue-600 rounded" />
              </div>
            )) : (
              <div className="text-center py-8 text-gray-500">
                <Package className="h-12 w-12 mx-auto mb-2 text-gray-300" />
                <p>All caught up! No urgent actions needed.</p>
              </div>
            )}
          </div>
        </div>

        {/* Quick Stats */}
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">📊 Quick Stats</h3>
          <div className="space-y-4">
            <div className="flex justify-between items-center py-2 border-b border-gray-100">
              <span className="text-gray-600">Units Sold Yesterday</span>
              <span className="font-semibold text-gray-900">
                {analytics?.yesterday_sales ? Object.values(analytics.yesterday_sales).reduce((a, b) => a + b, 0) : 0}
              </span>
            </div>
            <div className="flex justify-between items-center py-2 border-b border-gray-100">
              <span className="text-gray-600">Active Products</span>
              <span className="font-semibold text-gray-900">
                {analytics?.today_sales ? Object.keys(analytics.today_sales).length : 0}
              </span>
            </div>
            <div className="flex justify-between items-center py-2 border-b border-gray-100">
              <span className="text-gray-600">Critical Stock Alerts</span>
              <button 
                onClick={() => openModal('Critical Stock Alerts', getCriticalAlerts())}
                className="font-semibold text-red-600 hover:text-red-800 hover:underline transition-colors"
              >
                {stockStatus.critical}
              </button>
            </div>
            <div className="flex justify-between items-center py-2 border-b border-gray-100">
              <span className="text-gray-600">Growth Opportunities</span>
              <button 
                onClick={() => openModal('Growth Opportunities', getGrowthOpportunities())}
                className="font-semibold text-green-600 hover:text-green-800 hover:underline transition-colors"
              >
                {getGrowthOpportunities().length}
              </button>
            </div>
            <div className="flex justify-between items-center py-2">
              <span className="text-gray-600">Products to Monitor</span>
              <button 
                onClick={() => openModal('Products to Monitor', getMonitorProducts())}
                className="font-semibold text-yellow-600 hover:text-yellow-800 hover:underline transition-colors"
              >
                {getMonitorProducts().length}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Top Movers Chart */}
      {topMovers.length > 0 && (
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">🚀 Today's Top Movers</h3>
          <div className="mb-4">
            <div className="flex flex-wrap gap-2">
              {topMovers.map((mover, index) => (
                <a 
                  key={index}
                  href={`https://www.amazon.com/dp/${mover.asin}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 px-3 py-1 bg-blue-50 text-blue-700 rounded-full text-sm hover:bg-blue-100 transition-colors"
                >
                  {mover.asin} ({mover.sales} units)
                  <ExternalLink className="h-3 w-3" />
                </a>
              ))}
            </div>
          </div>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={topMovers}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="asin" />
              <YAxis />
              <Tooltip 
                formatter={(value, name) => [value, name === 'sales' ? 'Units Sold' : 'Trend %']}
                labelFormatter={(label) => `ASIN: ${label}`}
              />
              <Bar dataKey="sales" fill="#3b82f6" name="Units Sold" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Stock Status Overview */}
      <div className="card">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">📦 Inventory Status</h3>
        <div className="grid grid-cols-3 gap-4">
          <button 
            onClick={() => openModal('Critical Products', getProductsByCategory('critical'))}
            className="text-center p-4 bg-red-50 rounded-lg hover:bg-red-100 transition-colors"
          >
            <div className="text-2xl font-bold text-red-600">{stockStatus.critical}</div>
            <div className="text-sm text-red-700">Critical</div>
            <div className="text-xs text-gray-500">Need immediate action</div>
          </button>
          <button 
            onClick={() => openModal('Warning Products', getProductsByCategory('warning'))}
            className="text-center p-4 bg-yellow-50 rounded-lg hover:bg-yellow-100 transition-colors"
          >
            <div className="text-2xl font-bold text-yellow-600">{stockStatus.warning}</div>
            <div className="text-sm text-yellow-700">Watch Closely</div>
            <div className="text-xs text-gray-500">Monitor for changes</div>
          </button>
          <button 
            onClick={() => openModal('Healthy Products', getProductsByCategory('healthy'))}
            className="text-center p-4 bg-green-50 rounded-lg hover:bg-green-100 transition-colors"
          >
            <div className="text-2xl font-bold text-green-600">{stockStatus.healthy}</div>
            <div className="text-sm text-green-700">Healthy</div>
            <div className="text-xs text-gray-500">No action needed</div>
          </button>
        </div>
      </div>

      {showModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg max-w-4xl w-full max-h-[80vh] overflow-hidden">
            <div className="flex justify-between items-center p-6 border-b">
              <h2 className="text-xl font-bold text-gray-900">{modalTitle}</h2>
              <button 
                onClick={() => setShowModal(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="h-6 w-6" />
              </button>
            </div>
            
            <div className="p-6 overflow-y-auto max-h-[60vh]">
              {modalData && modalData.length > 0 ? (
                <div className="space-y-4">
                  {modalData.map((item, index) => (
                    <div key={index} className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50">
                      <div className="flex justify-between items-start mb-2">
                        <div className="flex items-center gap-2">
                          <h3 className="font-semibold text-gray-900">
                            {item.asin}
                          </h3>
                          <a 
                            href={`https://www.amazon.com/dp/${item.asin}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-600 hover:text-blue-800"
                          >
                            <ExternalLink className="h-4 w-4" />
                          </a>
                        </div>
                        {item.velocity !== undefined && (
                          <span className="text-sm font-medium text-gray-600">
                            {item.velocity.toFixed(1)} units/day
                          </span>
                        )}
                      </div>
                      
                      <p className="text-sm text-gray-700 mb-2">
                        {item.productName || item.product_name || 'Unknown Product'}
                      </p>
                      
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs text-gray-600">
                        {item.daysLeft !== undefined && (
                          <div>
                            <span className="font-medium">Days Left:</span> {item.daysLeft}
                          </div>
                        )}
                        {item.currentStock !== undefined && (
                          <div>
                            <span className="font-medium">Stock:</span> {item.currentStock}
                          </div>
                        )}
                        {item.roi !== undefined && (
                          <div>
                            <span className="font-medium">ROI:</span> {item.roi}%
                          </div>
                        )}
                        {item.suggestedQty !== undefined && (
                          <div>
                            <span className="font-medium">Suggested:</span> {item.suggestedQty}
                          </div>
                        )}
                      </div>
                      
                      {item.reasoning && (
                        <p className="text-sm text-gray-600 mt-2 italic">
                          {item.reasoning}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-gray-500">
                  <Package className="h-12 w-12 mx-auto mb-2 text-gray-300" />
                  <p>No products found in this category.</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Analytics;