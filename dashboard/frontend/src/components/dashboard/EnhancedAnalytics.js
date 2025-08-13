import React, { useState } from 'react';
import { 
  TrendingUp, 
  ShoppingCart,
  Target,
  BarChart3,
  ArrowLeft
} from 'lucide-react';
import SmartRestockRecommendations from './SmartRestockRecommendations';
import RetailerLeadAnalysis from './RetailerLeadAnalysis';
import DiscountOpportunities from './DiscountOpportunities';
import AllProductAnalytics from './AllProductAnalytics';

const EnhancedAnalytics = () => {
  const [selectedAnalytic, setSelectedAnalytic] = useState(null);

  const analytics = [
    {
      id: 'smart-restock',
      name: 'Smart Restock Recommendations',
      description: 'AI-powered inventory recommendations based on sales velocity and trends',
      icon: TrendingUp,
      color: 'bg-blue-500',
      component: SmartRestockRecommendations
    },
    {
      id: 'lead-analysis',
      name: 'Lead Analysis',
      description: 'Analyze competitor prices and identify buying opportunities',
      icon: ShoppingCart,
      color: 'bg-green-500',
      component: RetailerLeadAnalysis
    },
    {
      id: 'discount-opportunities',
      name: 'Discount Opportunities',
      description: 'Find products with pricing opportunities and profit margins',
      icon: Target,
      color: 'bg-purple-500',
      component: DiscountOpportunities
    },
    {
      id: 'all-product-analytics',
      name: 'All Product Analytics',
      description: 'Comprehensive analytics dashboard for all your products',
      icon: BarChart3,
      color: 'bg-orange-500',
      component: AllProductAnalytics
    }
  ];

  const handleSelectAnalytic = (analytic) => {
    if (analytic.component) {
      setSelectedAnalytic(analytic);
    }
  };

  const handleBackToMenu = () => {
    setSelectedAnalytic(null);
  };

  if (selectedAnalytic) {
    const SelectedComponent = selectedAnalytic.component;
    return (
      <div className="space-y-6">
        {/* Back Button */}
        <div className="flex items-center space-x-4">
          <button
            onClick={handleBackToMenu}
            className="flex items-center space-x-2 text-gray-600 hover:text-gray-900 transition-colors"
          >
            <ArrowLeft className="h-5 w-5" />
            <span>Back to Analytics Menu</span>
          </button>
        </div>

        {/* Selected Component */}
        <SelectedComponent />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center space-x-3">
        <TrendingUp className="h-8 w-8 text-builders-500" />
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Smart Restock Analytics</h1>
          <p className="text-gray-600">Choose an analytics tool to get started</p>
        </div>
      </div>

      {/* Analytics Selection Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {analytics.map((analytic) => {
          const Icon = analytic.icon;
          const isAvailable = analytic.component !== null;
          
          return (
            <div
              key={analytic.id}
              onClick={() => isAvailable && handleSelectAnalytic(analytic)}
              className={`relative bg-white rounded-lg shadow-sm border border-gray-200 p-6 transition-all duration-200 ${
                isAvailable 
                  ? 'hover:shadow-md hover:border-gray-300 cursor-pointer' 
                  : 'opacity-50 cursor-not-allowed'
              }`}
            >
              {/* Icon */}
              <div className={`inline-flex items-center justify-center w-12 h-12 rounded-lg ${analytic.color} mb-4`}>
                <Icon className="h-6 w-6 text-white" />
              </div>

              {/* Content */}
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">
                  {analytic.name}
                </h3>
                <p className="text-gray-600 text-sm mb-4">
                  {analytic.description}
                </p>
              </div>

              {/* Status Badge */}
              <div className="absolute top-4 right-4">
                {isAvailable ? (
                  <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                    Available
                  </span>
                ) : (
                  <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
                    Coming Soon
                  </span>
                )}
              </div>

              {/* Hover Effect Arrow */}
              {isAvailable && (
                <div className="absolute bottom-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity">
                  <div className="w-6 h-6 bg-gray-100 rounded-full flex items-center justify-center">
                    <ArrowLeft className="h-3 w-3 text-gray-600 transform rotate-180" />
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Info Box */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <div className="flex items-start space-x-3">
          <TrendingUp className="h-5 w-5 text-blue-500 mt-0.5" />
          <div>
            <h4 className="text-sm font-medium text-blue-900">Analytics Overview</h4>
            <p className="text-sm text-blue-700 mt-1">
              Each analytics tool provides unique insights to help optimize your Amazon business. 
              Start with Smart Restock Recommendations for inventory planning or Lead Analysis for competitive pricing insights.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default EnhancedAnalytics;