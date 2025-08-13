import React, { useState } from 'react';
import { 
  BarChart3, 
  Package, 
  TrendingUp,
  PieChart,
  Activity,
  AlertTriangle
} from 'lucide-react';

const AllProductAnalytics = () => {
  const [activeTab, setActiveTab] = useState('overview');

  const tabs = [
    { id: 'overview', name: 'Overview', icon: BarChart3 },
    { id: 'performance', name: 'Performance', icon: TrendingUp },
    { id: 'inventory', name: 'Inventory', icon: Package },
    { id: 'insights', name: 'Insights', icon: Activity }
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center space-x-3">
        <BarChart3 className="h-8 w-8 text-builders-500" />
        <div>
          <h1 className="text-2xl font-bold text-gray-900">All Product Analytics</h1>
          <p className="text-gray-600">Comprehensive analytics dashboard for all your products</p>
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
      {activeTab === 'overview' && (
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-center py-12">
            <BarChart3 className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">Product Overview</h3>
            <p className="text-gray-600">
              Comprehensive overview of all your products and their performance.
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

      {activeTab === 'performance' && (
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-center py-12">
            <TrendingUp className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">Performance Metrics</h3>
            <p className="text-gray-600">
              Detailed performance metrics and sales analytics.
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

      {activeTab === 'inventory' && (
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-center py-12">
            <Package className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">Inventory Analysis</h3>
            <p className="text-gray-600">
              Inventory levels, turnover rates, and stock management insights.
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

      {activeTab === 'insights' && (
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-center py-12">
            <Activity className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">Business Insights</h3>
            <p className="text-gray-600">
              AI-powered insights and recommendations for your business.
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

export default AllProductAnalytics;