import React, { useState, useEffect } from 'react';
import { Sparkles, Package, TrendingUp, AlertCircle, Loader, Clock } from 'lucide-react';
import axios from 'axios';

const AIRestockPage = () => {
  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [leadTime, setLeadTime] = useState(90);
  const [analysisPeriod, setAnalysisPeriod] = useState('');

  useEffect(() => {
    fetchRestockRecommendations();
  }, []);

  const fetchRestockRecommendations = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await axios.get('/api/analytics/restock-ai', {
        withCredentials: true
      });
      setRecommendations(response.data.recommendations || []);
      setLeadTime(response.data.lead_time_days || 90);
      setAnalysisPeriod(response.data.analysis_period || '');
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to fetch restocking recommendations');
    } finally {
      setLoading(false);
    }
  };

  const getUrgencyColor = (urgency) => {
    switch(urgency?.toLowerCase()) {
      case 'critical': return 'text-red-600 bg-red-50 border-red-200';
      case 'high': return 'text-orange-600 bg-orange-50 border-orange-200';
      case 'medium': return 'text-yellow-600 bg-yellow-50 border-yellow-200';
      case 'low': return 'text-green-600 bg-green-50 border-green-200';
      default: return 'text-gray-600 bg-gray-50 border-gray-200';
    }
  };

  const getUrgencyBadgeColor = (urgency) => {
    switch(urgency?.toLowerCase()) {
      case 'critical': return 'bg-red-100 text-red-800';
      case 'high': return 'bg-orange-100 text-orange-800';
      case 'medium': return 'bg-yellow-100 text-yellow-800';
      case 'low': return 'bg-green-100 text-green-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-indigo-600 to-blue-600 rounded-lg shadow-sm p-6 text-white">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center space-x-3 mb-2">
              <Sparkles className="h-8 w-8" />
              <h1 className="text-2xl font-bold">AI-Powered Restocking</h1>
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-indigo-100 text-indigo-800">
                Beta
              </span>
            </div>
            <p className="text-indigo-100">
              Smart inventory predictions to optimize your restocking
            </p>
          </div>
          
          <div className="text-right">
            <div className="flex items-center space-x-2 text-sm text-indigo-200">
              <Clock className="h-4 w-4" />
              <span>Lead Time: {leadTime} days</span>
            </div>
            {analysisPeriod && (
              <p className="text-xs text-indigo-200 mt-1">
                Analysis Period: {analysisPeriod}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Main Content */}
      {loading ? (
        <div className="bg-white border border-gray-200 rounded-lg p-12">
          <div className="text-center">
            <Loader className="h-12 w-12 animate-spin text-indigo-500 mx-auto mb-4" />
            <p className="text-gray-500">Calculating optimal restock quantities...</p>
            <p className="text-sm text-gray-400 mt-2">Analyzing sales velocity and inventory levels</p>
          </div>
        </div>
      ) : error ? (
        <div className="bg-red-50 border border-red-200 rounded-lg p-6">
          <div className="flex items-start space-x-3">
            <AlertCircle className="h-5 w-5 text-red-500 mt-0.5 flex-shrink-0" />
            <div>
              <h3 className="text-sm font-medium text-red-800">Error Loading Recommendations</h3>
              <p className="text-sm text-red-700 mt-1">{error}</p>
              <button
                onClick={fetchRestockRecommendations}
                className="mt-3 px-3 py-1.5 bg-red-100 hover:bg-red-200 text-red-800 text-sm font-medium rounded-md transition-colors"
              >
                Try Again
              </button>
            </div>
          </div>
        </div>
      ) : recommendations.length > 0 ? (
        <div className="space-y-4">
          {/* Summary Stats */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-white border border-gray-200 rounded-lg p-4">
              <div className="flex items-center space-x-3">
                <Package className="h-8 w-8 text-indigo-500" />
                <div>
                  <p className="text-sm text-gray-500">Total Products</p>
                  <p className="text-2xl font-semibold text-gray-900">{recommendations.length}</p>
                </div>
              </div>
            </div>
            
            <div className="bg-white border border-gray-200 rounded-lg p-4">
              <div className="flex items-center space-x-3">
                <AlertCircle className="h-8 w-8 text-red-500" />
                <div>
                  <p className="text-sm text-gray-500">Critical Items</p>
                  <p className="text-2xl font-semibold text-gray-900">
                    {recommendations.filter(r => r.urgency?.toLowerCase() === 'critical').length}
                  </p>
                </div>
              </div>
            </div>
            
            <div className="bg-white border border-gray-200 rounded-lg p-4">
              <div className="flex items-center space-x-3">
                <TrendingUp className="h-8 w-8 text-orange-500" />
                <div>
                  <p className="text-sm text-gray-500">High Priority</p>
                  <p className="text-2xl font-semibold text-gray-900">
                    {recommendations.filter(r => r.urgency?.toLowerCase() === 'high').length}
                  </p>
                </div>
              </div>
            </div>
            
            <div className="bg-white border border-gray-200 rounded-lg p-4">
              <div className="flex items-center space-x-3">
                <Clock className="h-8 w-8 text-blue-500" />
                <div>
                  <p className="text-sm text-gray-500">Avg. Days Left</p>
                  <p className="text-2xl font-semibold text-gray-900">
                    {Math.round(recommendations.reduce((sum, r) => sum + (r.estimated_runout_days || 0), 0) / recommendations.length)}
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Recommendations List */}
          <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
            <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900">Restocking Recommendations</h2>
            </div>
            
            <div className="divide-y divide-gray-200">
              {recommendations
                .sort((a, b) => {
                  // Sort by urgency: critical > high > medium > low
                  const urgencyOrder = { critical: 0, high: 1, medium: 2, low: 3 };
                  return urgencyOrder[a.urgency?.toLowerCase()] - urgencyOrder[b.urgency?.toLowerCase()];
                })
                .map((rec, index) => (
                <div key={index} className={`p-6 hover:bg-gray-50 transition-colors ${getUrgencyColor(rec.urgency)}`}>
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center space-x-3 mb-2">
                        <h3 className="text-sm font-medium text-gray-900">{rec.product_name || rec.asin}</h3>
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getUrgencyBadgeColor(rec.urgency)}`}>
                          {rec.urgency}
                        </span>
                      </div>
                      
                      <div className="flex items-center space-x-4 text-sm text-gray-600 mb-3">
                        <span className="font-mono">{rec.asin}</span>
                        {rec.estimated_runout_days && (
                          <span className="flex items-center space-x-1">
                            <Clock className="h-4 w-4" />
                            <span>{rec.estimated_runout_days} days until stockout</span>
                          </span>
                        )}
                      </div>
                      
                      <p className="text-sm text-gray-700 mb-3">{rec.reasoning}</p>
                      
                      <div className="flex items-center space-x-4">
                        <div className="bg-white rounded-md border border-gray-300 px-3 py-2">
                          <p className="text-xs text-gray-500">Recommended Order</p>
                          <p className="text-lg font-semibold text-gray-900">{rec.recommended_order_quantity} units</p>
                        </div>
                        
                        <a 
                          href={`https://www.amazon.com/dp/${rec.asin}`} 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="text-sm text-indigo-600 hover:text-indigo-800 font-medium"
                        >
                          View on Amazon →
                        </a>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Tips */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
            <h3 className="text-sm font-medium text-blue-900 mb-3">💡 Pro Tips</h3>
            <ul className="space-y-2 text-sm text-blue-800">
              <li className="flex items-start space-x-2">
                <span>•</span>
                <span>Order critical items immediately to avoid stockouts</span>
              </li>
              <li className="flex items-start space-x-2">
                <span>•</span>
                <span>Consider bundling orders from the same supplier to save on shipping</span>
              </li>
              <li className="flex items-start space-x-2">
                <span>•</span>
                <span>The AI considers your {leadTime}-day lead time in all calculations</span>
              </li>
              <li className="flex items-start space-x-2">
                <span>•</span>
                <span>Recommendations update daily based on your latest sales velocity</span>
              </li>
            </ul>
          </div>
        </div>
      ) : (
        <div className="bg-white border border-gray-200 rounded-lg p-12">
          <div className="text-center">
            <Package className="h-12 w-12 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-500">No restocking recommendations available</p>
            <p className="text-sm text-gray-400 mt-2">
              Check back after you have more sales data
            </p>
          </div>
        </div>
      )}
    </div>
  );
};

export default AIRestockPage;