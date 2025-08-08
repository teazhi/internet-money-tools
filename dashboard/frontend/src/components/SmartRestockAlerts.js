import React, { useMemo, useState } from 'react';
import axios from 'axios';
import { 
  AlertTriangle, 
  TrendingUp, 
  TrendingDown, 
  Minus,
  Package,
  Clock,
  BarChart3,
  Zap,
  Target,
  ShoppingCart,
  ExternalLink,
  DollarSign,
  X,
  Globe,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Filter,
  Search,
  GripVertical,
  RotateCcw
} from 'lucide-react';

const SmartRestockAlerts = React.memo(({ analytics }) => {
  // State for tabs
  const [activeTab, setActiveTab] = useState('recommendations');
  
  // State for restock sources modal
  const [showSourcesModal, setShowSourcesModal] = useState(false);
  const [modalAsin, setModalAsin] = useState('');
  const [purchaseSources, setPurchaseSources] = useState([]);
  const [sourcesLoading, setSourcesLoading] = useState(false);
  
  // State for filtering and sorting
  const [searchQuery, setSearchQuery] = useState('');
  const [priorityFilter, setPriorityFilter] = useState('all');
  const [sortConfig, setSortConfig] = useState({ key: null, direction: 'asc' });
  
  // State for column ordering
  const [draggedColumn, setDraggedColumn] = useState(null);
  const [columnOrders, setColumnOrders] = useState({
    recommendations: JSON.parse(localStorage.getItem('smart-restock-column-order-recommendations') || 'null') || [
      'product', 'priority', 'reasoning', 'current_stock', 'days_left', 'velocity', 'trend', 'last_cogs', 'already_ordered', 'suggested_order', 'actions'
    ],
    analytics: JSON.parse(localStorage.getItem('smart-restock-column-order-analytics') || 'null') || [
      'product', 'current_stock', 'velocity', 'trend', 'days_left', 'last_cogs', 'last_2_months', 'suggested_order', 'priority'
    ],
    detailed: JSON.parse(localStorage.getItem('smart-restock-column-order-detailed') || 'null') || [
      'product', 'velocity_analysis', 'stock_status', 'restock_recommendation', 'priority'
    ]
  });
  
  // Extract data first (before any conditional returns to avoid hook order issues)
  const { enhanced_analytics, restock_alerts, critical_alerts, high_priority_count } = analytics || {};

  // Sorting function
  const handleSort = (key) => {
    let direction = 'asc';
    if (sortConfig.key === key && sortConfig.direction === 'asc') {
      direction = 'desc';
    }
    setSortConfig({ key, direction });
  };

  // Get sort icon
  const getSortIcon = (columnKey) => {
    if (sortConfig.key !== columnKey) {
      return <ArrowUpDown className="h-3 w-3 text-gray-400" />;
    }
    return sortConfig.direction === 'asc' 
      ? <ArrowUp className="h-3 w-3 text-gray-600" />
      : <ArrowDown className="h-3 w-3 text-gray-600" />;
  };

  // Column definitions
  const columnDefinitions = {
    recommendations: {
      product: { key: 'product', label: 'Product', sortKey: 'product_name', draggable: true },
      priority: { key: 'priority', label: 'Priority', sortKey: 'priority_score', draggable: true },
      reasoning: { key: 'reasoning', label: 'Reasoning', sortKey: null, draggable: true },
      current_stock: { key: 'current_stock', label: 'Current Stock', sortKey: 'current_stock', draggable: true },
      days_left: { key: 'days_left', label: 'Days Left', sortKey: 'days_left', draggable: true },
      velocity: { key: 'velocity', label: 'Velocity', sortKey: 'velocity', draggable: true },
      trend: { key: 'trend', label: 'Trend', sortKey: null, draggable: true },
      last_cogs: { key: 'last_cogs', label: 'Last COGS', sortKey: 'cogs', draggable: true },
      already_ordered: { key: 'already_ordered', label: 'Already Ordered', sortKey: null, draggable: true },
      suggested_order: { key: 'suggested_order', label: 'Suggested Order', sortKey: 'suggested_quantity', draggable: true },
      actions: { key: 'actions', label: 'Actions', sortKey: null, draggable: false }
    },
    analytics: {
      product: { key: 'product', label: 'Product', sortKey: 'product_name', draggable: true },
      current_stock: { key: 'current_stock', label: 'Current Stock', sortKey: 'current_stock', draggable: true },
      velocity: { key: 'velocity', label: 'Velocity', sortKey: 'velocity', draggable: true },
      trend: { key: 'trend', label: 'Trend', sortKey: null, draggable: true },
      days_left: { key: 'days_left', label: 'Days Left', sortKey: 'days_left', draggable: true },
      last_cogs: { key: 'last_cogs', label: 'Last COGS', sortKey: 'cogs', draggable: true },
      last_2_months: { key: 'last_2_months', label: 'Last 2 Months', sortKey: null, draggable: true },
      suggested_order: { key: 'suggested_order', label: 'Suggested Order', sortKey: 'suggested_quantity', draggable: true },
      priority: { key: 'priority', label: 'Priority', sortKey: 'priority_score', draggable: true }
    },
    detailed: {
      product: { key: 'product', label: 'Product', sortKey: 'product_name', draggable: true },
      velocity_analysis: { key: 'velocity_analysis', label: 'Velocity Analysis', sortKey: 'velocity', draggable: true },
      stock_status: { key: 'stock_status', label: 'Stock Status', sortKey: 'current_stock', draggable: true },
      restock_recommendation: { key: 'restock_recommendation', label: 'Restock Recommendation', sortKey: 'suggested_quantity', draggable: true },
      priority: { key: 'priority', label: 'Priority', sortKey: 'priority_score', draggable: true }
    }
  };

  // Drag and drop handlers
  const handleDragStart = (e, columnKey, tableType) => {
    setDraggedColumn({ key: columnKey, tableType });
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  };

  const handleDrop = (e, targetColumnKey, tableType) => {
    e.preventDefault();
    
    if (!draggedColumn || draggedColumn.tableType !== tableType) {
      setDraggedColumn(null);
      return;
    }

    const newOrder = [...columnOrders[tableType]];
    const draggedIndex = newOrder.indexOf(draggedColumn.key);
    const targetIndex = newOrder.indexOf(targetColumnKey);

    if (draggedIndex !== -1 && targetIndex !== -1 && draggedIndex !== targetIndex) {
      // Remove dragged item
      const [draggedItem] = newOrder.splice(draggedIndex, 1);
      // Insert at new position
      newOrder.splice(targetIndex, 0, draggedItem);

      // Update state
      setColumnOrders(prev => ({
        ...prev,
        [tableType]: newOrder
      }));

      // Save to localStorage
      localStorage.setItem(`smart-restock-column-order-${tableType}`, JSON.stringify(newOrder));
    }
    
    setDraggedColumn(null);
  };

  const handleDragEnd = () => {
    setDraggedColumn(null);
  };

  // Reset column order to default
  const resetColumnOrder = (tableType) => {
    const defaultOrders = {
      recommendations: ['product', 'priority', 'reasoning', 'current_stock', 'days_left', 'velocity', 'trend', 'last_cogs', 'already_ordered', 'suggested_order', 'actions'],
      analytics: ['product', 'current_stock', 'velocity', 'trend', 'days_left', 'last_cogs', 'last_2_months', 'suggested_order', 'priority'],
      detailed: ['product', 'velocity_analysis', 'stock_status', 'restock_recommendation', 'priority']
    };
    
    setColumnOrders(prev => ({
      ...prev,
      [tableType]: defaultOrders[tableType]
    }));
    
    localStorage.setItem(`smart-restock-column-order-${tableType}`, JSON.stringify(defaultOrders[tableType]));
  };

  // Render cell content for recommendations table
  const renderRecommendationCell = (columnKey, alert) => {
    switch (columnKey) {
      case 'product':
        return (
          <td key={columnKey} className="px-3 py-2">
            <div>
              <div className="text-xs font-medium text-gray-900">
                {alert.product_name.length > 50 
                  ? alert.product_name.substring(0, 50) + '...'
                  : alert.product_name
                }
              </div>
              <div className="text-xs text-gray-500">
                {alert.asin}
                {(enhanced_analytics?.[alert.asin]?.stock_info?.Source || 
                  enhanced_analytics?.[alert.asin]?.stock_info?.source ||
                  enhanced_analytics?.[alert.asin]?.stock_info?.['Source Link'] ||
                  enhanced_analytics?.[alert.asin]?.stock_info?.['source link'] ||
                  enhanced_analytics?.[alert.asin]?.stock_info?.Link ||
                  enhanced_analytics?.[alert.asin]?.stock_info?.link ||
                  enhanced_analytics?.[alert.asin]?.stock_info?.URL ||
                  enhanced_analytics?.[alert.asin]?.stock_info?.url) && (
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
                      className="text-blue-600 hover:text-blue-800"
                      title="View source"
                    >
                      <ExternalLink className="inline h-2 w-2" />
                    </a>
                  </>
                )}
              </div>
            </div>
          </td>
        );
      case 'priority':
        return (
          <td key={columnKey} className="px-3 py-2 whitespace-nowrap">
            <span className={`inline-flex items-center px-1.5 py-0.5 rounded-full text-xs font-medium ${
              alert.category.includes('critical') 
                ? 'bg-red-100 text-red-800'
                : alert.category.includes('warning')
                ? 'bg-builders-100 text-builders-800'
                : alert.category.includes('opportunity')
                ? 'bg-green-100 text-green-800'
                : 'bg-gray-100 text-gray-800'
            }`}>
              {alert.emoji} {getCategoryLabel(alert.category)}
            </span>
            <div className="text-xs text-gray-500 mt-0.5">
              {alert.priority_score.toFixed(2)}
            </div>
          </td>
        );
      case 'reasoning':
        return (
          <td key={columnKey} className="px-3 py-2">
            <div className="text-xs text-gray-700 min-w-[250px] max-w-sm">
              {alert.reasoning}
            </div>
          </td>
        );
      case 'current_stock':
        return (
          <td key={columnKey} className="px-3 py-2 whitespace-nowrap text-xs text-gray-900">
            {Math.round(alert.current_stock)}
          </td>
        );
      case 'days_left':
        return (
          <td key={columnKey} className="px-3 py-2 whitespace-nowrap text-xs text-gray-900">
            {formatDaysLeft(alert.days_left)}
          </td>
        );
      case 'velocity':
        return (
          <td key={columnKey} className="px-3 py-2 whitespace-nowrap text-xs text-gray-900">
            {alert.velocity.toFixed(1)}/day
          </td>
        );
      case 'trend':
        return (
          <td key={columnKey} className="px-3 py-2 whitespace-nowrap">
            <div className="flex items-center space-x-1">
              {getTrendIcon(alert.trend)}
              <span className="text-xs text-gray-900 capitalize">
                {alert.trend}
              </span>
            </div>
          </td>
        );
      case 'last_cogs':
        return (
          <td key={columnKey} className="px-3 py-2 whitespace-nowrap text-xs">
            {enhanced_analytics?.[alert.asin]?.cogs_data?.cogs ? (
              <div>
                <div className="text-green-700 font-medium text-xs">
                  {formatCurrency(enhanced_analytics[alert.asin].cogs_data.cogs)}
                </div>
                {enhanced_analytics[alert.asin].cogs_data.last_purchase_date && (
                  <div className="text-xs text-gray-500">
                    {formatDate(enhanced_analytics[alert.asin].cogs_data.last_purchase_date)}
                  </div>
                )}
              </div>
            ) : (
              <span className="text-gray-400 text-xs">N/A</span>
            )}
          </td>
        );
      case 'already_ordered':
        return (
          <td key={columnKey} className="px-3 py-2 whitespace-nowrap text-xs">
            {enhanced_analytics?.[alert.asin]?.restock?.monthly_purchase_adjustment > 0 ? (
              <div className="flex items-center space-x-1">
                <ShoppingCart className="h-3 w-3 text-purple-600" />
                <span className="text-purple-700 font-medium text-xs">
                  {enhanced_analytics[alert.asin].restock.monthly_purchase_adjustment}
                </span>
              </div>
            ) : (
              <span className="text-gray-400 text-xs">-</span>
            )}
          </td>
        );
      case 'suggested_order':
        return (
          <td key={columnKey} className="px-3 py-2 whitespace-nowrap">
            <div className="text-lg font-bold text-builders-600">
              {alert.suggested_quantity}
            </div>
            <div className="text-xs text-gray-500">
              units
            </div>
          </td>
        );
      case 'actions':
        return (
          <td key={columnKey} className="px-3 py-2 whitespace-nowrap">
            {enhanced_analytics?.[alert.asin]?.cogs_data?.cogs && (
              <button
                onClick={() => handleRestockClick(alert.asin, enhanced_analytics[alert.asin].cogs_data.source_link)}
                className="inline-flex items-center px-2 py-1 bg-blue-600 text-white text-xs rounded-md hover:bg-blue-700 transition-colors disabled:opacity-50"
                disabled={sourcesLoading}
                title="Open restock source"
              >
                <ShoppingCart className="h-3 w-3 mr-1" />
                Restock
              </button>
            )}
          </td>
        );
      default:
        return <td key={columnKey}></td>;
    }
  };

  // Filter and sort alerts
  const sortedAlerts = useMemo(() => {
    if (!restock_alerts) return [];
    
    let filtered = Object.values(restock_alerts);
    
    // Filter out items with 0 suggested quantity
    filtered = filtered.filter(alert => alert.suggested_quantity > 0);
    
    // Apply search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(alert => 
        alert.product_name.toLowerCase().includes(query) ||
        alert.asin.toLowerCase().includes(query) ||
        alert.reasoning.toLowerCase().includes(query)
      );
    }
    
    // Apply priority filter
    if (priorityFilter !== 'all') {
      filtered = filtered.filter(alert => {
        if (priorityFilter === 'critical') return alert.category.includes('critical');
        if (priorityFilter === 'warning') return alert.category.includes('warning');
        if (priorityFilter === 'opportunity') return alert.category.includes('opportunity');
        return true;
      });
    }
    
    // Apply sorting
    if (sortConfig.key) {
      filtered.sort((a, b) => {
        let aValue = a[sortConfig.key];
        let bValue = b[sortConfig.key];
        
        // Handle nested properties
        if (sortConfig.key === 'cogs') {
          aValue = enhanced_analytics?.[a.asin]?.cogs_data?.cogs || 0;
          bValue = enhanced_analytics?.[b.asin]?.cogs_data?.cogs || 0;
        }
        
        if (aValue < bValue) return sortConfig.direction === 'asc' ? -1 : 1;
        if (aValue > bValue) return sortConfig.direction === 'asc' ? 1 : -1;
        return 0;
      });
    } else {
      // Default sort by priority score
      filtered.sort((a, b) => b.priority_score - a.priority_score);
    }
    
    return filtered;
  }, [restock_alerts, searchQuery, priorityFilter, sortConfig, enhanced_analytics]);

  // Filter and sort enhanced analytics
  const sortedAnalytics = useMemo(() => {
    if (!enhanced_analytics) return [];
    
    let entries = Object.entries(enhanced_analytics);
    
    // Apply search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      entries = entries.filter(([asin, data]) => 
        data.product_name.toLowerCase().includes(query) ||
        asin.toLowerCase().includes(query)
      );
    }
    
    // Apply sorting
    if (sortConfig.key) {
      entries.sort(([asinA, dataA], [asinB, dataB]) => {
        let aValue, bValue;
        
        switch (sortConfig.key) {
          case 'product_name':
            aValue = dataA.product_name;
            bValue = dataB.product_name;
            break;
          case 'current_stock':
            aValue = dataA.restock?.current_stock || 0;
            bValue = dataB.restock?.current_stock || 0;
            break;
          case 'velocity':
            aValue = dataA.velocity?.weighted_velocity || 0;
            bValue = dataB.velocity?.weighted_velocity || 0;
            break;
          case 'days_left':
            aValue = getDaysLeftFromStock(dataA.stock_info);
            bValue = getDaysLeftFromStock(dataB.stock_info);
            if (typeof aValue !== 'number') aValue = 999999;
            if (typeof bValue !== 'number') bValue = 999999;
            break;
          case 'cogs':
            aValue = dataA.cogs_data?.cogs || 0;
            bValue = dataB.cogs_data?.cogs || 0;
            break;
          case 'suggested_quantity':
            aValue = dataA.restock?.suggested_quantity || 0;
            bValue = dataB.restock?.suggested_quantity || 0;
            break;
          case 'priority_score':
            aValue = dataA.priority?.score || 0;
            bValue = dataB.priority?.score || 0;
            break;
          default:
            aValue = 0;
            bValue = 0;
        }
        
        if (aValue < bValue) return sortConfig.direction === 'asc' ? -1 : 1;
        if (aValue > bValue) return sortConfig.direction === 'asc' ? 1 : -1;
        return 0;
      });
    } else {
      // Default sort by priority score
      entries.sort(([,a], [,b]) => (b.priority?.score || 0) - (a.priority?.score || 0));
    }
    
    return entries;
  }, [enhanced_analytics, searchQuery, sortConfig]);

  // Function to fetch purchase sources for an ASIN
  const fetchPurchaseSources = async (asin) => {
    setSourcesLoading(true);
    try {
      const response = await axios.get(`/api/asin/${asin}/purchase-sources`, { withCredentials: true });
      setPurchaseSources(response.data.sources || []);
      setModalAsin(asin);
      setShowSourcesModal(true);
    } catch (error) {
      
      // Show a simple alert or could add error state
      alert(error.response?.data?.message || 'Failed to fetch purchase sources');
    } finally {
      setSourcesLoading(false);
    }
  };

  // Function to extract URLs from a text string (handles multiple URLs in one cell)
  const extractUrlsFromText = (text) => {
    if (!text) return [];
    
    // Handle URLs that might be separated by spaces, semicolons, commas, or newlines
    const urlRegex = /https?:\/\/[^\s;,\n]+/gi;
    const urls = text.match(urlRegex) || [];
    
    // Clean URLs (remove trailing punctuation)
    return urls.map(url => url.replace(/[.,;]+$/, ''));
  };

  // Function to handle restock button click
  const handleRestockClick = async (asin, existingSourceLink) => {
    setSourcesLoading(true);
    try {
      // First, try to get sources from the backend
      const response = await axios.get(`/api/asin/${asin}/purchase-sources`, { withCredentials: true });
      const backendSources = response.data.sources || [];
      
      // Extract URLs from existing source link (handle multiple URLs in one cell)
      const extractedUrls = extractUrlsFromText(existingSourceLink);
      
      // Combine backend sources with extracted URLs, remove duplicates
      const allUrls = new Set();
      backendSources.forEach(source => allUrls.add(source.url));
      extractedUrls.forEach(url => allUrls.add(url));
      
      const uniqueUrls = Array.from(allUrls).filter(Boolean);
      
      if (uniqueUrls.length === 0) {
        alert('No purchase sources found for this product');
        return;
      } else if (uniqueUrls.length === 1) {
        // Only one URL found, open directly
        window.open(uniqueUrls[0], '_blank');
      } else {
        // Multiple URLs found, open all of them
        
        uniqueUrls.forEach(url => {
          window.open(url, '_blank');
        });
      }
    } catch (error) {
      
      // Fallback: extract and open URLs from existing source link
      const extractedUrls = extractUrlsFromText(existingSourceLink);
      if (extractedUrls.length > 0) {
        extractedUrls.forEach(url => {
          window.open(url, '_blank');
        });
      } else if (existingSourceLink) {
        // Last resort: try to open the raw source link
        window.open(existingSourceLink, '_blank');
      } else {
        alert('No purchase sources found for this product');
      }
    } finally {
      setSourcesLoading(false);
    }
  };

  // Add error handling for null/undefined analytics
  if (!analytics) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Smart Restock Alerts</h3>
        <p className="text-gray-500">Loading analytics data...</p>
      </div>
    );
  }

  // Show fallback mode message if present
  if (analytics.fallback_mode) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Smart Restock Alerts</h3>
        <div className="bg-yellow-50 border border-yellow-200 rounded-md p-4">
          <p className="text-yellow-800">⚠️ {analytics.message || 'Analytics running in basic mode. Enhanced restock features unavailable.'}</p>
          <p className="text-yellow-700 text-sm mt-2">Please check your report URLs in Settings to enable enhanced analytics.</p>
        </div>
      </div>
    );
  }

  // Show basic mode message if present
  if (analytics.basic_mode) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Smart Restock Alerts</h3>
        <div className="bg-blue-50 border border-blue-200 rounded-md p-4">
          <p className="text-blue-800">📊 {analytics.message}</p>
        </div>
      </div>
    );
  }

  if (!analytics.enhanced_analytics || Object.keys(analytics.enhanced_analytics).length === 0) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Smart Restock Alerts</h3>
        <div className="text-center py-8">
          <Package className="h-12 w-12 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-500 mb-2">No enhanced analytics data available</p>
          <p className="text-gray-400 text-sm">
            {analytics.error ? `Error: ${analytics.error}` : 'Check your report URLs in Settings and ensure you have recent sales data.'}
          </p>
        </div>
      </div>
    );
  }

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

  const formatCurrency = (amount) => {
    if (typeof amount === 'number') {
      return `$${amount.toFixed(2)}`;
    }
    return 'N/A';
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'Unknown';
    try {
      const date = new Date(dateString);
      
      // Use user's timezone from analytics if available
      const userTimezone = analytics?.user_timezone;
      
      const options = {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        ...(userTimezone && { timeZone: userTimezone })
      };
      
      return date.toLocaleDateString('en-US', options);
    } catch {
      return 'Unknown';
    }
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
    // Tab configuration
    const tabs = [
      {
        id: 'recommendations',
        name: 'Smart Restock Recommendations',
        description: 'AI-powered restocking suggestions based on velocity, trends, and seasonality',
        count: sortedAlerts.length
      },
      {
        id: 'analytics',
        name: 'All Products Analytics', 
        description: 'Complete analysis of your inventory',
        count: enhanced_analytics ? Object.keys(enhanced_analytics).length : 0
      },
      {
        id: 'detailed',
        name: 'Detailed Product Analytics',
        description: 'In-depth analysis of individual products with advanced metrics',
        count: enhanced_analytics ? Object.keys(enhanced_analytics).filter(asin => enhanced_analytics[asin]?.velocity).length : 0
      }
    ];

    return (
      <div className="space-y-6">
        <div className="bg-white rounded-lg shadow">
        {/* Tab Navigation */}
        <div className="border-b border-gray-200">
          <div className="px-6 py-4">
            <nav className="-mb-px flex space-x-8">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`whitespace-nowrap pb-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                    activeTab === tab.id
                      ? 'border-builders-500 text-builders-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
                >
                  {tab.name}
                  {tab.count > 0 && (
                    <span className={`ml-2 py-0.5 px-2 rounded-full text-xs font-medium ${
                      activeTab === tab.id
                        ? 'bg-builders-100 text-builders-600'
                        : 'bg-gray-100 text-gray-600'
                    }`}>
                      {tab.count}
                    </span>
                  )}
                </button>
              ))}
            </nav>
          </div>
        </div>

        {/* Tab Content */}
        <div className="px-6 py-4">
          {/* Tab Description */}
          <p className="text-xs text-gray-600 mb-3">
            {tabs.find(tab => tab.id === activeTab)?.description}
          </p>

          {/* Filter Controls */}
          <div className="flex flex-col sm:flex-row gap-4 mb-6">
            <div className="flex-1 relative">
              <Search className="absolute left-2 top-1/2 transform -translate-y-1/2 h-3 w-3 text-gray-400" />
              <input
                type="text"
                placeholder="Search products, ASINs, or descriptions..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-8 pr-2 py-1.5 text-xs border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-builders-500 focus:border-transparent"
              />
            </div>
            <div className="flex items-center space-x-2">
              {activeTab === 'recommendations' && (
                <>
                  <Filter className="h-3 w-3 text-gray-400" />
                  <select
                    value={priorityFilter}
                    onChange={(e) => setPriorityFilter(e.target.value)}
                    className="px-2 py-1.5 text-xs border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-builders-500 focus:border-transparent"
                  >
                    <option value="all">All Priorities</option>
                    <option value="critical">Critical Only</option>
                    <option value="warning">High Priority Only</option>
                    <option value="opportunity">Opportunities Only</option>
                  </select>
                </>
              )}
              <button
                onClick={() => resetColumnOrder(activeTab)}
                className="flex items-center px-2 py-1.5 text-xs text-gray-600 hover:text-gray-800 border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-builders-500"
                title="Reset column order"
              >
                <RotateCcw className="h-3 w-3 mr-1" />
                Reset Columns
              </button>
            </div>
          </div>

          {/* Smart Restock Recommendations Tab */}
          {activeTab === 'recommendations' && (
            <div className="overflow-x-auto border border-gray-200 rounded-lg">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    {columnOrders.recommendations.map((columnKey) => {
                      const column = columnDefinitions.recommendations[columnKey];
                      if (!column) return null;
                      
                      return (
                        <th 
                          key={columnKey}
                          className={`px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wide ${
                            column.draggable ? 'cursor-move' : ''
                          } ${
                            draggedColumn?.key === columnKey ? 'opacity-50' : ''
                          }`}
                          draggable={column.draggable}
                          onDragStart={(e) => column.draggable && handleDragStart(e, columnKey, 'recommendations')}
                          onDragOver={handleDragOver}
                          onDrop={(e) => handleDrop(e, columnKey, 'recommendations')}
                          onDragEnd={handleDragEnd}
                        >
                          <div className="flex items-center space-x-1">
                            {column.draggable && (
                              <GripVertical className="h-3 w-3 text-gray-400" />
                            )}
                            {column.sortKey ? (
                              <button
                                onClick={() => handleSort(column.sortKey)}
                                className="flex items-center space-x-1 hover:text-gray-700 text-xs"
                              >
                                <span>{column.label}</span>
                                {getSortIcon(column.sortKey)}
                              </button>
                            ) : (
                              <span className="text-xs">{column.label}</span>
                            )}
                          </div>
                        </th>
                      );
                    })}
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {sortedAlerts.length > 0 ? (
                    sortedAlerts.map((alert) => (
                      <tr key={alert.asin} className="hover:bg-gray-50">
                        {columnOrders.recommendations.map((columnKey) => 
                          renderRecommendationCell(columnKey, alert)
                        )}
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={columnOrders.recommendations.length} className="px-3 py-8 text-center">
                        <div className="flex flex-col items-center">
                          <Package className="h-8 w-8 text-gray-400 mb-2" />
                          <h3 className="text-xs font-medium text-gray-900 mb-1">No Priority Alerts</h3>
                          <p className="text-xs text-gray-500">
                            All products have adequate stock levels or sufficient lead time
                          </p>
                        </div>
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}

          {/* All Products Analytics Tab */}
          {activeTab === 'analytics' && enhanced_analytics && Object.keys(enhanced_analytics).length > 0 && (
            <div className="overflow-x-auto border border-gray-200 rounded-lg">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                    <button
                      onClick={() => handleSort('product_name')}
                      className="flex items-center space-x-1 hover:text-gray-700 text-xs"
                    >
                      <span>Product</span>
                      {getSortIcon('product_name')}
                    </button>
                  </th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                    <button
                      onClick={() => handleSort('current_stock')}
                      className="flex items-center space-x-1 hover:text-gray-700 text-xs"
                    >
                      <span>Current Stock</span>
                      {getSortIcon('current_stock')}
                    </button>
                  </th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                    <button
                      onClick={() => handleSort('velocity')}
                      className="flex items-center space-x-1 hover:text-gray-700 text-xs"
                    >
                      <span>Velocity</span>
                      {getSortIcon('velocity')}
                    </button>
                  </th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                    <span className="text-xs">Trend</span>
                  </th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                    <button
                      onClick={() => handleSort('days_left')}
                      className="flex items-center space-x-1 hover:text-gray-700 text-xs"
                    >
                      <span>Days Left</span>
                      {getSortIcon('days_left')}
                    </button>
                  </th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                    <button
                      onClick={() => handleSort('cogs')}
                      className="flex items-center space-x-1 hover:text-gray-700 text-xs"
                    >
                      <span>Last COGS</span>
                      {getSortIcon('cogs')}
                    </button>
                  </th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                    <span className="text-xs">Last 2 Months</span>
                  </th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                    <button
                      onClick={() => handleSort('suggested_quantity')}
                      className="flex items-center space-x-1 hover:text-gray-700 text-xs"
                    >
                      <span>Suggested Order</span>
                      {getSortIcon('suggested_quantity')}
                    </button>
                  </th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                    <button
                      onClick={() => handleSort('priority_score')}
                      className="flex items-center space-x-1 hover:text-gray-700 text-xs"
                    >
                      <span>Priority</span>
                      {getSortIcon('priority_score')}
                    </button>
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {sortedAnalytics.length > 0 ? sortedAnalytics
                  .slice(0, 20) // Show top 20
                  .map(([asin, data]) => (
                    <tr key={asin} className="hover:bg-gray-50">
                      <td className="px-3 py-2 whitespace-nowrap">
                        <div>
                          <div className="text-xs font-medium text-gray-900">
                            {data.product_name.length > 40 
                              ? data.product_name.substring(0, 40) + '...'
                              : data.product_name
                            }
                          </div>
                          <div className="text-xs text-gray-500">{asin}</div>
                        </div>
                      </td>
                      <td className="px-3 py-2 whitespace-nowrap text-xs text-gray-900">
                        {Math.round(data.restock.current_stock)}
                      </td>
                      <td className="px-3 py-2 whitespace-nowrap text-xs text-gray-900">
                        {data.velocity.weighted_velocity.toFixed(1)}/day
                      </td>
                      <td className="px-3 py-2 whitespace-nowrap">
                        <div className="flex items-center space-x-1">
                          {getTrendIcon(data.velocity.trend_direction)}
                          <span className="text-xs text-gray-900 capitalize">
                            {data.velocity.trend_direction}
                          </span>
                        </div>
                      </td>
                      <td className="px-3 py-2 whitespace-nowrap text-xs text-gray-900">
                        {formatDaysLeft(getDaysLeftFromStock(data.stock_info))}
                      </td>
                      <td className="px-3 py-2 whitespace-nowrap text-xs text-gray-900">
                        {data.cogs_data?.cogs ? (
                          <div className="flex items-center space-x-1">
                            <span className="text-green-700 font-medium text-xs">
                              {formatCurrency(data.cogs_data.cogs)}
                            </span>
                            {data.cogs_data.source_link && (
                              <a
                                href={data.cogs_data.source_link}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-blue-600 hover:text-blue-800"
                                title="Restock here"
                              >
                                <ExternalLink className="h-2 w-2" />
                              </a>
                            )}
                          </div>
                        ) : (
                          <span className="text-gray-400 text-xs">N/A</span>
                        )}
                      </td>
                      <td className="px-3 py-2 whitespace-nowrap text-xs text-gray-900">
                        {data.restock?.monthly_purchase_adjustment > 0 ? (
                          <div className="flex items-center space-x-1">
                            <ShoppingCart className="h-3 w-3 text-purple-600" />
                            <span className="text-purple-700 font-medium text-xs">
                              {data.restock.monthly_purchase_adjustment}
                            </span>
                          </div>
                        ) : (
                          <span className="text-gray-400 text-xs">-</span>
                        )}
                      </td>
                      <td className="px-3 py-2 whitespace-nowrap text-xs font-medium text-builders-600">
                        {data.restock.suggested_quantity}
                      </td>
                      <td className="px-3 py-2 whitespace-nowrap">
                        <span className={`inline-flex items-center px-1.5 py-0.5 rounded-full text-xs font-medium ${
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
                  )) : (
                    <tr>
                      <td colSpan="9" className="px-6 py-12 text-center">
                        <div className="flex flex-col items-center">
                          <BarChart3 className="h-12 w-12 text-gray-400 mb-3" />
                          <h3 className="text-sm font-medium text-gray-900 mb-1">No Products Found</h3>
                          <p className="text-sm text-gray-500">
                            No products match your search criteria
                          </p>
                        </div>
                      </td>
                    </tr>
                  )}
              </tbody>
            </table>
            </div>
          )}

          {/* Detailed Product Analytics Tab */}
          {activeTab === 'detailed' && enhanced_analytics && Object.keys(enhanced_analytics).length > 0 && (
            <div className="overflow-x-auto border border-gray-200 rounded-lg">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      <button
                        onClick={() => handleSort('product_name')}
                        className="flex items-center space-x-1 hover:text-gray-700"
                      >
                        <span>Product</span>
                        {getSortIcon('product_name')}
                      </button>
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      <button
                        onClick={() => handleSort('velocity')}
                        className="flex items-center space-x-1 hover:text-gray-700"
                      >
                        <span>Velocity Analysis</span>
                        {getSortIcon('velocity')}
                      </button>
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      <button
                        onClick={() => handleSort('current_stock')}
                        className="flex items-center space-x-1 hover:text-gray-700"
                      >
                        <span>Stock Status</span>
                        {getSortIcon('current_stock')}
                      </button>
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      <button
                        onClick={() => handleSort('suggested_quantity')}
                        className="flex items-center space-x-1 hover:text-gray-700"
                      >
                        <span>Restock Recommendation</span>
                        {getSortIcon('suggested_quantity')}
                      </button>
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      <button
                        onClick={() => handleSort('priority_score')}
                        className="flex items-center space-x-1 hover:text-gray-700"
                      >
                        <span>Priority</span>
                        {getSortIcon('priority_score')}
                      </button>
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {sortedAnalytics.length > 0 ? sortedAnalytics.map(([asin, data]) => (
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
                            {data?.velocity?.trend_direction === 'accelerating' && <TrendingUp className="h-4 w-4 text-green-500" />}
                            {data?.velocity?.trend_direction === 'declining' && <TrendingDown className="h-4 w-4 text-red-500" />}
                            {data?.velocity?.trend_direction === 'stable' && <Minus className="h-4 w-4 text-gray-400" />}
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
                  )) : (
                    <tr>
                      <td colSpan="5" className="px-6 py-12 text-center">
                        <div className="flex flex-col items-center">
                          <Package className="h-12 w-12 text-gray-400 mb-3" />
                          <h3 className="text-sm font-medium text-gray-900 mb-1">No Products Found</h3>
                          <p className="text-sm text-gray-500">
                            No products match your search criteria
                          </p>
                        </div>
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}

          {/* Show message when no data for active tab */}
          {activeTab === 'recommendations' && sortedAlerts.length === 0 && (
            <div className="text-center py-12">
              <Package className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">No Restock Recommendations</h3>
              <p className="text-gray-500">All products have adequate stock levels or sufficient lead time</p>
            </div>
          )}

          {activeTab === 'analytics' && (!enhanced_analytics || Object.keys(enhanced_analytics).length === 0) && (
            <div className="text-center py-12">
              <BarChart3 className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">No Analytics Data</h3>
              <p className="text-gray-500">Analytics data will appear here once your inventory data is processed</p>
            </div>
          )}

          {activeTab === 'detailed' && (!enhanced_analytics || Object.keys(enhanced_analytics).length === 0) && (
            <div className="text-center py-12">
              <Package className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">No products found</h3>
              <p className="text-gray-500">Detailed analytics will appear here once your inventory data is processed</p>
            </div>
          )}
        </div>
        </div>

        {/* Purchase Sources Modal */}
      {showSourcesModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg max-w-md w-full mx-4 max-h-96 overflow-y-auto">
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-medium text-gray-900">Choose Restock Source</h3>
                <button
                  onClick={() => setShowSourcesModal(false)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
              
              <div className="mb-4">
                <p className="text-sm text-gray-600">
                  ASIN: <span className="font-mono">{modalAsin}</span>
                </p>
                <p className="text-xs text-gray-500 mt-1">
                  You've purchased this product from {purchaseSources.length} different source{purchaseSources.length !== 1 ? 's' : ''}
                </p>
              </div>

              <div className="space-y-3">
                {purchaseSources.length > 0 ? (
                  purchaseSources.map((source, index) => (
                    <a
                      key={index}
                      href={source.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center justify-between p-3 border border-gray-200 rounded-lg hover:bg-gray-50 hover:border-gray-300 transition-colors group"
                    >
                      <div className="flex items-center space-x-3">
                        <Globe className="h-5 w-5 text-gray-400 group-hover:text-blue-500" />
                        <div>
                          <p className="font-medium text-gray-900">{source.display_name}</p>
                          <p className="text-xs text-gray-500 truncate max-w-48">
                            {source.url}
                          </p>
                        </div>
                      </div>
                      <ExternalLink className="h-4 w-4 text-gray-400 group-hover:text-blue-500" />
                    </a>
                  ))
                ) : (
                  <div className="text-center py-8">
                    <Package className="h-12 w-12 text-gray-300 mx-auto mb-4" />
                    <p className="text-gray-500">No purchase sources found</p>
                    <p className="text-xs text-gray-400 mt-1">
                      This product may not have purchase history with source links
                    </p>
                  </div>
                )}
              </div>

              <div className="mt-6 flex justify-end">
                <button
                  onClick={() => setShowSourcesModal(false)}
                  className="px-4 py-2 text-gray-600 hover:text-gray-800 text-sm"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
      </div>
    );
  } catch (error) {
    
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
});

export default SmartRestockAlerts;