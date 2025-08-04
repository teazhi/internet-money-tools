import React, { useState, useEffect, useMemo, useCallback, memo } from 'react';
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
  RefreshCw,
  ExternalLink,
  ShoppingBag,
  Target,
  TrendingDown
} from 'lucide-react';
import axios from 'axios';

const Overview = () => {
  const { user } = useAuth();
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [error, setError] = useState(null);

  const fetchAnalytics = useCallback(async () => {
    try {
      setError(null);
      const response = await axios.get('/api/analytics/orders', { withCredentials: true });
      setAnalytics(response.data);
      setLastUpdated(new Date());
      
      if (response.data.error) {
        setError(response.data.error);
      }
    } catch (error) {
      console.error('Error fetching analytics:', error);
      
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
  }, []);

  useEffect(() => {
    fetchAnalytics();
    // Auto-refresh every 15 minutes to reduce server load, but don't show loading state
    const interval = setInterval(() => fetchAnalytics(false), 15 * 60 * 1000);
    return () => clearInterval(interval);
  }, [fetchAnalytics]);

  // Remove unused reportDate variable as dateDisplayInfo covers this functionality

  const dateDisplayInfo = useMemo(() => {
    if (!analytics?.report_date) return { text: 'Unknown Date', subtitle: null };
    
    // Parse the date string as local time to avoid timezone issues
    const reportDateStr = analytics.report_date; // YYYY-MM-DD format
    const [year, month, day] = reportDateStr.split('-').map(Number);
    const reportDateObj = new Date(year, month - 1, day); // month is 0-based in JS
    
    const today = new Date();
    today.setHours(0, 0, 0, 0); // Reset time to start of day
    
    const yesterday = new Date();
    yesterday.setDate(today.getDate() - 1);
    yesterday.setHours(0, 0, 0, 0); // Reset time to start of day
    
    // Reset report date time for accurate comparison
    const reportDateForComparison = new Date(reportDateObj);
    reportDateForComparison.setHours(0, 0, 0, 0);
    
    // Check if report date is yesterday or today
    const isYesterday = reportDateForComparison.getTime() === yesterday.getTime();
    const isToday = reportDateForComparison.getTime() === today.getTime();
    
    const formatted = reportDateObj.toLocaleDateString('en-US', { 
      weekday: 'long', 
      year: 'numeric', 
      month: 'long', 
      day: 'numeric' 
    });
    
    if (isYesterday) {
      // Use user's timezone if available
      const userTimezone = analytics?.user_timezone || Intl.DateTimeFormat().resolvedOptions().timeZone;
      
      const now = new Date();
      const switchTime = new Date();
      switchTime.setHours(23, 59, 0, 0);
      
      // If user has a different timezone, adjust the calculation
      if (userTimezone && userTimezone !== Intl.DateTimeFormat().resolvedOptions().timeZone) {
        try {
          const nowInUserTz = new Date(now.toLocaleString("en-US", {timeZone: userTimezone}));
          const switchTimeInUserTz = new Date();
          switchTimeInUserTz.setHours(23, 59, 0, 0);
          const timeUntilSwitch = switchTimeInUserTz - nowInUserTz;
          
          if (timeUntilSwitch > 0) {
            const hours = Math.floor(timeUntilSwitch / (1000 * 60 * 60));
            const minutes = Math.floor((timeUntilSwitch % (1000 * 60 * 60)) / (1000 * 60));
            return {
              text: `${formatted} (Yesterday's Complete Data)`,
              subtitle: `Will switch to today's data in ${hours}h ${minutes}m (${userTimezone})`
            };
          }
        } catch (e) {
          // Silently handle timezone errors
        }
      }
      
      // Fallback to local time calculation
      const timeUntilSwitch = switchTime - now;
      if (timeUntilSwitch > 0) {
        const hours = Math.floor(timeUntilSwitch / (1000 * 60 * 60));
        const minutes = Math.floor((timeUntilSwitch % (1000 * 60 * 60)) / (1000 * 60));
        return {
          text: `${formatted} (Yesterday's Complete Data)`,
          subtitle: `Will switch to today's data in ${hours}h ${minutes}m`
        };
      }
    }
    
    if (isToday) {
      return {
        text: `${formatted} (Today's Data)`,
        subtitle: 'Live data for today'
      };
    }
    
    return { text: formatted, subtitle: null };
  }, [analytics?.report_date, analytics?.user_timezone]);

  const setupProgress = useMemo(() => {
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
  }, [user?.profile_configured, user?.google_linked, user?.sheet_configured, user?.user_record?.run_scripts]);

  const formatTrendIcon = useCallback((pct) => {
    if (pct > 0) return <ArrowUp className="h-4 w-4 text-green-500" />;
    if (pct < 0) return <ArrowDown className="h-4 w-4 text-red-500" />;
    return <Minus className="h-4 w-4 text-gray-400" />;
  }, []);

  const formatTrendColor = useCallback((pct) => {
    if (pct > 0) return 'text-green-600';
    if (pct < 0) return 'text-red-600';
    return 'text-gray-500';
  }, []);

  // Memoized analytics calculations with improved logic and performance
  const analyticsStats = useMemo(() => {
    if (!analytics) return { todayOrders: 0, activeProducts: 0, lowStockCount: 0, restockPriorityCount: 0, yesterdayRevenue: 0 };
    
    const todayOrders = analytics.today_sales ? Object.values(analytics.today_sales).reduce((a, b) => a + b, 0) : 0;
    const activeProducts = analytics.today_sales ? Object.keys(analytics.today_sales).length : 0;
    
    // Calculate yesterday's revenue - optimized with early return
    let yesterdayRevenue = 0;
    if (analytics.sellerboard_orders?.length > 0) {
      yesterdayRevenue = analytics.sellerboard_orders.reduce((total, order) => {
        const amount = parseFloat(
          order.OrderTotalAmount || 
          order.order_total_amount || 
          order['Order Total Amount'] ||
          order.Revenue ||
          order.revenue ||
          order.Total ||
          order.total ||
          order.Amount ||
          order.amount ||
          0
        );
        return total + amount;
      }, 0);
    }
    
    // Optimized stock calculations with early returns
    let lowStockCount = 0;
    let restockPriorityCount = 0;
    
    if (analytics.enhanced_analytics) {
      const enhancedData = Object.values(analytics.enhanced_analytics);
      for (const data of enhancedData) {
        if (!data.velocity || !data.restock) continue;
        
        const velocity = data.velocity.weighted_velocity || 0;
        if (velocity <= 0) continue;
        
        const currentStock = data.restock.current_stock || 0;
        const daysLeft = currentStock / velocity;
        
        // Low stock: less than 14 days of inventory
        if (daysLeft < 14) {
          lowStockCount++;
        }
        
        // Restock priority: critical/warning categories or less than 30 days of inventory
        if (data.priority?.category?.includes('critical') || 
            data.priority?.category?.includes('warning') || 
            daysLeft < 30) {
          restockPriorityCount++;
        }
      }
    } else {
      // Fallback to old logic if enhanced analytics not available
      lowStockCount = analytics.low_stock ? Object.keys(analytics.low_stock).length : 0;
      restockPriorityCount = analytics.restock_priority ? Object.keys(analytics.restock_priority).length : 0;
    }
    
    return { todayOrders, activeProducts, lowStockCount, restockPriorityCount, yesterdayRevenue };
  }, [analytics?.today_sales, analytics?.sellerboard_orders, analytics?.enhanced_analytics, analytics?.low_stock, analytics?.restock_priority]);

  const topProducts = useMemo(() => {
    if (!analytics?.today_sales) return [];
    
    return Object.entries(analytics.today_sales)
      .sort(([,a], [,b]) => b - a)
      .slice(0, 5);
  }, [analytics?.today_sales]);

  const TopProductItem = memo(({ asin, count, index }) => {
    // Get purchase insights for this ASIN if available
    const purchaseInsights = analytics?.purchase_insights || {};
    const asinPurchaseData = {
      urgency: purchaseInsights.restock_urgency_scoring?.[asin],
      roi: purchaseInsights.roi_based_recommendations?.[asin],
      velocity: purchaseInsights.purchase_velocity_analysis?.[asin]
    };

    const getTrendIcon = (trend) => {
      if (!trend) return '';
      if (trend > 0.1) return '↗️';
      if (trend < -0.1) return '↘️';
      return '→';
    };

    return (
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <span className="flex-shrink-0 w-6 h-6 bg-builders-100 text-builders-600 rounded-full flex items-center justify-center text-sm font-medium">
            {index + 1}
          </span>
          <div className="flex-1">
            <div className="flex items-center space-x-2">
              <span className="text-sm font-medium text-gray-900">{asin}</span>
              {asinPurchaseData.velocity && (
                <span className="text-sm">{getTrendIcon(asinPurchaseData.velocity.purchase_trend)}</span>
              )}
              <a
                href={`https://amazon.com/dp/${asin}`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center text-blue-600 hover:text-blue-800 transition-colors"
                title="View on Amazon"
              >
                <ExternalLink className="h-4 w-4" />
              </a>
            </div>
            {asinPurchaseData.roi && (
              <div className="text-xs text-gray-500 mt-1">
                ROI: {asinPurchaseData.roi.roi_percentage}% • Profit: ${asinPurchaseData.roi.profit_per_unit}/unit
              </div>
            )}
          </div>
        </div>
        <div className="text-right">
          <span className="text-sm text-gray-600">{count} units sold</span>
          {asinPurchaseData.urgency && asinPurchaseData.urgency.urgency_level !== 'LOW' && (
            <div className="text-xs text-orange-600 mt-1">
              Restock {asinPurchaseData.urgency.urgency_level.toLowerCase()}
            </div>
          )}
        </div>
      </div>
    );
  });

  // Purchase Analytics data processing
  const purchaseInsights = useMemo(() => {
    if (!analytics?.purchase_insights) return null;
    
    const insights = analytics.purchase_insights;
    const summary = insights.summary_metrics || {};
    
    // Get top ROI recommendations
    const roiRecs = insights.roi_based_recommendations || {};
    const topROI = Object.entries(roiRecs)
      .filter(([_, data]) => data.roi_percentage > 0)
      .sort(([_, a], [__, b]) => b.roi_percentage - a.roi_percentage)
      .slice(0, 3);
    
    // Get urgent restock items
    const urgentItems = Object.entries(insights.restock_urgency_scoring || {})
      .filter(([_, data]) => data.urgency_level === 'CRITICAL' || data.urgency_level === 'HIGH')
      .sort(([_, a], [__, b]) => b.urgency_score - a.urgency_score)
      .slice(0, 3);
    
    // Calculate current month date range for display
    let dateRange = '';
    const today = new Date();
    const firstDayOfMonth = new Date(today.getFullYear(), today.getMonth(), 1);
    const currentDay = today.getDate();
    
    const formatOptions = { month: 'short', day: 'numeric' };
    
    if (currentDay === 1) {
      // If it's the 1st of the month, just show the single date
      dateRange = firstDayOfMonth.toLocaleDateString('en-US', { ...formatOptions, year: 'numeric' });
    } else {
      // Show range from 1st to current day
      dateRange = `${firstDayOfMonth.toLocaleDateString('en-US', formatOptions)} - ${today.toLocaleDateString('en-US', { ...formatOptions, year: 'numeric' })}`;
    }
    
    return {
      summary,
      topROI,
      urgentItems,
      cashFlowRecs: insights.cash_flow_optimization?.cash_flow_recommendations || [],
      dateRange
    };
  }, [analytics?.purchase_insights]);

  const PurchaseInsightItem = memo(({ asin, data, type }) => {
    const getIcon = () => {
      if (type === 'roi') return <DollarSign className="h-4 w-4 text-green-600" />;
      if (type === 'urgent') return <AlertTriangle className="h-4 w-4 text-red-600" />;
      return <Target className="h-4 w-4 text-blue-600" />;
    };
    
    const getMetric = () => {
      if (type === 'roi') return `${data.roi_percentage}% ROI`;
      if (type === 'urgent') return `${data.urgency_score}/100 urgency`;
      return '';
    };
    
    return (
      <div className="flex items-center justify-between p-2 bg-gray-50 rounded-lg">
        <div className="flex items-center space-x-3">
          {getIcon()}
          <div>
            <span className="text-sm font-medium text-gray-900">{asin}</span>
            <p className="text-xs text-gray-500">
              {type === 'roi' ? data.reason : type === 'urgent' ? `${data.days_since_last_purchase} days since purchase` : ''}
            </p>
          </div>
        </div>
        <span className="text-sm font-semibold text-gray-700">{getMetric()}</span>
      </div>
    );
  });

  const stockAlertsData = useMemo(() => {
    if (analytics?.enhanced_analytics) {
      const lowStockProducts = [];
      
      // Pre-filter and calculate days left in one pass
      for (const [asin, data] of Object.entries(analytics.enhanced_analytics)) {
        if (!data.velocity || !data.restock) continue;
        
        const velocity = data.velocity.weighted_velocity || 0;
        if (velocity <= 0) continue;
        
        const currentStock = data.restock.current_stock || 0;
        const daysLeft = currentStock / velocity;
        
        if (daysLeft < 14) {
          lowStockProducts.push({
            asin,
            productName: data.product_name,
            daysLeft,
            currentStock,
            suggestedQty: data.restock.suggested_quantity || 0
          });
        }
      }
      
      // Sort by days left and take top 5
      return lowStockProducts
        .sort((a, b) => a.daysLeft - b.daysLeft)
        .slice(0, 5);
    } else if (analytics?.low_stock) {
      return Object.entries(analytics.low_stock)
        .slice(0, 5)
        .map(([asin, info]) => ({
          asin,
          productName: info.title,
          daysLeft: parseInt(info.days_left) || 0,
          currentStock: 0,
          suggestedQty: info.reorder_qty || 0,
          isLegacy: true
        }));
    }
    return [];
  }, [analytics?.enhanced_analytics, analytics?.low_stock]);

  const StockAlertItem = memo(({ item }) => {
    // Get purchase insights for this ASIN if available
    const purchaseInsights = analytics?.purchase_insights || {};
    const asinPurchaseData = {
      urgency: purchaseInsights.restock_urgency_scoring?.[item.asin],
      roi: purchaseInsights.roi_based_recommendations?.[item.asin],
      velocity: purchaseInsights.purchase_velocity_analysis?.[item.asin]
    };

    const getUrgencyIcon = (urgencyLevel) => {
      switch (urgencyLevel) {
        case 'CRITICAL': return '🔥';
        case 'HIGH': return '⚠️';
        case 'MEDIUM': return '⏰';
        default: return '';
      }
    };

    const getTrendIcon = (trend) => {
      if (!trend) return '';
      if (trend > 0.1) return '↗️';
      if (trend < -0.1) return '↘️';
      return '→';
    };

    return (
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <div className="flex items-center space-x-2">
            <p className="text-sm font-medium text-gray-900">{item.asin}</p>
            {asinPurchaseData.urgency && (
              <span className="text-sm">{getUrgencyIcon(asinPurchaseData.urgency.urgency_level)}</span>
            )}
            {asinPurchaseData.velocity && (
              <span className="text-sm">{getTrendIcon(asinPurchaseData.velocity.purchase_trend)}</span>
            )}
          </div>
          <p className="text-xs text-gray-500 truncate max-w-xs">
            {item.productName?.length > 40 
              ? item.productName.substring(0, 40) + '...'
              : item.productName
            }
          </p>
          {asinPurchaseData.roi && (
            <p className="text-xs text-green-600">
              ROI: {asinPurchaseData.roi.roi_percentage}% • Profit: ${asinPurchaseData.roi.profit_per_unit}
            </p>
          )}
        </div>
        <div className="text-right ml-4">
          <p className="text-sm text-red-600 font-medium">
            {item.isLegacy ? `${item.daysLeft} days left` : 
             item.daysLeft < 1 ? '< 1 day' : `${Math.round(item.daysLeft)} days left`}
          </p>
          <p className="text-xs text-gray-500">
            {item.isLegacy ? `Reorder: ${item.suggestedQty}` :
             `Stock: ${Math.round(item.currentStock)} • Reorder: ${item.suggestedQty}`}
          </p>
          {asinPurchaseData.velocity && (
            <p className="text-xs text-blue-600">
              Last purchased: {asinPurchaseData.velocity.days_since_last_purchase}d ago
            </p>
          )}
        </div>
      </div>
    );
  });

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

  // Skeleton loading component
  const SkeletonCard = () => (
    <div className="card animate-pulse">
      <div className="flex items-center">
        <div className="flex-shrink-0">
          <div className="h-8 w-8 bg-gray-300 rounded"></div>
        </div>
        <div className="ml-4 flex-1">
          <div className="h-4 bg-gray-300 rounded w-24 mb-2"></div>
          <div className="h-8 bg-gray-300 rounded w-16"></div>
        </div>
      </div>
    </div>
  );

  if (loading && !analytics) {
    return (
      <div className="space-y-6">
        {/* Welcome Header Skeleton */}
        <div className="bg-gradient-to-r from-builders-500 to-builders-600 rounded-lg shadow-sm p-6 text-white">
          <div className="flex justify-between items-start">
            <div>
              <div className="h-8 bg-white/20 rounded w-64 mb-2"></div>
              <div className="h-4 bg-white/20 rounded w-96 mb-2"></div>
              <div className="h-3 bg-white/20 rounded w-48"></div>
            </div>
            <div className="h-10 w-10 bg-white/20 rounded-lg"></div>
          </div>
        </div>

        {/* Stats Grid Skeleton */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>

        {/* Content Skeleton */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="card animate-pulse">
            <div className="h-6 bg-gray-300 rounded w-40 mb-4"></div>
            <div className="space-y-3">
              {[1, 2, 3, 4, 5].map(i => (
                <div key={i} className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <div className="h-6 w-6 bg-gray-300 rounded-full"></div>
                    <div className="h-4 bg-gray-300 rounded w-20"></div>
                  </div>
                  <div className="h-4 bg-gray-300 rounded w-16"></div>
                </div>
              ))}
            </div>
          </div>
          <div className="card animate-pulse">
            <div className="h-6 bg-gray-300 rounded w-32 mb-4"></div>
            <div className="space-y-3">
              {[1, 2, 3, 4, 5].map(i => (
                <div key={i} className="flex items-center justify-between">
                  <div className="flex-1">
                    <div className="h-4 bg-gray-300 rounded w-24 mb-1"></div>
                    <div className="h-3 bg-gray-300 rounded w-32"></div>
                  </div>
                  <div className="text-right">
                    <div className="h-4 bg-gray-300 rounded w-16 mb-1"></div>
                    <div className="h-3 bg-gray-300 rounded w-12"></div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Loading indicator */}
        <div className="text-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-builders-500 mx-auto mb-2"></div>
          <p className="text-gray-600 text-sm">Loading your business analytics...</p>
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
                <p className="mt-1">This usually happens when the server is processing large amounts of data.</p>
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
      {/* Welcome Header */}
      <div className="bg-gradient-to-r from-builders-500 to-builders-600 rounded-lg shadow-sm p-6 text-white">
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-2xl font-bold mb-2">
              Welcome back, {user?.discord_username}!
            </h1>
            <p className="text-builders-100">
              Here's your business overview for {dateDisplayInfo.text}
            </p>
            {dateDisplayInfo.subtitle && (
              <p className="text-builders-200 text-sm mt-1">
                📅 {dateDisplayInfo.subtitle}
              </p>
            )}
            {lastUpdated && (
              <p className="text-builders-200 text-sm mt-1">
                Last updated: {lastUpdated.toLocaleTimeString()}
              </p>
            )}
          </div>
          <button
            onClick={() => fetchAnalytics(true)}
            disabled={loading}
            className="bg-white/20 hover:bg-white/30 p-2 rounded-lg transition-colors duration-200 disabled:opacity-50"
            title={loading ? "Loading..." : "Refresh Data"}
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
        {loading && analytics && (
          <div className="mt-3 p-3 bg-white/20 border border-white/30 rounded-md">
            <div className="flex items-center">
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
              <p className="text-white text-sm">Refreshing analytics data...</p>
            </div>
          </div>
        )}
      </div>

      {/* Setup Progress Card (only show if not fully configured) */}
      {setupProgress.progress < 100 && (
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">Setup Progress</h2>
            <span className="text-sm text-gray-500">{setupProgress.progress}% Complete</span>
          </div>
          <div className="mb-4">
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div 
                className="bg-builders-500 h-2 rounded-full transition-all duration-300"
                style={{ width: `${setupProgress.progress}%` }}
              ></div>
            </div>
          </div>
          <div className="space-y-2">
            {setupProgress.steps.map((step, index) => (
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

      {/* Quick Stats - Operational Metrics */}
      <div className="space-y-6">
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
                  {analyticsStats.todayOrders || '—'}
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
                <p className="text-sm font-medium text-gray-500">ASIN's Sold</p>
                <p className="text-2xl font-semibold text-gray-900">
                  {analyticsStats.activeProducts || '—'}
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
                  {analyticsStats.lowStockCount || '—'}
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
                  {analyticsStats.restockPriorityCount || '—'}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Financial Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="card">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <DollarSign className="h-8 w-8 text-green-500" />
              </div>
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-500">
                  {analytics?.is_yesterday ? "Yesterday's Revenue" : "Today's Revenue"}
                </p>
                <p className="text-2xl font-semibold text-gray-900">
                  {analyticsStats.yesterdayRevenue ? 
                    `$${analyticsStats.yesterdayRevenue.toFixed(2)}` : '—'}
                </p>
              </div>
            </div>
          </div>

          {/* Purchase Insights Card - Enhanced */}
          {purchaseInsights && (
            <div className="card">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <ShoppingBag className="h-8 w-8 text-indigo-500" />
                </div>
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-500">
                    Purchase Investment ({purchaseInsights.dateRange})
                  </p>
                  <p className="text-2xl font-semibold text-gray-900">
                    ${(purchaseInsights.summary.total_investment || 0).toLocaleString()}
                  </p>
                  <p className="text-xs text-gray-500">
                    {(purchaseInsights.summary.total_asins_tracked || 0)} ASINs • {(purchaseInsights.summary.total_units_purchased || 0)} units
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Yesterday's Top Sellers */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Yesterday's Top Products</h3>
          <div className="space-y-3">
            {topProducts.length > 0 ? 
              topProducts.map(([asin, count], index) => (
                <TopProductItem key={asin} asin={asin} count={count} index={index} />
              )) : (
              <div className="text-center py-8">
                <Package className="h-12 w-12 text-gray-300 mx-auto mb-4" />
                <p className="text-gray-500 text-sm">
                  {error ? 'Error loading sales data' : 'No sales data available for this date'}
                </p>
                {analytics?.report_date && (
                  <div className="text-gray-400 text-xs mt-1">
                    <p>Showing data for {dateDisplayInfo.text}</p>
                    {dateDisplayInfo.subtitle && (
                      <p className="mt-1">📅 {dateDisplayInfo.subtitle}</p>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Stock Alerts</h3>
          <div className="space-y-3">
            {stockAlertsData.map((item) => (
              <StockAlertItem key={item.asin} item={item} />
            ))}
            {stockAlertsData.length === 0 && (
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

      {/* Purchase Insights - Integrated into existing sections above */}

    </div>
  );
};

export default memo(Overview);