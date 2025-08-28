import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  ShoppingCart, 
  Search, 
  Package, 
  AlertCircle, 
  CheckCircle,
  XCircle,
  ExternalLink,
  Download,
  RefreshCw,
  Upload,
  Eye
} from 'lucide-react';
import StandardTable from '../common/StandardTable';

const RetailerLeadAnalysis = () => {
  const [selectedWorksheet, setSelectedWorksheet] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingWorksheets, setLoadingWorksheets] = useState(true);
  const [error, setError] = useState('');
  const [analysis, setAnalysis] = useState(null);
  const [filterRecommendation, setFilterRecommendation] = useState('all');
  const [worksheets, setWorksheets] = useState([]);
  const [excludeKeywords, setExcludeKeywords] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [syncLoading, setSyncLoading] = useState(false);
  const [syncResults, setSyncResults] = useState(null);
  const [defaultWorksheetForNoSource, setDefaultWorksheetForNoSource] = useState('Unknown');
  const [targetWorksheets, setTargetWorksheets] = useState([]);

  useEffect(() => {
    fetchWorksheets();
    fetchTargetWorksheets();
  }, []);

  const fetchWorksheets = async () => {
    try {
      setLoadingWorksheets(true);
      const response = await axios.get('/api/retailer-leads/worksheets', { withCredentials: true });
      setWorksheets(response.data.worksheets || []);
    } catch (error) {
      setError('Failed to load available worksheets');
    } finally {
      setLoadingWorksheets(false);
    }
  };

  const fetchTargetWorksheets = async () => {
    try {
      const response = await axios.get('/api/retailer-leads/target-worksheets', { withCredentials: true });
      setTargetWorksheets(response.data.worksheets || []);
    } catch (error) {
      // Not critical - we'll use a default list
      setTargetWorksheets(['Unknown', 'Other', 'Misc', 'No Source']);
    }
  };

  const handleAnalyze = async () => {
    if (!selectedWorksheet) {
      setError('Please select a worksheet');
      return;
    }

    setLoading(true);
    setError('');
    setAnalysis(null);

    try {
      const response = await axios.post('/api/retailer-leads/analyze', {
        worksheet: selectedWorksheet
      }, { withCredentials: true });

      setAnalysis(response.data);
    } catch (error) {
      setError(error.response?.data?.message || error.response?.data?.error || 'Failed to analyze worksheet leads');
      
      // If worksheets are available, show them
      if (error.response?.data?.available_worksheets) {
        setError(prev => `${prev}\n\nAvailable worksheets: ${error.response.data.available_worksheets.join(', ')}`);
      }
    } finally {
      setLoading(false);
    }
  };

  const getRecommendationIcon = (recommendation) => {
    switch (recommendation) {
      case 'BUY - RESTOCK':
        return <AlertCircle className="h-5 w-5 text-red-500" />;
      case 'BUY - NEW':
        return <Package className="h-5 w-5 text-green-500" />;
      case 'MONITOR':
        return <Eye className="h-5 w-5 text-yellow-500" />;
      case 'SKIP':
        return <XCircle className="h-5 w-5 text-gray-400" />;
      default:
        return null;
    }
  };

  const getRecommendationBadge = (recommendation) => {
    const badges = {
      'BUY - RESTOCK': 'bg-red-100 text-red-800 border-red-200',
      'BUY - NEW': 'bg-green-100 text-green-800 border-green-200',
      'MONITOR': 'bg-yellow-100 text-yellow-800 border-yellow-200',
      'SKIP': 'bg-gray-100 text-gray-600 border-gray-200'
    };
    
    return badges[recommendation] || 'bg-gray-100 text-gray-600';
  };

  const filteredRecommendations = analysis?.recommendations?.filter(item => {
    // Filter by recommendation type
    let passesRecommendationFilter = true;
    if (filterRecommendation === 'all') passesRecommendationFilter = true;
    else if (filterRecommendation === 'buy') {
      passesRecommendationFilter = item.recommendation.startsWith('BUY');
    } else {
      passesRecommendationFilter = item.recommendation === filterRecommendation;
    }
    
    // Filter by search query (inclusive search - find matching items)
    let passesSearchFilter = true;
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      const searchableFields = [
        item.asin,
        item.product_name,
        item.source_link,
        item.recommendation,
        item.reason,
        item.retailer
      ];
      passesSearchFilter = searchableFields.some(field => 
        field && String(field).toLowerCase().includes(query)
      );
    }
    
    // Filter by exclude keywords (exclusive filter - remove matching items)
    let passesKeywordFilter = true;
    if (excludeKeywords.trim()) {
      const keywords = excludeKeywords.split(',').map(k => k.trim().toLowerCase()).filter(k => k);
      const productName = (item.product_name || '').toLowerCase();
      passesKeywordFilter = !keywords.some(keyword => productName.includes(keyword));
    }
    
    return passesRecommendationFilter && passesSearchFilter && passesKeywordFilter;
  }) || [];

  const handleSyncLeads = async () => {
    setSyncLoading(true);
    setSyncResults(null);
    setError('');

    try {
      // This now syncs leads from user's connected sheet to the target spreadsheet
      const response = await axios.post('/api/retailer-leads/sync-to-sheets', {
        default_worksheet: defaultWorksheetForNoSource
      }, { 
        withCredentials: true 
      });

      setSyncResults(response.data);
    } catch (error) {
      setError(error.response?.data?.message || error.response?.data?.error || 'Failed to sync leads to spreadsheet');
    } finally {
      setSyncLoading(false);
    }
  };

  // Table configuration for StandardTable
  const getTableColumns = () => {
    const columns = {
      asin: {
        key: 'asin',
        label: 'ASIN',
        sortKey: 'asin',
        draggable: true
      },
      source: {
        key: 'source',
        label: 'Source',
        sortKey: null,
        draggable: true
      },
      product_name: {
        key: 'product_name',
        label: 'Product Name',
        sortKey: 'product_name',
        draggable: true
      },
      recommendation: {
        key: 'recommendation',
        label: 'Recommendation',
        sortKey: 'recommendation',
        draggable: true
      },
      stock_info: {
        key: 'stock_info',
        label: 'Stock Info',
        sortKey: null,
        draggable: true
      },
      restock_priority: {
        key: 'restock_priority',
        label: 'Restock Priority',
        sortKey: null,
        draggable: true
      },
      recent_purchases: {
        key: 'recent_purchases',
        label: 'Recent Purchases',
        sortKey: 'recent_purchases',
        draggable: true
      }
    };

    // Add retailer column if showing all leads
    if (analysis?.worksheet === 'All Leads') {
      columns.retailer = {
        key: 'retailer',
        label: 'Retailer',
        sortKey: 'retailer',
        draggable: true
      };
    }

    return columns;
  };

  const getDefaultColumnOrder = () => {
    const baseOrder = ['asin', 'source', 'product_name', 'recommendation', 'stock_info', 'restock_priority', 'recent_purchases'];
    
    if (analysis?.worksheet === 'All Leads') {
      return ['asin', 'source', 'product_name', 'retailer', 'recommendation', 'stock_info', 'restock_priority', 'recent_purchases'];
    }
    
    return baseOrder;
  };

  const renderTableCell = (columnKey, item, index) => {
    switch (columnKey) {
      case 'asin':
        return (
          <td key={columnKey} className="px-3 py-3 whitespace-nowrap">
            <a
              href={`https://www.amazon.com/dp/${item.asin}`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm font-medium text-blue-600 hover:text-blue-800"
            >
              {item.asin}
            </a>
          </td>
        );
      
      case 'source':
        return (
          <td key={columnKey} className="px-3 py-3 text-center">
            {item.source_link ? (
              <a
                href={item.source_link}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:text-blue-800"
              >
                <ExternalLink className="h-4 w-4" />
              </a>
            ) : (
              <span className="text-gray-400">-</span>
            )}
          </td>
        );
      
      case 'product_name':
        return (
          <td key={columnKey} className="px-3 py-3">
            <div className="text-sm text-gray-900">
              {item.product_name ? (
                <span title={item.product_name}>
                  {item.product_name.length > 80 ? 
                    `${item.product_name.substring(0, 80)}...` : 
                    item.product_name
                  }
                  {!item.in_inventory && (
                    <span className="text-xs text-orange-500 ml-2">(New)</span>
                  )}
                </span>
              ) : (
                <span className="text-gray-400 italic">
                  {item.in_inventory ? 'Product name not available' : 'New Product (name not in sheet)'}
                </span>
              )}
            </div>
          </td>
        );
      
      case 'retailer':
        return (
          <td key={columnKey} className="px-3 py-3 whitespace-nowrap">
            <span className="text-sm text-gray-600">{item.retailer}</span>
          </td>
        );
      
      case 'recommendation':
        return (
          <td key={columnKey} className="px-3 py-3 whitespace-nowrap">
            <div className="flex items-center">
              {getRecommendationIcon(item.recommendation)}
              <span className={`ml-2 px-2 py-1 text-xs font-medium rounded-full border ${getRecommendationBadge(item.recommendation)}`}>
                {item.recommendation}
              </span>
            </div>
          </td>
        );
      
      case 'stock_info':
        return (
          <td key={columnKey} className="px-3 py-3 text-center">
            {item.inventory_details ? (
              <div className="text-sm">
                <div className="font-medium">{item.inventory_details.current_stock} units</div>
                <div className="text-xs text-gray-500">
                  Need: {item.inventory_details.suggested_quantity}
                </div>
              </div>
            ) : (
              <span className="text-sm text-gray-400">N/A</span>
            )}
          </td>
        );
      
      case 'restock_priority':
        return (
          <td key={columnKey} className="px-3 py-3 text-center">
            {item.inventory_details ? (
              <div className="text-sm">
                <div className="font-medium">{item.inventory_details.units_per_day.toFixed(1)}/day</div>
                <div className="text-xs text-gray-500">
                  {item.inventory_details.days_of_stock} days left
                </div>
              </div>
            ) : (
              <span className="text-sm text-gray-400">-</span>
            )}
          </td>
        );
      
      case 'recent_purchases':
        return (
          <td key={columnKey} className="px-3 py-3 text-center">
            <div className="text-sm">
              <div className="font-medium">{item.recent_purchases || 0}</div>
              <div className="text-xs text-gray-500">last 2 months</div>
            </div>
          </td>
        );
      
      default:
        return <td key={columnKey}></td>;
    }
  };

  const exportToCSV = () => {
    if (!analysis?.recommendations) return;

    const headers = ['ASIN', 'Source Link', 'Product Name', 'Retailer', 'Recommendation', 'Current Stock', 'Suggested Qty', 'Units/Day', 'Days of Stock', 'Recent Purchases'];
    const rows = analysis.recommendations.map(item => [
      item.asin,
      item.source_link || '',
      item.product_name || '',
      item.retailer || '',
      item.recommendation,
      item.inventory_details?.current_stock || '',
      item.inventory_details?.suggested_quantity || '',
      item.inventory_details?.units_per_day?.toFixed(2) || '',
      item.inventory_details?.days_of_stock || '',
      item.recent_purchases || 0
    ]);

    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.map(cell => `"${cell}"`).join(','))
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${selectedWorksheet.replace(/[^a-z0-9]/gi, '_')}_lead_analysis_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
  };


  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center space-x-3">
        <ShoppingCart className="h-8 w-8 text-builders-500" />
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Lead Analysis</h1>
          <p className="text-gray-600">Analyze retailer leads and get buying recommendations</p>
        </div>
      </div>

      {/* Main Content */}
        <div className="bg-white rounded-lg shadow p-6">
          <div className="mb-6">
            <h2 className="text-xl font-bold text-gray-900">
              Retailer Lead Analysis
            </h2>
            <p className="text-sm text-gray-600 mt-1">
              Analyze all leads from a specific worksheet and get buying recommendations
            </p>
          </div>


        <div className="flex items-end space-x-4">
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Select Worksheet
            </label>
            {loadingWorksheets ? (
              <div className="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-50">
                <div className="flex items-center">
                  <RefreshCw className="h-4 w-4 mr-2 animate-spin text-gray-400" />
                  <span className="text-sm text-gray-500">Loading worksheets...</span>
                </div>
              </div>
            ) : (
              <select
                value={selectedWorksheet}
                onChange={(e) => setSelectedWorksheet(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-builders-500"
              >
                <option value="">Choose a worksheet...</option>
                {worksheets.map(worksheet => (
                  <option key={worksheet} value={worksheet}>
                    {worksheet}
                  </option>
                ))}
              </select>
            )}
          </div>
          <button
            onClick={handleAnalyze}
            disabled={!selectedWorksheet || loading || loadingWorksheets}
            className="px-4 py-2 bg-builders-600 text-white rounded-md hover:bg-builders-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
          >
            {loading ? (
              <>
                <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                Analyzing...
              </>
            ) : (
              <>
                <Search className="h-4 w-4 mr-2" />
                Analyze Leads
              </>
            )}
          </button>
        </div>

        {error && (
          <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-md">
            <div className="flex items-start">
              <AlertCircle className="h-5 w-5 text-red-500 mt-0.5 mr-2" />
              <div className="text-sm text-red-800 whitespace-pre-line">{error}</div>
            </div>
          </div>
        )}

        {syncResults && (
          <div className="mt-4 p-3 bg-green-50 border border-green-200 rounded-md">
            <div className="flex items-center">
              <CheckCircle className="h-4 w-4 text-green-500 mr-2" />
              <div className="text-sm text-green-800">
                <span className="font-medium">Sync completed!</span> {syncResults.added || 0} leads added
                {syncResults.already_existed > 0 && <span>, {syncResults.already_existed} skipped</span>}
                {syncResults.errors > 0 && <span className="text-red-600">, {syncResults.errors} errors</span>}
              </div>
            </div>
          </div>
        )}

        {analysis && (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            <div className="bg-white rounded-lg shadow p-4">
              <div className="text-sm font-medium text-gray-600">Total Leads</div>
              <div className="text-2xl font-bold text-gray-900">{analysis.summary.total_leads}</div>
            </div>
            <div className="bg-red-50 rounded-lg shadow p-4 border border-red-200">
              <div className="text-sm font-medium text-red-600">Buy - Restock</div>
              <div className="text-2xl font-bold text-red-900">{analysis.summary.buy_restock}</div>
            </div>
            <div className="bg-green-50 rounded-lg shadow p-4 border border-green-200">
              <div className="text-sm font-medium text-green-600">Buy - New</div>
              <div className="text-2xl font-bold text-green-900">{analysis.summary.buy_new}</div>
            </div>
            <div className="bg-yellow-50 rounded-lg shadow p-4 border border-yellow-200">
              <div className="text-sm font-medium text-yellow-600">Monitor</div>
              <div className="text-2xl font-bold text-yellow-900">{analysis.summary.monitor}</div>
            </div>
            <div className="bg-gray-50 rounded-lg shadow p-4 border border-gray-200">
              <div className="text-sm font-medium text-gray-600">Skip</div>
              <div className="text-2xl font-bold text-gray-900">{analysis.summary.skip}</div>
            </div>
          </div>


          {/* Results Table */}
          <div className="bg-white rounded-lg shadow">
            <div className="px-6 py-4 border-b border-gray-200">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">
                    Analysis Results - {analysis.worksheet}
                  </h3>
                  <p className="text-sm text-gray-600 mt-1">
                    Analyzed at {new Date(analysis.analyzed_at).toLocaleString()}
                  </p>
                </div>
                <div className="flex items-center space-x-4">
                  {/* Search Input */}
                  <div className="flex items-center space-x-2">
                    <input
                      type="text"
                      placeholder="Search products (ASIN, name, retailer...)"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="px-3 py-1 border border-gray-300 rounded-md text-sm w-64"
                      title="Search for products by ASIN, product name, retailer, or recommendation"
                    />
                  </div>
                  {/* Exclude Keywords Input */}
                  <div className="flex items-center space-x-2">
                    <input
                      type="text"
                      placeholder="Exclude keywords (e.g., Champion, Nike)"
                      value={excludeKeywords}
                      onChange={(e) => setExcludeKeywords(e.target.value)}
                      className="px-3 py-1 border border-gray-300 rounded-md text-sm w-64"
                      title="Enter keywords separated by commas to filter out products containing these words"
                    />
                    <select
                      value={filterRecommendation}
                      onChange={(e) => setFilterRecommendation(e.target.value)}
                      className="px-3 py-1 border border-gray-300 rounded-md text-sm"
                    >
                      <option value="all">All Recommendations</option>
                      <option value="buy">Buy (All)</option>
                      <option value="BUY - RESTOCK">Buy - Restock Only</option>
                      <option value="BUY - NEW">Buy - New Only</option>
                      <option value="MONITOR">Monitor Only</option>
                      <option value="SKIP">Skip Only</option>
                    </select>
                  </div>
                  <div className="flex items-center space-x-2">
                    <button
                      onClick={handleSyncLeads}
                      disabled={syncLoading}
                      className="px-2 py-1 bg-green-100 text-green-700 rounded text-xs hover:bg-green-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
                      title="Sync all leads to sheets"
                    >
                      {syncLoading ? (
                        <>
                          <RefreshCw className="h-3 w-3 mr-1 animate-spin" />
                          Syncing
                        </>
                      ) : (
                        <>
                          <Upload className="h-3 w-3 mr-1" />
                          Sync
                        </>
                      )}
                    </button>
                    <button
                      onClick={exportToCSV}
                      className="px-2 py-1 bg-gray-100 text-gray-700 rounded text-xs hover:bg-gray-200 flex items-center"
                    >
                      <Download className="h-3 w-3 mr-1" />
                      Export
                    </button>
                  </div>
                </div>
              </div>
            </div>

            <StandardTable
              data={filteredRecommendations || []}
              tableKey="lead-analysis"
              columns={getTableColumns()}
              defaultColumnOrder={getDefaultColumnOrder()}
              renderCell={renderTableCell}
              enableSearch={false}  // Search handled in parent component
              enableFilters={false}  // Filters handled in parent component
              enableSorting={true}
              enableColumnReordering={true}
              enableColumnResetting={true}
              emptyIcon={Package}
              emptyTitle="No Recommendations"
              emptyDescription="No recommendations found matching your filter criteria."
            />
            
            {analysis?.recommendations && filteredRecommendations.length !== analysis.recommendations.length && (
              <div className="px-6 py-3 bg-blue-50 border-t border-blue-200">
                <div className="text-sm text-blue-800">
                  Showing {filteredRecommendations.length} of {analysis.recommendations.length} recommendations
                  {searchQuery.trim() && (
                    <span> (searched for: "{searchQuery}")</span>
                  )}
                  {excludeKeywords.trim() && (
                    <span> (excluded: {excludeKeywords})</span>
                  )}
                </div>
              </div>
            )}
          </div>
        </>
        )}
        </div>
    </div>
  );
};

export default RetailerLeadAnalysis;