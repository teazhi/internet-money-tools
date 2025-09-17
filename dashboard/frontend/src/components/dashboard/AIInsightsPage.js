import React, { useState, useEffect } from 'react';
import { Brain, TrendingUp, AlertCircle, Lightbulb, Loader, Calendar } from 'lucide-react';
import axios from 'axios';
import AIInsights from '../AIInsights';

const AIInsightsPage = () => {
  const [selectedDate, setSelectedDate] = useState('');
  const [insights, setInsights] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchInsights();
  }, [selectedDate]);

  const fetchInsights = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const dateParam = selectedDate ? `?date=${selectedDate}` : '';
      const response = await axios.get(`/api/analytics/ai-insights${dateParam}`, {
        withCredentials: true
      });
      setInsights(response.data);
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to fetch AI insights');
    } finally {
      setLoading(false);
    }
  };

  const handleDateChange = (e) => {
    setSelectedDate(e.target.value);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-purple-600 to-indigo-600 rounded-lg shadow-sm p-6 text-white">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center space-x-3 mb-2">
              <Brain className="h-8 w-8" />
              <h1 className="text-2xl font-bold">AI-Powered Insights</h1>
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
                Beta
              </span>
            </div>
            <p className="text-purple-100">
              Intelligent analysis and recommendations powered by AI
            </p>
          </div>
          
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2">
              <Calendar className="h-5 w-5 text-purple-200" />
              <input
                type="date"
                value={selectedDate}
                onChange={handleDateChange}
                className="bg-white/20 backdrop-blur-sm border border-white/30 rounded-md px-3 py-2 text-sm text-white placeholder-purple-200"
                placeholder="Select date"
              />
            </div>
          </div>
        </div>
      </div>

      {/* AI Status Card */}
      <div className="bg-white border border-gray-200 rounded-lg p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className={`h-3 w-3 rounded-full ${insights?.ai_enabled ? 'bg-green-500' : 'bg-gray-300'}`} />
            <span className="text-sm font-medium text-gray-900">
              AI Status: {insights?.ai_enabled ? 'Active' : 'Inactive'}
            </span>
          </div>
          {insights && (
            <span className="text-xs text-gray-500">
              {insights.total_orders || 0} orders analyzed
            </span>
          )}
        </div>
      </div>

      {/* Main Content */}
      {loading ? (
        <div className="bg-white border border-gray-200 rounded-lg p-12">
          <div className="text-center">
            <Loader className="h-12 w-12 animate-spin text-purple-500 mx-auto mb-4" />
            <p className="text-gray-500">Analyzing your data with AI...</p>
            <p className="text-sm text-gray-400 mt-2">This may take a few moments</p>
          </div>
        </div>
      ) : error ? (
        <div className="bg-red-50 border border-red-200 rounded-lg p-6">
          <div className="flex items-start space-x-3">
            <AlertCircle className="h-5 w-5 text-red-500 mt-0.5 flex-shrink-0" />
            <div>
              <h3 className="text-sm font-medium text-red-800">Error Loading AI Insights</h3>
              <p className="text-sm text-red-700 mt-1">{error}</p>
              <button
                onClick={fetchInsights}
                className="mt-3 px-3 py-1.5 bg-red-100 hover:bg-red-200 text-red-800 text-sm font-medium rounded-md transition-colors"
              >
                Try Again
              </button>
            </div>
          </div>
        </div>
      ) : insights ? (
        <div className="space-y-6">
          {/* Full AI Insights Component */}
          <div className="bg-white border border-gray-200 rounded-lg p-6">
            <div className="mb-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-2">Detailed Analysis</h2>
              <p className="text-sm text-gray-500">
                AI-generated insights based on your sales and inventory data
              </p>
            </div>
            
            {/* Insights */}
            {insights.insights && insights.insights.length > 0 && (
              <div className="mb-6">
                <h3 className="text-sm font-medium text-gray-900 mb-3 flex items-center">
                  <Lightbulb className="h-4 w-4 text-blue-500 mr-2" />
                  Key Insights
                </h3>
                <div className="space-y-2">
                  {insights.insights.map((insight, index) => (
                    <div key={index} className="flex items-start space-x-3 p-3 bg-blue-50 rounded-lg">
                      <span className="text-xs font-medium text-blue-600">{index + 1}</span>
                      <p className="text-sm text-blue-800">{insight}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {/* Recommendations */}
            {insights.recommendations && insights.recommendations.length > 0 && (
              <div className="mb-6">
                <h3 className="text-sm font-medium text-gray-900 mb-3 flex items-center">
                  <TrendingUp className="h-4 w-4 text-green-500 mr-2" />
                  Recommendations
                </h3>
                <div className="space-y-2">
                  {insights.recommendations.map((rec, index) => (
                    <div key={index} className="flex items-start space-x-3 p-3 bg-green-50 rounded-lg">
                      <span className="text-xs font-medium text-green-600">{index + 1}</span>
                      <p className="text-sm text-green-800">{rec}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {/* Warnings */}
            {insights.warnings && insights.warnings.length > 0 && (
              <div className="mb-6">
                <h3 className="text-sm font-medium text-gray-900 mb-3 flex items-center">
                  <AlertCircle className="h-4 w-4 text-orange-500 mr-2" />
                  Warnings
                </h3>
                <div className="space-y-2">
                  {insights.warnings.map((warning, index) => (
                    <div key={index} className="flex items-start space-x-3 p-3 bg-orange-50 rounded-lg">
                      <span className="text-xs font-medium text-orange-600">{index + 1}</span>
                      <p className="text-sm text-orange-800">{warning}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {/* Opportunities */}
            {insights.opportunities && insights.opportunities.length > 0 && (
              <div className="mb-6">
                <h3 className="text-sm font-medium text-gray-900 mb-3 flex items-center">
                  <TrendingUp className="h-4 w-4 text-purple-500 mr-2" />
                  Growth Opportunities
                </h3>
                <div className="space-y-2">
                  {insights.opportunities.map((opp, index) => (
                    <div key={index} className="flex items-start space-x-3 p-3 bg-purple-50 rounded-lg">
                      <span className="text-xs font-medium text-purple-600">{index + 1}</span>
                      <p className="text-sm text-purple-800">{opp}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {/* No insights message */}
            {(!insights.insights || insights.insights.length === 0) && 
             (!insights.recommendations || insights.recommendations.length === 0) && 
             (!insights.warnings || insights.warnings.length === 0) && 
             (!insights.opportunities || insights.opportunities.length === 0) && (
              <div className="text-center py-8">
                <Brain className="h-12 w-12 text-gray-300 mx-auto mb-4" />
                <p className="text-gray-500">No insights available for this period</p>
                <p className="text-sm text-gray-400 mt-2">
                  Try selecting a different date with more order data
                </p>
              </div>
            )}
          </div>

          {/* How it Works */}
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-6">
            <h3 className="text-sm font-medium text-gray-900 mb-3">How AI Insights Work</h3>
            <div className="space-y-3 text-sm text-gray-600">
              <div className="flex items-start space-x-3">
                <span className="text-purple-600 font-medium">1.</span>
                <p>AI analyzes your sales patterns, inventory levels, and profit margins</p>
              </div>
              <div className="flex items-start space-x-3">
                <span className="text-purple-600 font-medium">2.</span>
                <p>Identifies trends, anomalies, and optimization opportunities</p>
              </div>
              <div className="flex items-start space-x-3">
                <span className="text-purple-600 font-medium">3.</span>
                <p>Generates actionable recommendations to improve your business</p>
              </div>
              <div className="flex items-start space-x-3">
                <span className="text-purple-600 font-medium">4.</span>
                <p>Updates insights based on your latest data and market conditions</p>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
};

export default AIInsightsPage;