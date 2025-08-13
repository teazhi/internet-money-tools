import React, { useState } from 'react';
import { 
  Target, 
  TrendingDown, 
  BarChart3,
  Percent,
  AlertTriangle
} from 'lucide-react';

const DiscountOpportunities = () => {
  const [activeTab, setActiveTab] = useState('opportunities');

  const tabs = [
    { id: 'opportunities', name: 'Opportunities', icon: Target },
    { id: 'pricing', name: 'Pricing Analysis', icon: Percent },
    { id: 'trends', name: 'Market Trends', icon: TrendingDown }
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center space-x-3">
        <Target className="h-8 w-8 text-builders-500" />
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
      {activeTab === 'opportunities' && (
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-center py-12">
            <Target className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">Discount Opportunities</h3>
            <p className="text-gray-600">
              Find products with pricing opportunities and profit margins.
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