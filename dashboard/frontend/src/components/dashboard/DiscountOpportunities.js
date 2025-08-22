import React, { useState, useEffect } from 'react';
import { 
  Target, 
  TrendingDown, 
  Percent,
  AlertTriangle,
  ExternalLink,
  Package,
  Clock,
  RefreshCw,
  Mail
} from 'lucide-react';
import axios from 'axios';
import StandardTable from '../common/StandardTable';
import { useProductImage } from '../../hooks/useProductImages';

// Product image component that uses optimized backend API
const ProductImage = ({ asin, productName }) => {
  const { imageUrl, loading, error } = useProductImage(asin);

  if (loading) {
    return (
      <div className="h-16 w-16 rounded-lg bg-gray-100 border border-gray-200 flex items-center justify-center">
        <div className="h-6 w-6 bg-gray-300 rounded animate-pulse" />
      </div>
    );
  }

  if (error || !imageUrl) {
    return (
      <div className="h-16 w-16 rounded-lg bg-gradient-to-br from-blue-50 to-indigo-100 border border-blue-200 flex items-center justify-center" title={`Product: ${asin}`}>
        <Package className="h-8 w-8 text-blue-600" />
      </div>
    );
  }

  return (
    <div className="h-16 w-16 rounded-lg overflow-hidden border border-gray-200 bg-white">
      <img
        src={imageUrl}
        alt={productName || `Product ${asin}`}
        className="h-full w-full object-cover"
        loading="lazy"
      />
    </div>
  );
};

const DiscountOpportunities = () => {
  const [activeTab, setActiveTab] = useState('opportunities');
  const [opportunities, setOpportunities] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [retailerFilter, setRetailerFilter] = useState('');
  const [stats, setStats] = useState(null);


  const tabs = [
    { id: 'opportunities', name: 'Opportunities', icon: Target },
    { id: 'pricing', name: 'Pricing Analysis', icon: Percent },
    { id: 'trends', name: 'Market Trends', icon: TrendingDown }
  ];


  const fetchOpportunities = async (forceRefresh = false) => {
    try {
      setLoading(true);
      setError(null);
      
      const endpoint = forceRefresh 
        ? '/api/discount-opportunities/refresh' 
        : '/api/discount-opportunities/analyze';
      
      const response = await axios.post(endpoint, {
        retailer: retailerFilter
      }, { withCredentials: true });
      
      // Parse response data if it's a string
      let responseData = response.data;
      if (typeof response.data === 'string') {
        try {
          responseData = JSON.parse(response.data);
        } catch (e) {
          throw new Error('Invalid JSON response from server');
        }
      }
      
      // Extract opportunities data
      const opportunitiesData = responseData.opportunities || [];
      const statsData = {
        totalAlertsProcessed: responseData.total_alerts_processed,
        matchedProducts: responseData.matched_products,
        restockNeededCount: responseData.restock_needed_count,
        notNeededCount: responseData.not_needed_count,
        notTrackedCount: responseData.not_tracked_count,
        message: responseData.message
      };
      
      // Filter out duplicate ASINs and non-restock items
      const filteredOpportunities = [];
      const seenASINs = new Set();
      let notNeededFiltered = 0;
      
      opportunitiesData.forEach(opportunity => {
        // Skip if duplicate ASIN
        if (seenASINs.has(opportunity.asin)) {
          return;
        }
        
        // Skip if doesn't need restocking
        if (opportunity.status === 'Not Needed' || !opportunity.needs_restock) {
          notNeededFiltered++;
          return;
        }
        
        seenASINs.add(opportunity.asin);
        filteredOpportunities.push(opportunity);
      });
      
      setOpportunities(filteredOpportunities);
      setStats({
        ...statsData,
        originalCount: opportunitiesData.length,
        uniqueCount: filteredOpportunities.length,
        duplicatesRemoved: opportunitiesData.length - filteredOpportunities.length - notNeededFiltered,
        notNeededFiltered: notNeededFiltered
      });
      setLastUpdated(new Date());
      
    } catch (error) {
      setError(error.response?.data?.message || 'Failed to fetch discount opportunities');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'opportunities') {
      fetchOpportunities();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, retailerFilter]);

  const getPriorityColor = (priority) => {
    switch (priority) {
      case 'critical_high_velocity':
      case 'critical_low_velocity':
        return 'text-red-600 bg-red-100';
      case 'warning_high_velocity':
      case 'warning_moderate':
        return 'text-yellow-600 bg-yellow-100';
      case 'opportunity_high_velocity':
        return 'text-blue-600 bg-blue-100';
      default:
        return 'text-gray-600 bg-gray-100';
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'Restock Needed':
        return 'text-red-700 bg-red-100';
      case 'Not Needed':
        return 'text-green-700 bg-green-100';
      case 'Not Tracked':
        return 'text-gray-700 bg-gray-100';
      default:
        return 'text-blue-700 bg-blue-100';
    }
  };

  const formatTimeAgo = (timestamp) => {
    if (!timestamp) return 'Unknown';
    
    try {
      const now = new Date();
      const alertTime = new Date(timestamp);
      
      if (isNaN(alertTime.getTime())) return 'Invalid date';
      
      const diffHours = Math.floor((now - alertTime) / (1000 * 60 * 60));
      
      if (diffHours < 1) return 'Just now';
      if (diffHours === 1) return '1 hour ago';
      if (diffHours < 24) return `${diffHours} hours ago`;
      
      const diffDays = Math.floor(diffHours / 24);
      if (diffDays === 1) return '1 day ago';
      return `${diffDays} days ago`;
    } catch (error) {
      return 'Unknown';
    }
  };

  // Table configuration for StandardTable
  const tableColumns = {
    product: {
      key: 'product',
      label: 'Product',
      sortKey: 'product_name',
      draggable: true
    },
    retailer: {
      key: 'retailer',
      label: 'Retailer',
      sortKey: 'retailer',
      draggable: true
    },
    status: {
      key: 'status',
      label: 'Status',
      sortKey: 'status',
      draggable: true
    },
    inventory: {
      key: 'inventory',
      label: 'Inventory',
      sortKey: 'current_stock',
      draggable: true
    },
    alert_time: {
      key: 'alert_time',
      label: 'Alert Time',
      sortKey: 'alert_time',
      draggable: true
    },
    actions: {
      key: 'actions',
      label: 'Actions',
      draggable: false
    }
  };

  const defaultColumnOrder = ['product', 'retailer', 'status', 'inventory', 'alert_time', 'actions'];

  const tableFilters = [
    {
      key: 'status',
      label: 'Status',
      defaultValue: 'all',
      options: [
        { value: 'restock_needed', label: 'Restock Needed' },
        { value: 'not_tracked', label: 'Not Tracked' }
      ],
      filterFn: (item, value) => {
        switch (value) {
          case 'restock_needed': return item.status === 'Restock Needed';
          case 'not_tracked': return item.status === 'Not Tracked';
          default: return true;
        }
      }
    },
    {
      key: 'retailer',
      label: 'Retailer',
      defaultValue: 'all',
      options: [
        { value: 'walmart', label: 'Walmart' },
        { value: 'target', label: 'Target' },
        { value: 'lowes', label: 'Lowes' },
        { value: 'vitacost', label: 'Vitacost' },
        { value: 'kohls', label: "Kohl's" }
      ],
      filterFn: (item, value) => item.retailer.toLowerCase().includes(value.toLowerCase())
    }
  ];

  const renderTableCell = (columnKey, opportunity, index) => {
    switch (columnKey) {
      case 'product':
        return (
          <td key={columnKey} className="px-3 py-3 whitespace-nowrap w-80">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <a 
                  href={`https://www.amazon.com/dp/${opportunity.asin}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block hover:opacity-80 transition-opacity"
                >
                  <ProductImage asin={opportunity.asin} productName={opportunity.product_name} />
                </a>
              </div>
              <div className="ml-3 min-w-0 flex-1">
                <div className="text-sm font-medium truncate" title={opportunity.product_name || opportunity.asin}>
                  <a 
                    href={`https://www.amazon.com/dp/${opportunity.asin}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-gray-900 hover:text-blue-600 transition-colors"
                  >
                    {opportunity.product_name ? (
                      opportunity.product_name.length > 35 
                        ? `${opportunity.product_name.substring(0, 35)}...`
                        : opportunity.product_name
                    ) : opportunity.asin}
                  </a>
                </div>
                <div className="text-xs text-gray-500 truncate">
                  {opportunity.asin}
                </div>
                {opportunity.note && (
                  <div className="text-xs text-blue-600 mt-1 truncate" title={opportunity.note}>
                    {opportunity.note.length > 25 ? `${opportunity.note.substring(0, 25)}...` : opportunity.note}
                  </div>
                )}
              </div>
            </div>
          </td>
        );
      
      case 'retailer':
        return (
          <td key={columnKey} className="px-3 py-3 whitespace-nowrap w-32">
            <div className="text-sm text-gray-900 truncate">{opportunity.retailer}</div>
            {opportunity.promo_message && (
              <div className="text-xs text-green-600 mt-1 truncate" title={opportunity.promo_message}>
                {opportunity.promo_message.length > 20 ? `${opportunity.promo_message.substring(0, 20)}...` : opportunity.promo_message}
              </div>
            )}
          </td>
        );
      
      case 'status':
        return (
          <td key={columnKey} className="px-3 py-3 whitespace-nowrap w-36">
            <div className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(opportunity.status)}`}>
              {opportunity.status}
            </div>
          </td>
        );
      
      case 'inventory':
        return (
          <td key={columnKey} className="px-3 py-3 whitespace-nowrap w-40">
            {opportunity.status === 'Not Tracked' ? (
              <div className="text-sm text-gray-500 italic">
                Product not in inventory
              </div>
            ) : (
              <>
                <div className="text-sm text-gray-900">
                  <div className="flex items-center space-x-2">
                    <Package className="h-4 w-4 text-gray-500" />
                    <span>{opportunity.current_stock || 0} units</span>
                  </div>
                  {opportunity.needs_restock && (
                    <div className="text-xs text-gray-500 mt-1">
                      Need: {opportunity.suggested_quantity || 0} • {typeof opportunity.days_left === 'number' ? opportunity.days_left.toFixed(1) : 'N/A'} days left
                    </div>
                  )}
                  {opportunity.velocity > 0 && (
                    <div className="text-xs text-gray-500">
                      Velocity: {(opportunity.velocity || 0).toFixed(2)}/day
                    </div>
                  )}
                </div>
                {opportunity.restock_priority !== 'not_tracked' && opportunity.restock_priority !== 'normal' && (
                  <div className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium mt-2 ${getPriorityColor(opportunity.restock_priority)}`}>
                    {opportunity.restock_priority.replace('_', ' ')}
                  </div>
                )}
              </>
            )}
          </td>
        );
      
      case 'alert_time':
        return (
          <td key={columnKey} className="px-3 py-3 whitespace-nowrap w-32">
            <div className="text-sm text-gray-900">
              <div className="flex items-center space-x-1">
                <Clock className="h-4 w-4 text-gray-500" />
                <span>{formatTimeAgo(opportunity.alert_time)}</span>
              </div>
            </div>
          </td>
        );
      
      case 'actions':
        return (
          <td key={columnKey} className="px-3 py-3 whitespace-nowrap text-right text-sm font-medium w-48">
            <div className="flex items-center justify-end space-x-2">
              {opportunity.source_link ? (
                <a
                  href={opportunity.source_link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={`inline-flex items-center space-x-1 px-3 py-1 rounded-md text-sm font-medium transition-colors ${
                    opportunity.status === 'Restock Needed' 
                      ? 'text-white bg-blue-600 hover:bg-blue-700' 
                      : 'text-blue-600 bg-blue-50 hover:bg-blue-100'
                  }`}
                >
                  <ExternalLink className="h-4 w-4" />
                  <span>{opportunity.status === 'Restock Needed' ? 'Buy Now' : 'View Deal'}</span>
                </a>
              ) : (
                <span className="text-gray-400 text-sm">No link</span>
              )}
              {opportunity.status === 'Not Needed' && (
                <span className="text-xs text-green-600 bg-green-50 px-2 py-1 rounded">
                  ✓ Stocked
                </span>
              )}
              {opportunity.status === 'Not Tracked' && (
                <span className="text-xs text-gray-600 bg-gray-50 px-2 py-1 rounded">
                  Not Tracked
                </span>
              )}
            </div>
          </td>
        );
      
      default:
        return <td key={columnKey}></td>;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center space-x-3">
        <Target className="h-8 w-8 text-blue-500" />
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Discount Opportunities</h1>
          <p className="text-gray-600">Find products with pricing opportunities and profit margins</p>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`py-2 px-1 border-b-2 font-medium text-sm flex items-center space-x-2 ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <Icon className="h-4 w-4" />
                <span>{tab.name}</span>
              </button>
            );
          })}
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'opportunities' && (
        <div className="space-y-6">
          {/* Stats and Controls */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center space-y-4 sm:space-y-0">
              <div>
                <h3 className="text-lg font-medium text-gray-900">Email Opportunities</h3>
                <p className="text-sm text-gray-600">
                  Products from email alerts that need restocking (past 7 days)
                </p>
                {stats && (
                  <div className="mt-2 text-xs text-gray-500">
                    {stats.message} • {stats.totalAlertsProcessed} emails processed • Showing {stats.uniqueCount} restock opportunities
                    {stats.cached && (
                      <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                        Cached {stats.cache_age_hours < 1 
                          ? `(${Math.round(stats.cache_age_hours * 60)}m ago)` 
                          : stats.cache_age_hours < 24 
                            ? `(${Math.round(stats.cache_age_hours)}h ago)`
                            : `(${Math.round(stats.cache_age_hours / 24)}d ago)`
                        }
                      </span>
                    )}
                    {(stats.duplicatesRemoved > 0 || stats.notNeededFiltered > 0) && (
                      <span className="ml-2 text-orange-600 font-medium">
                        (filtered: {stats.duplicatesRemoved > 0 && `${stats.duplicatesRemoved} duplicate${stats.duplicatesRemoved !== 1 ? 's' : ''}`}{stats.duplicatesRemoved > 0 && stats.notNeededFiltered > 0 && ', '}{stats.notNeededFiltered > 0 && `${stats.notNeededFiltered} non-restock`})
                      </span>
                    )}
                    {stats.restockNeededCount !== undefined && (
                      <div className="mt-1">
                        Original breakdown: {stats.restockNeededCount} need restocking, {stats.notNeededCount} not needed, {stats.notTrackedCount} not tracked
                      </div>
                    )}
                  </div>
                )}
              </div>
              
              <div className="flex items-center space-x-3">
                {/* Retailer Filter */}
                <select
                  value={retailerFilter}
                  onChange={(e) => setRetailerFilter(e.target.value)}
                  className="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">All Retailers</option>
                  <option value="walmart">Walmart</option>
                  <option value="target">Target</option>
                  <option value="lowes">Lowes</option>
                  <option value="vitacost">Vitacost</option>
                  <option value="kohls">Kohl's</option>
                </select>
                
                {/* Refresh Buttons */}
                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => fetchOpportunities(false)}
                    disabled={loading}
                    className="flex items-center space-x-2 px-3 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm"
                    title="Load from cache (instant load, up to 24h old)"
                  >
                    <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                    <span>Refresh</span>
                  </button>
                  
                  <button
                    onClick={() => fetchOpportunities(true)}
                    disabled={loading}
                    className={`flex items-center space-x-1 px-3 py-2 rounded-md disabled:opacity-50 disabled:cursor-not-allowed text-sm ${
                      stats?.cache_age_hours > 6 
                        ? 'bg-orange-600 text-white hover:bg-orange-700' 
                        : 'bg-gray-600 text-white hover:bg-gray-700'
                    }`}
                    title={`Get fresh data from source (${stats?.cache_age_hours > 6 ? 'recommended - data is ' + Math.round(stats.cache_age_hours) + 'h old' : 'slower but most current'})`}
                  >
                    <RefreshCw className={`h-3 w-3 ${loading ? 'animate-spin' : ''}`} />
                    <span>{stats?.cache_age_hours > 12 ? 'Update' : 'Force'}</span>
                  </button>
                </div>
              </div>
            </div>
            
            {lastUpdated && (
              <div className="mt-4 text-xs text-gray-500">
                Last updated: {lastUpdated.toLocaleString()}
              </div>
            )}
          </div>

          {/* Error State */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-md p-4">
              <div className="flex">
                <AlertTriangle className="h-5 w-5 text-red-400" />
                <div className="ml-3">
                  <h3 className="text-sm font-medium text-red-800">Error</h3>
                  <div className="mt-2 text-sm text-red-700">{error}</div>
                </div>
              </div>
            </div>
          )}

          {/* Loading State */}
          {loading && (
            <div className="bg-white rounded-lg shadow p-8">
              <div className="text-center">
                <RefreshCw className="h-8 w-8 text-blue-500 mx-auto mb-4 animate-spin" />
                <p className="text-gray-600">Analyzing email alerts...</p>
              </div>
            </div>
          )}


          {/* Opportunities Table */}
          {!loading && !error && (
            <div className="bg-white rounded-lg shadow p-6">
              <StandardTable
                data={opportunities || []}
                tableKey="discount-opportunities"
                columns={tableColumns}
                defaultColumnOrder={defaultColumnOrder}
                renderCell={renderTableCell}
                enableSearch={true}
                enableFilters={true}
                enableSorting={true}
                enableColumnReordering={true}
                enableColumnResetting={true}
                searchPlaceholder="Search opportunities by ASIN, product name, retailer..."
                searchFields={['asin', 'product_name', 'retailer', 'note']}
                filters={tableFilters}
                emptyIcon={Mail}
                emptyTitle="No Opportunities Found"
                emptyDescription="No discount leads found in recent email alerts from the last 7 days."
              />
            </div>
          )}
        </div>
      )}

      {activeTab === 'pricing' && (
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-center py-12">
            <Percent className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">Pricing Analysis</h3>
            <p className="text-gray-600">
              Detailed pricing analysis and competitor comparison.
            </p>
            <div className="mt-4 p-3 bg-yellow-50 rounded-md">
              <div className="flex items-center justify-center">
                <AlertTriangle className="h-5 w-5 text-yellow-500 mr-2" />
                <span className="text-sm text-yellow-800">Coming Soon</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'trends' && (
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-center py-12">
            <TrendingDown className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">Market Trends</h3>
            <p className="text-gray-600">
              Market trends and pricing patterns over time.
            </p>
            <div className="mt-4 p-3 bg-yellow-50 rounded-md">
              <div className="flex items-center justify-center">
                <AlertTriangle className="h-5 w-5 text-yellow-500 mr-2" />
                <span className="text-sm text-yellow-800">Coming Soon</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DiscountOpportunities;