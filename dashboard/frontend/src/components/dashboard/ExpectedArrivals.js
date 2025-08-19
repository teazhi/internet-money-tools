import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  Package, 
  RefreshCw, 
  AlertCircle, 
  Calendar,
  DollarSign,
  ExternalLink,
  Download,
  Plus
} from 'lucide-react';

const ExpectedArrivals = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [missingListings, setMissingListings] = useState([]);
  const [summary, setSummary] = useState({ total_items: 0, total_quantity: 0, total_cost: 0 });
  const [analyzedAt, setAnalyzedAt] = useState('');
  const [analysisScope, setAnalysisScope] = useState('all'); // 'all' or 'current_month'

  useEffect(() => {
    fetchMissingListings();
  }, []);

  const fetchMissingListings = async (scope = analysisScope) => {
    setLoading(true);
    setError('');
    
    try {
      const params = new URLSearchParams();
      if (scope) {
        params.append('scope', scope);
      }
      
      const response = await axios.get(`/api/expected-arrivals?${params.toString()}`, { withCredentials: true });
      
      if (response.data.missing_listings) {
        setMissingListings(response.data.missing_listings);
        setSummary(response.data.summary);
        setAnalyzedAt(response.data.analyzed_at);
      } else {
        setError(response.data.message || 'No missing listings found');
      }
    } catch (error) {
      console.error('Missing listings error:', error);
      setError(error.response?.data?.error || 'Failed to fetch missing listings data');
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'Unknown';
    return new Date(dateString).toLocaleDateString();
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(amount);
  };

  const createListing = (asin) => {
    const listingUrl = `https://sellercentral.amazon.com/abis/listing/syh/ref=udp_sdp_sell?_encoding=UTF8&mons_sel_best_mkid=amzn1.mp.o.ATVPDKIKX0DER&ld=AMZUDP&coliid=&asin=${asin}&colid=&qid=&sr=`;
    window.open(listingUrl, '_blank', 'noopener,noreferrer');
  };

  const exportToCSV = () => {
    if (!missingListings.length) return;

    const headers = ['ASIN', 'Product Name', 'Qty Purchased', 'Purchase Count', 'Last Purchase', 'Avg COGS', 'Total Cost', 'Source Worksheets', 'Status'];
    const rows = missingListings.map(item => [
      item.asin,
      item.product_name || '',
      item.quantity_purchased,
      item.purchase_count,
      formatDate(item.last_purchase_date),
      item.avg_cogs?.toFixed(2) || '0.00',
      item.total_cost?.toFixed(2) || '0.00',
      item.source_worksheets?.join('; ') || '',
      item.status || 'No Amazon listing created'
    ]);

    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.map(cell => `"${cell}"`).join(','))
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `missing_listings_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-xl font-bold text-gray-900 flex items-center">
              <Package className="h-6 w-6 mr-2 text-blue-500" />
              Missing Listings
            </h2>
            <p className="text-sm text-gray-600 mt-1">
              Items you purchased but haven't created Amazon listings for yet
            </p>
          </div>
          <div className="flex items-center space-x-3">
            <select
              value={analysisScope}
              onChange={(e) => setAnalysisScope(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
              disabled={loading}
            >
              <option value="all">All Sheets (Last 2 months)</option>
              <option value="current_month">Current Month Sheet Only</option>
            </select>
            <button
              onClick={() => fetchMissingListings(analysisScope)}
              disabled={loading}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
            >
              {loading ? (
                <>
                  <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                  Analyzing...
                </>
              ) : (
                <>
                  <RefreshCw className="h-4 w-4 mr-2" />
                  Check for Missing Listings
                </>
              )}
            </button>
          </div>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-md">
            <div className="flex items-start">
              <AlertCircle className="h-5 w-5 text-red-500 mt-0.5 mr-2" />
              <div className="text-sm text-red-800">{error}</div>
            </div>
          </div>
        )}
      </div>

      {missingListings.length > 0 && (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center">
                <Package className="h-8 w-8 text-red-500" />
                <div className="ml-4">
                  <div className="text-sm font-medium text-gray-600">Missing Listings</div>
                  <div className="text-2xl font-bold text-gray-900">{summary.total_items}</div>
                </div>
              </div>
            </div>
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center">
                <Calendar className="h-8 w-8 text-green-500" />
                <div className="ml-4">
                  <div className="text-sm font-medium text-gray-600">Total Quantity</div>
                  <div className="text-2xl font-bold text-gray-900">{summary.total_quantity}</div>
                </div>
              </div>
            </div>
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center">
                <DollarSign className="h-8 w-8 text-purple-500" />
                <div className="ml-4">
                  <div className="text-sm font-medium text-gray-600">Unlisted Inventory Value</div>
                  <div className="text-2xl font-bold text-gray-900">{formatCurrency(summary.total_cost)}</div>
                </div>
              </div>
            </div>
          </div>

          {/* Missing Listings Table */}
          <div className="bg-white rounded-lg shadow">
            <div className="px-6 py-4 border-b border-gray-200">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">
                    Items Needing Amazon Listings
                  </h3>
                  {analyzedAt && (
                    <p className="text-sm text-gray-600 mt-1">
                      Analyzed at {new Date(analyzedAt).toLocaleString()}
                    </p>
                  )}
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
                    <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Qty Purchased
                    </th>
                    <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Purchase Count
                    </th>
                    <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Last Purchase
                    </th>
                    <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Avg COGS
                    </th>
                    <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Total Cost
                    </th>
                    <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Sources
                    </th>
                    <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {missingListings.map((item, index) => (
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
                          <ExternalLink className="h-3 w-3 ml-1 text-gray-400" />
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="text-sm text-gray-900">
                          {item.product_name ? (
                            <span title={item.product_name}>
                              {item.product_name.length > 60 ? 
                                `${item.product_name.substring(0, 60)}...` : 
                                item.product_name
                              }
                            </span>
                          ) : (
                            <span className="text-gray-400 italic">No name available</span>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4 text-center">
                        <span className="text-sm font-medium text-gray-900">
                          {item.quantity_purchased}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-center">
                        <span className="text-sm text-gray-600">
                          {item.purchase_count} {item.purchase_count === 1 ? 'purchase' : 'purchases'}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-center">
                        <span className="text-sm text-gray-600">
                          {formatDate(item.last_purchase_date)}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-center">
                        <span className="text-sm font-medium text-gray-900">
                          {formatCurrency(item.avg_cogs)}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-center">
                        <span className="text-sm font-bold text-green-600">
                          {formatCurrency(item.total_cost)}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-center">
                        <div className="text-sm text-gray-600">
                          {item.source_worksheets && item.source_worksheets.length > 0 ? (
                            <span title={item.source_worksheets.join(', ')}>
                              {item.source_worksheets.length === 1 
                                ? item.source_worksheets[0] 
                                : `${item.source_worksheets.length} sources`}
                            </span>
                          ) : (
                            <span className="text-gray-400">-</span>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4 text-center">
                        <button
                          onClick={() => createListing(item.asin)}
                          className="inline-flex items-center px-3 py-1 bg-green-600 hover:bg-green-700 text-white text-sm font-medium rounded-md transition-colors duration-200"
                          title={`Create listing for ${item.asin}`}
                        >
                          <Plus className="h-4 w-4 mr-1" />
                          Create Listing
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {!loading && missingListings.length === 0 && !error && (
        <div className="bg-white rounded-lg shadow p-12">
          <div className="text-center">
            <Package className="mx-auto h-12 w-12 text-green-400" />
            <h3 className="mt-4 text-lg font-medium text-gray-900">All Listings Created!</h3>
            <p className="mt-2 text-sm text-gray-500">
              All items purchased in the last 2 months have Amazon listings created.
            </p>
          </div>
        </div>
      )}
    </div>
  );
};

export default ExpectedArrivals;