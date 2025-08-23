import React, { useMemo, useState, useEffect } from 'react';
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
  RotateCcw,
  Calendar,
  BarChart3
} from 'lucide-react';
import { useProductImage, useProductImages } from '../hooks/useProductImages';
import StandardTable from './common/StandardTable';
import InventoryAgeAnalysis from './InventoryAgeAnalysis';

// Product image component that uses batch loaded images with fallback
const ProductImage = ({ asin, productName, batchImages, imagesLoading }) => {
  const [imgError, setImgError] = useState(false);
  const [retryCount, setRetryCount] = useState(0);
  const [currentImageUrl, setCurrentImageUrl] = useState(null);
  const { imageUrl: fallbackUrl, loading: fallbackLoading } = useProductImage(imgError && retryCount < 2 ? asin : null);
  
  // Effect to handle image URL fallbacks - must be called before any returns
  React.useEffect(() => {
    if (imgError && !currentImageUrl && asin) {
      // Try Amazon's direct image URL as fallback
      const directAmazonUrl = `https://ws-na.amazon-adsystem.com/widgets/q?_encoding=UTF8&ASIN=${asin}&Format=_SL250_&ID=AsinImage&MarketPlace=US&ServiceVersion=20070822&WS=1`;
      setCurrentImageUrl(directAmazonUrl);
    }
  }, [imgError, currentImageUrl, asin]);

  // Enhanced fallback logic - try multiple endpoints
  const imageUrl = currentImageUrl || (imgError && fallbackUrl ? fallbackUrl : batchImages?.[asin]);
  const isLoading = (imagesLoading && !batchImages?.[asin]) || (imgError && fallbackLoading);
  
  // For debugging - always show something visible
  if (!asin) {
    return (
      <div className="h-16 w-16 rounded-lg bg-red-100 border border-red-300 flex items-center justify-center" title="No ASIN provided">
        <span className="text-sm text-red-600">!</span>
      </div>
    );
  }
  
  if (isLoading) {
    return (
      <div className="h-16 w-16 rounded-lg bg-gray-100 border border-gray-200 flex items-center justify-center" title="Loading image...">
        <div className="h-6 w-6 bg-gray-300 rounded animate-pulse" />
      </div>
    );
  }

  if (!imageUrl || (imgError && !fallbackUrl)) {
    return (
      <div className="h-16 w-16 rounded-lg bg-gradient-to-br from-blue-50 to-indigo-100 border border-blue-200 flex items-center justify-center" title={`Product: ${asin} - ${imgError ? 'Image failed to load' : 'No image available'}`}>
        <Package className="h-8 w-8 text-blue-600" />
      </div>
    );
  }

  return (
    <div className="h-16 w-16 rounded-lg overflow-hidden border border-gray-200 bg-white" title={`Product ${asin}`}>
      <img
        src={imageUrl}
        alt={productName || `Product ${asin}`}
        className="h-full w-full object-cover"
        loading="lazy"
        onError={() => {
          if (retryCount < 3) { // Increased retry count for more fallback attempts
            setRetryCount(prev => prev + 1);
            setImgError(true);
          } else {
            setImgError(true);
          }
        }}
        onLoad={() => {
          // Reset error state when image loads successfully
          setImgError(false);
          setRetryCount(0);
        }}
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
  
  // Extract data first (before any conditional returns to avoid hook order issues)
  const { enhanced_analytics, restock_alerts } = analytics || {};
  
  // Extract all ASINs for batch image loading
  const allAsins = useMemo(() => {
    if (!restock_alerts) return [];
    
    return Object.values(restock_alerts)
      .filter(alert => 
        alert.suggested_quantity && 
        alert.suggested_quantity > 0 && 
        !isNaN(alert.suggested_quantity) &&
        alert.asin
      )
      .map(alert => alert.asin);
  }, [restock_alerts]);
  
  // Use batch image loading for better performance
  const { images: batchImages, loading: imagesLoading } = useProductImages(allAsins);
  
  // Default column order
  const defaultColumnOrder = ['product', 'priority', 'current_stock', 'days_left', 'velocity', 'trend', 'last_cogs', 'already_ordered', 'suggested_order', 'actions'];
  
  // Search fields for StandardTable
  const searchFields = ['product_name', 'asin'];
  
  // Filters for StandardTable
  const tableFilters = [
    {
      key: 'priority',
      label: 'Priority',
      allLabel: 'All Priorities',
      options: [
        { value: 'critical', label: 'Critical Only' },
        { value: 'warning', label: 'High Priority Only' },
        { value: 'opportunity', label: 'Opportunities Only' }
      ],
      filterFn: (item, value) => {
        if (value === 'critical') return item.category.includes('critical');
        if (value === 'warning') return item.category.includes('warning');
        if (value === 'opportunity') return item.category.includes('opportunity');
        return true;
      }
    }
  ];
  
  
  // Column definitions for StandardTable
  const tableColumns = {
    product: { 
      key: 'product', 
      label: 'Product', 
      sortKey: 'product_name', 
      draggable: false 
    },
    priority: { 
      key: 'priority', 
      label: 'Priority', 
      sortKey: 'priority_score', 
      draggable: true 
    },
    current_stock: { 
      key: 'current_stock', 
      label: 'Current Stock', 
      sortKey: 'current_stock', 
      draggable: true 
    },
    days_left: { 
      key: 'days_left', 
      label: 'Days Left', 
      sortKey: 'days_left', 
      draggable: true 
    },
    velocity: { 
      key: 'velocity', 
      label: 'Velocity', 
      sortKey: 'velocity', 
      draggable: true 
    },
    trend: { 
      key: 'trend', 
      label: 'Trend', 
      sortKey: null, 
      draggable: true 
    },
    last_cogs: { 
      key: 'last_cogs', 
      label: 'Last COGS', 
      sortKey: 'cogs',
      sortFn: (a, b, direction) => {
        const aValue = enhanced_analytics?.[a.asin]?.cogs_data?.cogs || 0;
        const bValue = enhanced_analytics?.[b.asin]?.cogs_data?.cogs || 0;
        return direction === 'asc' ? aValue - bValue : bValue - aValue;
      },
      draggable: true 
    },
    already_ordered: { 
      key: 'already_ordered', 
      label: 'Already Ordered', 
      sortKey: null, 
      draggable: true 
    },
    suggested_order: { 
      key: 'suggested_order', 
      label: 'Suggested Order', 
      sortKey: 'suggested_quantity', 
      draggable: true 
    },
    actions: { 
      key: 'actions', 
      label: 'Actions', 
      sortKey: null, 
      draggable: false 
    }
  };



  // Render cell function for StandardTable (existing)
  const renderCell = (columnKey, alert) => {
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
                  <ProductImage 
                    asin={alert.asin} 
                    productName={alert.product_name}
                    batchImages={batchImages}
                    imagesLoading={imagesLoading}
                  />
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
            {/* Show restock button for all products */}
            <button
              onClick={() => handleRestockClick(alert.asin, enhanced_analytics?.[alert.asin]?.cogs_data?.source_link || null)}
              className="inline-flex items-center px-2 py-1 bg-blue-600 text-white text-xs rounded-md hover:bg-blue-700 transition-colors disabled:opacity-50"
              disabled={sourcesLoading}
              title={enhanced_analytics?.[alert.asin]?.cogs_data?.source_link ? "Open supplier link" : "Find purchase sources"}
            >
              <ShoppingCart className="h-3 w-3 mr-1" />
              Restock
            </button>
          </td>
        );
      default:
        return <td key={columnKey}></td>;
    }
  };

  // Prepare table data
  const tableData = useMemo(() => {
    if (!restock_alerts) return [];
    
    let data = Object.values(restock_alerts);
    
    // Filter out items with 0 or null suggested quantity
    data = data.filter(alert => 
      alert.suggested_quantity && 
      alert.suggested_quantity > 0 && 
      !isNaN(alert.suggested_quantity)
    );
    
    // Add id field for StandardTable
    data = data.map(alert => ({
      ...alert,
      id: alert.asin
    }));
    
    // Default sort by priority score
    data.sort((a, b) => b.priority_score - a.priority_score);
    
    return data;
  }, [restock_alerts]);

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
    
    // Strategy: Use existing source link immediately if available, then try to enhance with backend data
    const extractedUrls = extractUrlsFromText(existingSourceLink);
    
    // If we have a direct source link, open it immediately
    if (extractedUrls.length > 0) {
      extractedUrls.forEach(url => {
        window.open(url, '_blank');
      });
      setSourcesLoading(false);
      return;
    } else if (existingSourceLink && existingSourceLink.startsWith('http')) {
      // Direct URL in source link
      window.open(existingSourceLink, '_blank');
      setSourcesLoading(false);
      return;
    }
    
    // If no direct source link available, try backend API (this might be slow)
    try {
      const response = await axios.get(`/api/asin/${asin}/purchase-sources`, { withCredentials: true });
      const backendSources = response.data.sources || [];
      
      if (backendSources.length > 0) {
        backendSources.forEach(source => {
          window.open(source.url, '_blank');
        });
      } else {
        // Last resort: open Amazon product page
        window.open(`https://www.amazon.com/dp/${asin}`, '_blank');
      }
    } catch (error) {
      console.log('Backend source lookup failed, opening Amazon page:', error);
      // Fallback to Amazon product page
      window.open(`https://www.amazon.com/dp/${asin}`, '_blank');
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
              <p className="text-xs text-gray-600 mb-6">
                Products requiring immediate restocking attention based on current stock levels and sales velocity.
              </p>

              <StandardTable
                data={tableData}
                tableKey="smart-restock-alerts"
                columns={tableColumns}
                defaultColumnOrder={defaultColumnOrder}
                renderCell={renderCell}
                enableSearch={true}
                enableFilters={true}
                enableSorting={true}
                enableColumnReordering={true}
                enableColumnResetting={true}
                enableFullscreen={true}
                searchPlaceholder="Search products, ASINs, or descriptions..."
                searchFields={searchFields}
                filters={tableFilters}
                emptyIcon={Package}
                emptyTitle="No Priority Alerts"
                emptyDescription="All products have adequate stock levels or sufficient lead time"
                title="Smart Restock Alerts"
                className="mt-4"
              />
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