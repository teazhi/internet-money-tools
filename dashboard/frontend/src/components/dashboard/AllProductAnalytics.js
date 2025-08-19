import React, { useState } from 'react';
import { 
  BarChart3, 
  Package, 
  TrendingUp,
  PieChart,
  Activity,
  AlertTriangle
} from 'lucide-react';
import StandardTable from '../common/StandardTable';

const AllProductAnalytics = () => {
  const [activeTab, setActiveTab] = useState('overview');

  // Table configuration functions (placeholder for when data is available)
  const getOverviewColumns = () => ({
    product: { key: 'product', label: 'Product', sortKey: 'product_name', draggable: true },
    sales: { key: 'sales', label: 'Sales', sortKey: 'total_sales', draggable: true },
    revenue: { key: 'revenue', label: 'Revenue', sortKey: 'revenue', draggable: true },
    profit: { key: 'profit', label: 'Profit', sortKey: 'profit', draggable: true },
    stock: { key: 'stock', label: 'Stock', sortKey: 'current_stock', draggable: true },
    trend: { key: 'trend', label: 'Trend', sortKey: null, draggable: true }
  });

  const getPerformanceColumns = () => ({
    product: { key: 'product', label: 'Product', sortKey: 'product_name', draggable: true },
    velocity: { key: 'velocity', label: 'Velocity', sortKey: 'velocity', draggable: true },
    conversion: { key: 'conversion', label: 'Conversion', sortKey: 'conversion_rate', draggable: true },
    sessions: { key: 'sessions', label: 'Sessions', sortKey: 'sessions', draggable: true },
    rank: { key: 'rank', label: 'BSR', sortKey: 'bsr', draggable: true },
    competition: { key: 'competition', label: 'Competition', sortKey: null, draggable: true }
  });

  const getInventoryColumns = () => ({
    product: { key: 'product', label: 'Product', sortKey: 'product_name', draggable: true },
    current_stock: { key: 'current_stock', label: 'Current Stock', sortKey: 'current_stock', draggable: true },
    days_left: { key: 'days_left', label: 'Days Left', sortKey: 'days_left', draggable: true },
    turnover: { key: 'turnover', label: 'Turnover Rate', sortKey: 'turnover_rate', draggable: true },
    reorder_point: { key: 'reorder_point', label: 'Reorder Point', sortKey: 'reorder_point', draggable: true },
    status: { key: 'status', label: 'Status', sortKey: 'status', draggable: true }
  });

  const getInsightsColumns = () => ({
    product: { key: 'product', label: 'Product', sortKey: 'product_name', draggable: true },
    insight_type: { key: 'insight_type', label: 'Type', sortKey: 'insight_type', draggable: true },
    recommendation: { key: 'recommendation', label: 'Recommendation', sortKey: null, draggable: true },
    priority: { key: 'priority', label: 'Priority', sortKey: 'priority', draggable: true },
    impact: { key: 'impact', label: 'Impact', sortKey: 'impact_score', draggable: true },
    action: { key: 'action', label: 'Action', sortKey: null, draggable: false }
  });

  const getInventoryFilters = () => [
    {
      key: 'status',
      label: 'Status',
      defaultValue: 'all',
      options: [
        { value: 'in_stock', label: 'In Stock' },
        { value: 'low_stock', label: 'Low Stock' },
        { value: 'out_of_stock', label: 'Out of Stock' },
        { value: 'reorder_needed', label: 'Reorder Needed' }
      ],
      filterFn: (item, value) => item.status === value
    }
  ];

  const getInsightsFilters = () => [
    {
      key: 'insight_type',
      label: 'Type',
      defaultValue: 'all',
      options: [
        { value: 'opportunity', label: 'Opportunity' },
        { value: 'warning', label: 'Warning' },
        { value: 'optimization', label: 'Optimization' },
        { value: 'trend', label: 'Trend' }
      ],
      filterFn: (item, value) => item.insight_type === value
    },
    {
      key: 'priority',
      label: 'Priority',
      defaultValue: 'all',
      options: [
        { value: 'high', label: 'High' },
        { value: 'medium', label: 'Medium' },
        { value: 'low', label: 'Low' }
      ],
      filterFn: (item, value) => item.priority === value
    }
  ];

  // Placeholder render functions for when data is available
  const renderOverviewCell = (columnKey, item) => (
    <td key={columnKey} className="px-3 py-3 whitespace-nowrap text-sm text-gray-900">
      {/* Cell content based on columnKey */}
    </td>
  );

  const renderPerformanceCell = (columnKey, item) => (
    <td key={columnKey} className="px-3 py-3 whitespace-nowrap text-sm text-gray-900">
      {/* Cell content based on columnKey */}
    </td>
  );

  const renderInventoryCell = (columnKey, item) => (
    <td key={columnKey} className="px-3 py-3 whitespace-nowrap text-sm text-gray-900">
      {/* Cell content based on columnKey */}
    </td>
  );

  const renderInsightsCell = (columnKey, item) => (
    <td key={columnKey} className="px-3 py-3 whitespace-nowrap text-sm text-gray-900">
      {/* Cell content based on columnKey */}
    </td>
  );

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
          {/* Placeholder table structure for when data is available */}
          <div className="hidden">
            <StandardTable
              data={[]}
              tableKey="all-products-overview"
              columns={getOverviewColumns()}
              defaultColumnOrder={['product', 'sales', 'revenue', 'profit', 'stock', 'trend']}
              renderCell={renderOverviewCell}
              enableSearch={true}
              enableFilters={true}
              enableSorting={true}
              enableColumnReordering={true}
              enableColumnResetting={true}
              searchPlaceholder="Search products by ASIN, name..."
              searchFields={['asin', 'product_name']}
              emptyIcon={Package}
              emptyTitle="No Products"
              emptyDescription="No product data available"
            />
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
          {/* Placeholder table structure for when data is available */}
          <div className="hidden">
            <StandardTable
              data={[]}
              tableKey="all-products-performance"
              columns={getPerformanceColumns()}
              defaultColumnOrder={['product', 'velocity', 'conversion', 'sessions', 'rank', 'competition']}
              renderCell={renderPerformanceCell}
              enableSearch={true}
              enableFilters={true}
              enableSorting={true}
              enableColumnReordering={true}
              enableColumnResetting={true}
              searchPlaceholder="Search by product name, ASIN..."
              searchFields={['asin', 'product_name', 'category']}
              emptyIcon={TrendingUp}
              emptyTitle="No Performance Data"
              emptyDescription="No performance metrics available"
            />
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
          {/* Placeholder table structure for when data is available */}
          <div className="hidden">
            <StandardTable
              data={[]}
              tableKey="all-products-inventory"
              columns={getInventoryColumns()}
              defaultColumnOrder={['product', 'current_stock', 'days_left', 'turnover', 'reorder_point', 'status']}
              renderCell={renderInventoryCell}
              enableSearch={true}
              enableFilters={true}
              enableSorting={true}
              enableColumnReordering={true}
              enableColumnResetting={true}
              searchPlaceholder="Search by ASIN, product name..."
              searchFields={['asin', 'product_name']}
              filters={getInventoryFilters()}
              emptyIcon={Package}
              emptyTitle="No Inventory Data"
              emptyDescription="No inventory information available"
            />
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
          {/* Placeholder table structure for when data is available */}
          <div className="hidden">
            <StandardTable
              data={[]}
              tableKey="all-products-insights"
              columns={getInsightsColumns()}
              defaultColumnOrder={['product', 'insight_type', 'recommendation', 'priority', 'impact', 'action']}
              renderCell={renderInsightsCell}
              enableSearch={true}
              enableFilters={true}
              enableSorting={true}
              enableColumnReordering={true}
              enableColumnResetting={true}
              searchPlaceholder="Search insights, recommendations..."
              searchFields={['product_name', 'insight_type', 'recommendation']}
              filters={getInsightsFilters()}
              emptyIcon={Activity}
              emptyTitle="No Insights"
              emptyDescription="No business insights available"
            />
          </div>
        </div>
      )}
    </div>
  );
};

export default AllProductAnalytics;