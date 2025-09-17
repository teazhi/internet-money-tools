import React, { useState, useEffect } from 'react';
import { Brain, TrendingUp, AlertCircle, Lightbulb, Loader } from 'lucide-react';
import axios from 'axios';

const AIInsights = ({ selectedDate, analyticsData }) => {
  const [insights, setInsights] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showFullInsights, setShowFullInsights] = useState(false);
  const [aiStatus, setAiStatus] = useState(null);

  // Check if AI is enabled - try multiple possible fields or use cached status
  const aiEnabled = aiStatus?.ai_enabled || analyticsData?.ai_enabled || analyticsData?.ai_insights?.enabled || false;

  // Check AI status if not available in analytics data
  useEffect(() => {
    const checkAiStatus = async () => {
      if (!analyticsData?.ai_enabled && !analyticsData?.ai_insights?.enabled && !aiStatus) {
        try {
          const response = await axios.get('/api/analytics/ai-status', { withCredentials: true });
          setAiStatus(response.data);
        } catch (err) {
          // Silent fail - AI status check is not critical
          console.log('AI status check failed:', err);
        }
      }
    };
    
    checkAiStatus();
  }, [analyticsData, aiStatus]);

  useEffect(() => {
    // If AI insights are already included in analytics data, use them
    if (analyticsData?.ai_insights?.summary?.length > 0) {
      setInsights({
        insights: analyticsData.ai_insights.summary,
        recommendations: analyticsData.ai_insights.top_recommendation || [],
        ai_enabled: true
      });
    }
  }, [analyticsData]);

  const fetchFullInsights = async () => {
    if (!aiEnabled) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const dateParam = selectedDate ? `?date=${selectedDate}` : '';
      const response = await axios.get(`/api/analytics/ai-insights${dateParam}`, {
        withCredentials: true
      });
      setInsights(response.data);
      setShowFullInsights(true);
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to fetch AI insights');
    } finally {
      setLoading(false);
    }
  };

  if (!aiEnabled) {
    return (
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-6">
        <div className="flex items-center space-x-3 mb-4">
          <Brain className="h-6 w-6 text-gray-400" />
          <h3 className="text-lg font-semibold text-gray-600">AI Insights</h3>
        </div>
        <div className="text-center py-8">
          <Brain className="h-12 w-12 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-500 mb-4">AI insights are not configured</p>
          <p className="text-sm text-gray-400">
            Set your Keywords.ai API key to enable intelligent analytics
          </p>
        </div>
      </div>
    );
  }

  const renderInsightItem = (insight, index) => (
    <div key={index} className="flex items-start space-x-3 p-3 bg-blue-50 rounded-lg">
      <Lightbulb className="h-5 w-5 text-blue-500 mt-0.5 flex-shrink-0" />
      <p className="text-sm text-blue-800">{insight}</p>
    </div>
  );

  const renderRecommendation = (recommendation, index) => (
    <div key={index} className="flex items-start space-x-3 p-3 bg-green-50 rounded-lg">
      <TrendingUp className="h-5 w-5 text-green-500 mt-0.5 flex-shrink-0" />
      <p className="text-sm text-green-800">{recommendation}</p>
    </div>
  );

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-3">
          <Brain className="h-6 w-6 text-purple-500" />
          <h3 className="text-lg font-semibold text-gray-900">AI Insights</h3>
          <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
            Powered by AI
          </span>
        </div>
        
        {!showFullInsights && insights && (
          <button
            onClick={fetchFullInsights}
            disabled={loading}
            className="text-sm text-purple-600 hover:text-purple-800 font-medium"
          >
            View More Insights
          </button>
        )}
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
          <div className="flex items-center space-x-2">
            <AlertCircle className="h-4 w-4 text-red-500" />
            <p className="text-sm text-red-800">{error}</p>
          </div>
        </div>
      )}

      {loading && (
        <div className="text-center py-8">
          <Loader className="h-8 w-8 animate-spin text-purple-500 mx-auto mb-4" />
          <p className="text-gray-500">Generating AI insights...</p>
        </div>
      )}

      {insights && !loading && (
        <div className="space-y-4">
          {/* Quick Insights */}
          {insights.insights && insights.insights.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-gray-900 mb-3 flex items-center">
                <Lightbulb className="h-4 w-4 text-blue-500 mr-2" />
                Key Insights
              </h4>
              <div className="space-y-2">
                {insights.insights.slice(0, showFullInsights ? undefined : 2).map(renderInsightItem)}
              </div>
            </div>
          )}

          {/* Recommendations */}
          {insights.recommendations && insights.recommendations.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-gray-900 mb-3 flex items-center">
                <TrendingUp className="h-4 w-4 text-green-500 mr-2" />
                Recommendations
              </h4>
              <div className="space-y-2">
                {insights.recommendations.slice(0, showFullInsights ? undefined : 1).map(renderRecommendation)}
              </div>
            </div>
          )}

          {/* Warnings */}
          {showFullInsights && insights.warnings && insights.warnings.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-gray-900 mb-3 flex items-center">
                <AlertCircle className="h-4 w-4 text-orange-500 mr-2" />
                Warnings
              </h4>
              <div className="space-y-2">
                {insights.warnings.map((warning, index) => (
                  <div key={index} className="flex items-start space-x-3 p-3 bg-orange-50 rounded-lg">
                    <AlertCircle className="h-5 w-5 text-orange-500 mt-0.5 flex-shrink-0" />
                    <p className="text-sm text-orange-800">{warning}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Opportunities */}
          {showFullInsights && insights.opportunities && insights.opportunities.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-gray-900 mb-3 flex items-center">
                <TrendingUp className="h-4 w-4 text-purple-500 mr-2" />
                Growth Opportunities
              </h4>
              <div className="space-y-2">
                {insights.opportunities.map((opportunity, index) => (
                  <div key={index} className="flex items-start space-x-3 p-3 bg-purple-50 rounded-lg">
                    <TrendingUp className="h-5 w-5 text-purple-500 mt-0.5 flex-shrink-0" />
                    <p className="text-sm text-purple-800">{opportunity}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* No insights message */}
          {(!insights.insights || insights.insights.length === 0) && 
           (!insights.recommendations || insights.recommendations.length === 0) && (
            <div className="text-center py-6">
              <Brain className="h-8 w-8 text-gray-300 mx-auto mb-3" />
              <p className="text-gray-500">No insights available for this period</p>
              <p className="text-sm text-gray-400">Try selecting a different date with order data</p>
            </div>
          )}

          {/* Metadata */}
          {insights.date && (
            <div className="pt-3 border-t border-gray-100">
              <p className="text-xs text-gray-500">
                Analysis for {insights.date} • {insights.total_orders || 0} orders analyzed
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default AIInsights;