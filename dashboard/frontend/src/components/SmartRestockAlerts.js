import React, { useMemo, useState } from 'react';
import axios from 'axios';
import { 
  TrendingUp, 
  TrendingDown, 
  Minus,
  Package,
  ShoppingCart,
  ExternalLink,
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
import { useProductImage } from '../hooks/useProductImages';

// Product image component that uses optimized backend API
const ProductImage = ({ asin, productName }) => {
  // Always show a visible element to debug
  const [imgError, setImgError] = useState(false);
  const { imageUrl, loading, error } = useProductImage(asin);
  
  // For debugging - always show something visible
  if (!asin) {
    return (
      <div className="h-8 w-8 rounded-md bg-red-100 border border-red-300 flex items-center justify-center" title="No ASIN provided">
        <span className="text-xs text-red-600">!</span>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="h-8 w-8 rounded-md bg-gray-100 border border-gray-200 flex items-center justify-center" title="Loading image...">
        <div className="h-3 w-3 bg-gray-300 rounded animate-pulse" />
      </div>
    );
  }

  if (error || !imageUrl || imgError) {
    return (
      <div className="h-8 w-8 rounded-md bg-gradient-to-br from-blue-50 to-indigo-100 border border-blue-200 flex items-center justify-center" title={`Product: ${asin} - ${error ? 'Error' : imgError ? 'Image failed to load' : 'No URL'}`}>
        <Package className="h-4 w-4 text-blue-600" />
      </div>
    );
  }

  return (
    <div className="h-8 w-8 rounded-md overflow-hidden border border-gray-200 bg-white" title={`Product ${asin}`}>
      <img
        src={imageUrl}
        alt={productName || `Product ${asin}`}
        className="h-full w-full object-cover"
        loading="lazy"
        onError={() => setImgError(true)}
      />
    </div>
  );
};

const SmartRestockAlerts = React.memo(({ analytics, loading = false }) => {
  // Removed tab state - SmartRestockAlerts now only shows recommendations
  
  // State for restock sources modal
  const [showSourcesModal, setShowSourcesModal] = useState(false);
  const [modalAsin] = useState('');
  const [purchaseSources] = useState([]);
  const [sourcesLoading, setSourcesLoading] = useState(false);
  
  // State for filtering and sorting
  const [searchQuery, setSearchQuery] = useState('');
  const [priorityFilter, setPriorityFilter] = useState('all');
  const [sortConfig, setSortConfig] = useState({ key: null, direction: 'asc' });
  
  // State for column ordering
  const [draggedColumn, setDraggedColumn] = useState(null);
  
  // Force product to be first and ensure it's included
  const getColumnOrder = () => {
    const saved = JSON.parse(localStorage.getItem('smart-restock-column-order-recommendations') || 'null');
    if (saved) {
      // Remove product from saved order if it exists
      const filtered = saved.filter(col => col !== 'product');
      // Always put product first
      return ['product', ...filtered];
    }
    return ['product', 'priority', 'current_stock', 'days_left', 'velocity', 'trend', 'last_cogs', 'already_ordered', 'suggested_order', 'actions'];
  };
  
  const [columnOrders, setColumnOrders] = useState({
    recommendations: getColumnOrder()
  });
  
  // Extract data first (before any conditional returns to avoid hook order issues)
  const { enhanced_analytics, restock_alerts } = analytics || {};

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
      product: { key: 'product', label: 'Product', sortKey: 'product_name', draggable: false },
      priority: { key: 'priority', label: 'Priority', sortKey: 'priority_score', draggable: true },
      current_stock: { key: 'current_stock', label: 'Current Stock', sortKey: 'current_stock', draggable: true },
      days_left: { key: 'days_left', label: 'Days Left', sortKey: 'days_left', draggable: true },
      velocity: { key: 'velocity', label: 'Velocity', sortKey: 'velocity', draggable: true },
      trend: { key: 'trend', label: 'Trend', sortKey: null, draggable: true },
      last_cogs: { key: 'last_cogs', label: 'Last COGS', sortKey: 'cogs', draggable: true },
      already_ordered: { key: 'already_ordered', label: 'Already Ordered', sortKey: null, draggable: true },
      suggested_order: { key: 'suggested_order', label: 'Suggested Order', sortKey: 'suggested_quantity', draggable: true },
      actions: { key: 'actions', label: 'Actions', sortKey: null, draggable: false }
    }
  };

  // Drag and drop handlers
  const handleDragStart = (e, columnKey, tableType) => {
    const column = columnDefinitions[tableType]?.[columnKey];
    if (!column || !column.draggable) {
      e.preventDefault();
      return;
    }
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

    // Prevent dropping on non-draggable columns
    const targetColumn = columnDefinitions[tableType]?.[targetColumnKey];
    const draggedCol = columnDefinitions[tableType]?.[draggedColumn.key];
    if (!targetColumn || !draggedCol || !targetColumn.draggable || !draggedCol.draggable) {
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
      
      // Ensure product always stays first
      const productIndex = newOrder.indexOf('product');
      if (productIndex > 0) {
        newOrder.splice(productIndex, 1);
        newOrder.unshift('product');
      }

      // Update state
      setColumnOrders(prev => ({
        ...prev,
        [tableType]: newOrder
      }));

      // Save to localStorage (without product since we always add it first)
      const toSave = newOrder.filter(col => col !== 'product');
      localStorage.setItem(`smart-restock-column-order-${tableType}`, JSON.stringify(toSave));
    }
    
    setDraggedColumn(null);
  };

  const handleDragEnd = () => {
    setDraggedColumn(null);
  };

  // Reset column order to default
  const resetColumnOrder = (tableType) => {
    const defaultOrders = {
      recommendations: ['product', 'priority', 'current_stock', 'days_left', 'velocity', 'trend', 'last_cogs', 'already_ordered', 'suggested_order', 'actions']
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
            <div className="flex items-center space-x-2">
              <div className="flex-shrink-0">
                <a 
                  href={`https://www.amazon.com/dp/${alert.asin}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block hover:opacity-80 transition-opacity"
                >
                  <ProductImage asin={alert.asin} productName={alert.product_name} />
                </a>
              </div>
              <div className="min-w-0 flex-1">
                <div className="text-xs font-medium text-gray-900">
                  <a 
                    href={`https://www.amazon.com/dp/${alert.asin}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="hover:text-blue-600 transition-colors"
                    title={alert.product_name}
                  >
                    {alert.product_name.length > 45 
                      ? alert.product_name.substring(0, 45) + '...'
                      : alert.product_name
                    }
                  </a>
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
            <div className="flex items-center justify-center" title={alert.trend}>
              {getTrendIcon(alert.trend)}
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
            <div className="text-sm font-bold text-builders-600">
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
    
    // Filter out items with 0 or null suggested quantity
    filtered = filtered.filter(alert => 
      alert.suggested_quantity && 
      alert.suggested_quantity > 0 && 
      !isNaN(alert.suggested_quantity)
    );
    
    // Apply search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(alert => 
        alert.product_name.toLowerCase().includes(query) ||
        alert.asin.toLowerCase().includes(query)
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
        <h3 className="text-sm font-medium text-gray-900 mb-4">Smart Restock Alerts</h3>
        <p className="text-gray-500">Loading analytics data...</p>
      </div>
    );
  }

  // Show fallback mode message if present
  if (analytics.fallback_mode) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-sm font-medium text-gray-900 mb-4">Smart Restock Alerts</h3>
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
        <h3 className="text-sm font-medium text-gray-900 mb-4">Smart Restock Alerts</h3>
        <div className="bg-blue-50 border border-blue-200 rounded-md p-4">
          <p className="text-blue-800">📊 {analytics.message}</p>
        </div>
      </div>
    );
  }

  if (!analytics.enhanced_analytics || Object.keys(analytics.enhanced_analytics).length === 0) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-sm font-medium text-gray-900 mb-4">Smart Restock Alerts</h3>
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

  try {
    return (
      <div className="space-y-6">
        <div className="bg-white rounded-lg shadow relative">
          <div className="px-6 py-4">
            {loading && (
              <div className="absolute inset-0 bg-white bg-opacity-75 flex items-center justify-center z-10">
                <div className="flex items-center space-x-2">
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-builders-500"></div>
                  <span className="text-sm text-gray-600">Refreshing data...</span>
                </div>
              </div>
            )}
            <div className={loading ? 'opacity-50' : ''}>
            <p className="text-xs text-gray-600 mb-3">
              Products requiring immediate restocking attention based on current stock levels and sales velocity.
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
                <button
                  onClick={() => resetColumnOrder('recommendations')}
                  className="flex items-center px-2 py-1.5 text-xs text-gray-600 hover:text-gray-800 border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-builders-500"
                  title="Reset column order"
                >
                  <RotateCcw className="h-3 w-3 mr-1" />
                  Reset Columns
                </button>
              </div>
            </div>

            {/* Smart Restock Recommendations Table */}
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
                            column.draggable ? 'cursor-move' : 'cursor-default'
                          } ${
                            draggedColumn?.key === columnKey ? 'opacity-50' : ''
                          }`}
                          draggable={column.draggable === true}
                          onDragStart={(e) => {
                            if (!column.draggable) {
                              e.preventDefault();
                              return;
                            }
                            handleDragStart(e, columnKey, 'recommendations');
                          }}
                          onDragOver={column.draggable ? handleDragOver : undefined}
                          onDrop={(e) => column.draggable ? handleDrop(e, columnKey, 'recommendations') : e.preventDefault()}
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

            {/* Show message when no restock recommendations */}
            {sortedAlerts.length === 0 && (
              <div className="text-center py-12">
                <Package className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                <h3 className="text-sm font-medium text-gray-900 mb-2">No Restock Recommendations</h3>
                <p className="text-gray-500">All products have adequate stock levels or sufficient lead time</p>
              </div>
            )}
            </div>
          </div>
        </div>

        {/* Purchase Sources Modal */}
        {showSourcesModal && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg max-w-md w-full mx-4 max-h-96 overflow-y-auto">
              <div className="p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-medium text-gray-900">Choose Restock Source</h3>
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
        <h3 className="text-sm font-medium text-gray-900 mb-4">Smart Restock Alerts</h3>
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