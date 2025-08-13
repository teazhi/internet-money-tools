import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  ShoppingCart, 
  Search, 
  Package, 
  AlertCircle, 
  TrendingUp, 
  Eye,
  CheckCircle,
  XCircle,
  ExternalLink,
  Download,
  RefreshCw
} from 'lucide-react';

const RetailerLeadAnalysis = () => {
  const [activeTab, setActiveTab] = useState('analysis');
  const [selectedWorksheet, setSelectedWorksheet] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingWorksheets, setLoadingWorksheets] = useState(true);
  const [error, setError] = useState('');
  const [analysis, setAnalysis] = useState(null);
  const [filterRecommendation, setFilterRecommendation] = useState('all');
  const [worksheets, setWorksheets] = useState([]);
  const [excludeKeywords, setExcludeKeywords] = useState('');

  useEffect(() => {
    fetchWorksheets();
  }, []);

  const fetchWorksheets = async () => {
    try {
      setLoadingWorksheets(true);
      const response = await axios.get('/api/retailer-leads/worksheets', { withCredentials: true });
      setWorksheets(response.data.worksheets || []);
    } catch (error) {
      console.error('Failed to fetch worksheets:', error);
      setError('Failed to load available worksheets');
    } finally {
      setLoadingWorksheets(false);
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
      console.error('Analysis error:', error);
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
    
    // Filter by exclude keywords
    let passesKeywordFilter = true;
    if (excludeKeywords.trim()) {
      const keywords = excludeKeywords.split(',').map(k => k.trim().toLowerCase()).filter(k => k);
      const productName = (item.product_name || '').toLowerCase();
      passesKeywordFilter = !keywords.some(keyword => productName.includes(keyword));
    }
    
    return passesRecommendationFilter && passesKeywordFilter;
  }) || [];

  const exportToCSV = () => {
    if (!analysis?.recommendations) return;

    const headers = ['ASIN', 'Product Name', 'Retailer', 'Recommendation', 'Reason', 'Current Stock', 'Suggested Qty', 'Units/Day', 'Days of Stock', 'Recent Purchases', 'Source Link'];
    const rows = analysis.recommendations.map(item => [
      item.asin,
      item.product_name || '',
      item.retailer || '',
      item.recommendation,
      item.reason,
      item.inventory_details?.current_stock || '',
      item.inventory_details?.suggested_quantity || '',
      item.inventory_details?.units_per_day?.toFixed(2) || '',
      item.inventory_details?.days_of_stock || '',
      item.recent_purchases || 0,
      item.source_link || ''
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

  const tabs = [
    { id: 'analysis', name: 'Lead Analysis', icon: ShoppingCart },
    { id: 'reports', name: 'Reports', icon: TrendingUp },
    { id: 'history', name: 'History', icon: Eye }
  ];

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
                    ? 'border-builders-500 text-builders-600'
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
      {activeTab === 'analysis' && (
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-xl font-bold text-gray-900">
                Retailer Lead Analysis
              </h2>
              <p className="text-sm text-gray-600 mt-1">
                Analyze all leads from a specific worksheet and get buying recommendations
              </p>
            </div>
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
                  <button
                    onClick={exportToCSV}
                    className="px-3 py-1 bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 flex items-center text-sm"
                  >
                    <Download className="h-4 w-4 mr-1" />
                    Export CSV
                  </button>
                </div>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      ASIN
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Product Name
                    </th>
                    {analysis.worksheet === 'All Leads' && (
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Retailer
                      </th>
                    )}
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Recommendation
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Reason
                    </th>
                    <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Stock Info
                    </th>
                    <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Restock Priority
                    </th>
                    <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Recent Purchases
                    </th>
                    <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Source
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {filteredRecommendations.map((item, index) => (
                    <tr key={`${item.asin}-${index}`} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center">
                          <a
                            href={`https://www.amazon.com/dp/${item.asin}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-sm font-medium text-blue-600 hover:text-blue-800"
                          >
                            {item.asin}
                          </a>
                        </div>
                      </td>
                      <td className="px-6 py-4">
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
                      {analysis.worksheet === 'All Leads' && (
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className="text-sm text-gray-600">{item.retailer}</span>
                        </td>
                      )}
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center">
                          {getRecommendationIcon(item.recommendation)}
                          <span className={`ml-2 px-2 py-1 text-xs font-medium rounded-full border ${getRecommendationBadge(item.recommendation)}`}>
                            {item.recommendation}
                          </span>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="text-sm text-gray-900">{item.reason}</div>
                      </td>
                      <td className="px-6 py-4 text-center">
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
                      <td className="px-6 py-4 text-center">
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
                      <td className="px-6 py-4 text-center">
                        <div className="text-sm">
                          <div className="font-medium">{item.recent_purchases || 0}</div>
                          <div className="text-xs text-gray-500">last 2 months</div>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-center">
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
                    </tr>
                  ))}
                </tbody>
              </table>
              
              {filteredRecommendations.length === 0 && (
                <div className="text-center py-8 text-gray-500">
                  No recommendations found matching your filter criteria.
                </div>
              )}
              
              {analysis?.recommendations && filteredRecommendations.length !== analysis.recommendations.length && (
                <div className="px-6 py-3 bg-blue-50 border-t border-blue-200">
                  <div className="text-sm text-blue-800">
                    Showing {filteredRecommendations.length} of {analysis.recommendations.length} recommendations
                    {excludeKeywords.trim() && (
                      <span> (filtered out products containing: {excludeKeywords})</span>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </>
        )}
        </div>
      )}

      {/* Reports Tab */}
      {activeTab === 'reports' && (
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-center py-12">
            <TrendingUp className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">Reports Coming Soon</h3>
            <p className="text-gray-600">
              Detailed reports and analytics will be available here.
            </p>
          </div>
        </div>
      )}

      {/* History Tab */}
      {activeTab === 'history' && (
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-center py-12">
            <Eye className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">History Coming Soon</h3>
            <p className="text-gray-600">
              Analysis history and previous results will be available here.
            </p>
          </div>
        </div>
      )}
    </div>
  );
};

export default RetailerLeadAnalysis;