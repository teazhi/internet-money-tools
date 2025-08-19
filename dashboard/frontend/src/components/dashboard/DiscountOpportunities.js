import React, { useState, useEffect } from 'react';
import { 
  Target, 
  TrendingDown, 
  BarChart3,
  Percent,
  AlertTriangle,
  ExternalLink,
  Package,
  Clock,
  TrendingUp,
  RefreshCw,
  Mail,
  ShoppingCart,
  Calendar
} from 'lucide-react';
import axios from 'axios';

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

  const fetchOpportunities = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await axios.post('/api/discount-opportunities/analyze', {
        retailer: retailerFilter
      }, { withCredentials: true });
      
      console.log('Discount opportunities response:', response.data);
      console.log('Opportunities count:', response.data.opportunities?.length);
      console.log('First opportunity:', response.data.opportunities?.[0]);
      
      setOpportunities(response.data.opportunities || []);
      setStats({
        totalAlertsProcessed: response.data.total_alerts_processed,
        matchedProducts: response.data.matched_products,
        restockNeededCount: response.data.restock_needed_count,
        notNeededCount: response.data.not_needed_count,
        notTrackedCount: response.data.not_tracked_count,
        message: response.data.message
      });
      setLastUpdated(new Date());
      
    } catch (error) {
      console.error('Error fetching opportunities:', error);
      setError(error.response?.data?.message || 'Failed to fetch discount opportunities');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'opportunities') {
      fetchOpportunities();
    }
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
    const now = new Date();
    const alertTime = new Date(timestamp);
    const diffHours = Math.floor((now - alertTime) / (1000 * 60 * 60));
    
    if (diffHours < 1) return 'Just now';
    if (diffHours === 1) return '1 hour ago';
    if (diffHours < 24) return `${diffHours} hours ago`;
    
    const diffDays = Math.floor(diffHours / 24);
    if (diffDays === 1) return '1 day ago';
    return `${diffDays} days ago`;
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
                    {stats.message} • {stats.totalAlertsProcessed} emails processed
                    {stats.restockNeededCount !== undefined && (
                      <div className="mt-1">
                        Breakdown: {stats.restockNeededCount} need restocking, {stats.notNeededCount} not needed, {stats.notTrackedCount} not tracked
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
                
                {/* Refresh Button */}
                <button
                  onClick={fetchOpportunities}
                  disabled={loading}
                  className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm"
                >
                  <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                  <span>Refresh</span>
                </button>
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

          {/* Debug info */}
          {!loading && !error && opportunities && (
            <div className="text-xs text-gray-500 bg-gray-50 p-2 rounded mb-2">
              Debug: {opportunities.length} opportunities loaded
            </div>
          )}

          {/* Opportunities List */}
          {!loading && !error && (
            <div className="bg-white rounded-lg shadow">
              {!opportunities || opportunities.length === 0 ? (
                <div className="p-8 text-center">
                  <Mail className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-gray-900 mb-2">No Opportunities Found</h3>
                  <p className="text-gray-600">
                    No discount leads found in recent email alerts from the last 7 days.
                  </p>
                </div>
              ) : (
                <div className="overflow-hidden">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Product
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Retailer
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Status
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Inventory Status
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Alert Info
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Actions
                        </th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {opportunities.map((opportunity, index) => (
                        <tr key={`${opportunity.asin}-${index}`} className="hover:bg-gray-50">
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className="flex items-center">
                              <div className="flex-shrink-0 h-10 w-10">
                                <div className="h-10 w-10 rounded-lg bg-gray-200 flex items-center justify-center">
                                  <Package className="h-5 w-5 text-gray-600" />
                                </div>
                              </div>
                              <div className="ml-4">
                                <div className="text-sm font-medium text-gray-900">
                                  {opportunity.product_name || opportunity.asin}
                                </div>
                                <div className="text-sm text-gray-500">
                                  ASIN: {opportunity.asin}
                                </div>
                                {opportunity.note && (
                                  <div className="text-xs text-blue-600 mt-1">
                                    {opportunity.note}
                                  </div>
                                )}
                              </div>
                            </div>
                          </td>
                          
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className="text-sm text-gray-900">{opportunity.retailer}</div>
                            {opportunity.promo_message && (
                              <div className="text-xs text-green-600 mt-1">
                                {opportunity.promo_message}
                              </div>
                            )}
                          </td>
                          
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(opportunity.status)}`}>
                              {opportunity.status}
                            </div>
                          </td>
                          
                          <td className="px-6 py-4 whitespace-nowrap">
                            {opportunity.status === 'Not Tracked' ? (
                              <div className="text-sm text-gray-500 italic">
                                Product not in inventory
                              </div>
                            ) : (
                              <>
                                <div className="text-sm text-gray-900">
                                  <div className="flex items-center space-x-2">
                                    <Package className="h-4 w-4 text-gray-500" />
                                    <span>{opportunity.current_stock} units</span>
                                  </div>
                                  {opportunity.needs_restock && (
                                    <div className="text-xs text-gray-500 mt-1">
                                      Need: {opportunity.suggested_quantity} • {typeof opportunity.days_left === 'number' ? opportunity.days_left.toFixed(1) : 'N/A'} days left
                                    </div>
                                  )}
                                  {opportunity.velocity > 0 && (
                                    <div className="text-xs text-gray-500">
                                      Velocity: {opportunity.velocity.toFixed(2)}/day
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
                          
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className="text-sm text-gray-900">
                              <div className="flex items-center space-x-1">
                                <Clock className="h-4 w-4 text-gray-500" />
                                <span>{formatTimeAgo(opportunity.alert_time)}</span>
                              </div>
                            </div>
                          </td>
                          
                          <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
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
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
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