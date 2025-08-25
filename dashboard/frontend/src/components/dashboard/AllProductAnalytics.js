import React, { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import { 
  BarChart3, 
  Package, 
  TrendingUp,
  Activity,
  AlertTriangle,
  Calendar,
  ShoppingCart,
  Clock,
  ExternalLink
} from 'lucide-react';
import StandardTable from '../common/StandardTable';
import { useProductImages } from '../../hooks/useProductImages';

// Mock data generator for when endpoints are unavailable
const generateMockInventoryData = () => {
  const mockAsins = ['B08N5WRWNW', 'B07XJ8C8F7', 'B09KMXJQ9R', 'B08ABC123', 'B09DEF456', 'B07GHI789'];
  
  const ageCategories = {
    'fresh': {'min': 0, 'max': 30, 'label': 'Fresh (0-30 days)', 'color': '#10b981'},
    'moderate': {'min': 31, 'max': 90, 'label': 'Moderate (31-90 days)', 'color': '#f59e0b'}, 
    'aged': {'min': 91, 'max': 180, 'label': 'Aged (91-180 days)', 'color': '#f97316'},
    'old': {'min': 181, 'max': 365, 'label': 'Old (181-365 days)', 'color': '#dc2626'},
    'ancient': {'min': 366, 'max': 1000, 'label': 'Ancient (365+ days)', 'color': '#7c2d12'}
  };

  const ageAnalysis = {};
  const categoriesCount = {fresh: 1, moderate: 2, aged: 1, old: 1, ancient: 1};
  
  mockAsins.forEach((asin, index) => {
    const categories = ['fresh', 'moderate', 'aged', 'old', 'ancient'];
    const category = categories[index % categories.length];
    const config = ageCategories[category];
    const ageDays = Math.floor(Math.random() * (config.max - config.min + 1)) + config.min;
    
    ageAnalysis[asin] = {
      estimated_age_days: ageDays,
      age_category: category,
      confidence_score: 0.7 + Math.random() * 0.25,
      data_sources: ['mock_data'],
      age_range: {min: ageDays - 5, max: ageDays + 5, variance: 10},
      recommendations: [`Mock recommendation for ${category} inventory`]
    };
  });

  return {
    age_analysis: ageAnalysis,
    summary: {
      total_products: mockAsins.length,
      products_with_age_data: mockAsins.length,
      coverage_percentage: 100.0,
      average_age_days: 120,
      categories_breakdown: categoriesCount,
      insights: [
        "⚠️ This is mock data for demonstration purposes",
        "🔧 Configure backend endpoints for real inventory age analysis"
      ]
    },
    age_categories: ageCategories,
    action_items: [],
    total_action_items: 0,
    demo_mode: true,
    fallback_mode: true
  };
};

const AllProductAnalytics = () => {
  const [activeTab, setActiveTab] = useState('inventory');
  const [allProductsData, setAllProductsData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Fetch comprehensive product data
  const fetchAllProductsData = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Try main endpoint first, fallback to demo, then fallback to mock data
      let response;
      try {
        const url = '/api/analytics/inventory-age';
        console.log('Calling endpoint:', url);
        response = await axios.get(url, { 
          withCredentials: true,
          headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
          },
          responseType: 'json' // Force axios to parse as JSON
        });
        console.log('Response status:', response.status);
        console.log('Response headers:', response.headers);
        console.log('✓ Successfully loaded real inventory age data');
        
        // Debug the raw response
        console.log('Raw response type:', typeof response.data);
        console.log('Is array?', Array.isArray(response.data));
        console.log('Response data constructor:', response.data?.constructor?.name);
        
        // Check if response.data is a string that needs parsing
        if (typeof response.data === 'string') {
          console.log('Response is a string, length:', response.data.length);
          console.log('First 200 chars:', response.data.substring(0, 200));
          console.log('Last 200 chars:', response.data.substring(response.data.length - 200));
          
          // Check if the string looks like it might be double-encoded or corrupted
          const firstChar = response.data[0];
          console.log('First character:', firstChar, 'char code:', firstChar.charCodeAt(0));
          
          // Log character at position 6 where error occurs
          console.log('Character at position 6:', response.data[6], 'char code:', response.data.charCodeAt(6));
          
          // Check for BOM or other invisible characters
          if (response.data.charCodeAt(0) === 0xFEFF) {
            console.log('Found BOM, removing it');
            response.data = response.data.substring(1);
          }
          
          try {
            const parsed = JSON.parse(response.data);
            console.log('Successfully parsed string response');
            console.log('Parsed keys:', Object.keys(parsed));
            response.data = parsed;
          } catch (e) {
            console.error('Failed to parse string response:', e);
            // Try to find where the JSON might be valid
            const validJsonMatch = response.data.match(/(\{[\s\S]*\})/);
            if (validJsonMatch) {
              console.log('Found potential JSON match');
              try {
                const parsed = JSON.parse(validJsonMatch[1]);
                console.log('Successfully parsed extracted JSON');
                response.data = parsed;
              } catch (e2) {
                console.error('Failed to parse extracted JSON:', e2);
              }
            }
          }
        }
        
        // If it's an array or has numeric keys, log more info
        if (Array.isArray(response.data) || (response.data && Object.keys(response.data)[0] === '0')) {
          console.log('WARNING: Response appears to be an array or array-like object!');
          console.log('Sample of response:', response.data?.slice ? response.data.slice(0, 3) : 'Cannot slice');
          console.log('First item type:', typeof response.data[0]);
          if (response.data[0]) {
            console.log('First item:', response.data[0]);
          }
        }
        
        console.log('Backend response data keys:', Object.keys(response.data || {}));
        console.log('Age analysis exists?', !!response.data?.age_analysis);
        console.log('Age analysis type:', typeof response.data?.age_analysis);
        if (response.data?.age_analysis) {
          const keys = Object.keys(response.data.age_analysis);
          console.log('Number of products in age_analysis:', keys.length);
          console.log('First 10 age_analysis keys:', keys.slice(0, 10));
          console.log('Sample age_analysis entry:', response.data.age_analysis[keys[0]]);
        }
      } catch (mainError) {
        console.log('Main endpoint failed:', mainError.response?.data);
        console.log('Trying demo mode...');
        try {
          response = await axios.get('/api/demo/analytics/inventory-age', { 
            withCredentials: true 
          });
          console.log('✓ Successfully loaded demo inventory age data');
        } catch (demoError) {
          console.log('Demo endpoint failed:', demoError.response?.data);
          console.log('Using fallback data...');
          // Use fallback mock data when endpoints are not available
          response = {
            data: generateMockInventoryData()
          };
        }
      }
      
      setAllProductsData(response.data);
      
    } catch (err) {
      setError(err.response?.data?.message || 'Failed to load product data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAllProductsData();
  }, []);

  // Extract ASINs for image loading
  const allAsins = useMemo(() => {
    if (!allProductsData?.age_analysis) return [];
    return Object.keys(allProductsData.age_analysis);
  }, [allProductsData]);

  const { images: batchImages, loading: imagesLoading } = useProductImages(allAsins);

  // Prepare table data for inventory tab
  const inventoryTableData = useMemo(() => {
    if (!allProductsData?.age_analysis) return [];
    
    return Object.entries(allProductsData.age_analysis).map(([asin, ageInfo]) => ({
      id: asin,
      asin,
      product_name: `Product ${asin}`, // This would come from enhanced analytics in real implementation
      age_info: ageInfo,
      estimated_age_days: ageInfo.estimated_age_days || 0,
      age_category: ageInfo.age_category || 'unknown',
      confidence_score: ageInfo.confidence_score || 0,
      // Mock additional inventory data for demonstration
      current_stock: Math.floor(Math.random() * 200) + 10,
      velocity: Math.random() * 5 + 0.1,
      days_left: Math.floor(Math.random() * 180) + 5,
      reorder_point: Math.floor(Math.random() * 50) + 10,
      last_cogs: Math.random() * 50 + 10,
      supplier_info: 'Various',
      status: ageInfo.age_category === 'ancient' ? 'critical' : 
              ageInfo.age_category === 'old' ? 'warning' :
              ageInfo.age_category === 'aged' ? 'attention' : 'normal'
    }));
  }, [allProductsData]);

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
    product: { key: 'product', label: 'Product', sortKey: 'product_name', draggable: false },
    current_stock: { key: 'current_stock', label: 'Current Stock', sortKey: 'current_stock', draggable: true },
    velocity: { key: 'velocity', label: 'Velocity', sortKey: 'velocity', draggable: true },
    days_left: { key: 'days_left', label: 'Days Left', sortKey: 'days_left', draggable: true },
    inventory_age: { key: 'inventory_age', label: 'Inventory Age', sortKey: 'estimated_age_days', draggable: true },
    last_cogs: { key: 'last_cogs', label: 'Last COGS', sortKey: 'last_cogs', draggable: true },
    reorder_point: { key: 'reorder_point', label: 'Reorder Point', sortKey: 'reorder_point', draggable: true },
    status: { key: 'status', label: 'Status', sortKey: 'status', draggable: true },
    actions: { key: 'actions', label: 'Actions', sortKey: null, draggable: false }
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
      key: 'age_category',
      label: 'Inventory Age',
      allLabel: 'All Ages',
      options: [
        { value: 'fresh', label: 'Fresh (0-30 days)' },
        { value: 'moderate', label: 'Moderate (31-90 days)' },
        { value: 'aged', label: 'Aged (91-180 days)' },
        { value: 'old', label: 'Old (181-365 days)' },
        { value: 'ancient', label: 'Ancient (365+ days)' },
        { value: 'unknown', label: 'Unknown Age' }
      ],
      filterFn: (item, value) => item.age_category === value
    },
    {
      key: 'status',
      label: 'Status',
      allLabel: 'All Status',
      options: [
        { value: 'normal', label: 'Normal' },
        { value: 'attention', label: 'Needs Attention' },
        { value: 'warning', label: 'Warning' },
        { value: 'critical', label: 'Critical' }
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

  // Product Image Component
  const ProductImage = ({ asin }) => {
    const imageUrl = batchImages?.[asin];
    const isLoading = imagesLoading && !imageUrl;
    
    if (isLoading) {
      return (
        <div className="h-12 w-12 rounded-lg bg-gray-100 border border-gray-200 flex items-center justify-center">
          <div className="h-4 w-4 bg-gray-300 rounded animate-pulse" />
        </div>
      );
    }

    if (!imageUrl) {
      return (
        <div className="h-12 w-12 rounded-lg bg-gradient-to-br from-blue-50 to-indigo-100 border border-blue-200 flex items-center justify-center">
          <Package className="h-6 w-6 text-blue-600" />
        </div>
      );
    }

    return (
      <div className="h-12 w-12 rounded-lg overflow-hidden border border-gray-200 bg-white">
        <img
          src={imageUrl}
          alt={`Product ${asin}`}
          className="h-full w-full object-cover"
          loading="lazy"
        />
      </div>
    );
  };

  // Age category styling
  const getAgeCategoryStyles = (category) => {
    const styles = {
      'fresh': 'bg-green-100 text-green-800',
      'moderate': 'bg-yellow-100 text-yellow-800',
      'aged': 'bg-orange-100 text-orange-800',
      'old': 'bg-red-100 text-red-800',
      'ancient': 'bg-red-200 text-red-900',
      'unknown': 'bg-gray-100 text-gray-800'
    };
    return styles[category] || styles.unknown;
  };

  // Status styling
  const getStatusStyles = (status) => {
    const styles = {
      'normal': 'bg-green-100 text-green-800',
      'attention': 'bg-yellow-100 text-yellow-800',
      'warning': 'bg-orange-100 text-orange-800',
      'critical': 'bg-red-100 text-red-800'
    };
    return styles[status] || styles.normal;
  };

  // Format currency
  const formatCurrency = (amount) => {
    return `$${parseFloat(amount).toFixed(2)}`;
  };

  // Format days
  const formatDays = (days) => {
    if (days < 1) return '< 1 day';
    if (days === 1) return '1 day';
    return `${Math.round(days)} days`;
  };

  // Render functions for different tabs
  const renderOverviewCell = (columnKey, item) => (
    <td key={columnKey} className="px-3 py-3 whitespace-nowrap text-sm text-gray-900">
      {/* Placeholder for overview data */}
      Coming Soon
    </td>
  );

  const renderPerformanceCell = (columnKey, item) => (
    <td key={columnKey} className="px-3 py-3 whitespace-nowrap text-sm text-gray-900">
      {/* Placeholder for performance data */}
      Coming Soon
    </td>
  );

  const renderInventoryCell = (columnKey, item) => {
    switch (columnKey) {
      case 'product':
        return (
          <td key={columnKey} className="px-3 py-2">
            <div className="flex items-center space-x-3">
              <div className="flex-shrink-0">
                <a 
                  href={`https://www.amazon.com/dp/${item.asin}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block hover:opacity-80 transition-opacity"
                >
                  <ProductImage asin={item.asin} />
                </a>
              </div>
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium text-gray-900">
                  <a 
                    href={`https://www.amazon.com/dp/${item.asin}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="hover:text-blue-600 transition-colors"
                  >
                    {item.product_name}
                  </a>
                </div>
                <div className="text-xs text-gray-500">{item.asin}</div>
              </div>
            </div>
          </td>
        );

      case 'current_stock':
        return (
          <td key={columnKey} className="px-3 py-2 whitespace-nowrap text-sm text-gray-900">
            {Math.round(item.current_stock)}
          </td>
        );

      case 'velocity':
        return (
          <td key={columnKey} className="px-3 py-2 whitespace-nowrap text-sm text-gray-900">
            {item.velocity.toFixed(1)}/day
          </td>
        );

      case 'days_left':
        return (
          <td key={columnKey} className="px-3 py-2 whitespace-nowrap text-sm text-gray-900">
            {formatDays(item.days_left)}
          </td>
        );

      case 'inventory_age':
        return (
          <td key={columnKey} className="px-3 py-2 whitespace-nowrap">
            <div className="flex flex-col space-y-1">
              {item.estimated_age_days > 0 ? (
                <>
                  <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${getAgeCategoryStyles(item.age_category)}`}>
                    <Calendar className="h-3 w-3 mr-1" />
                    {item.estimated_age_days} days
                  </span>
                  <div className="text-xs text-gray-500">
                    {Math.round(item.confidence_score * 100)}% confidence
                  </div>
                </>
              ) : (
                <span className="text-xs text-gray-400">Unknown</span>
              )}
            </div>
          </td>
        );

      case 'last_cogs':
        return (
          <td key={columnKey} className="px-3 py-2 whitespace-nowrap text-sm">
            <div className="text-green-700 font-medium">
              {formatCurrency(item.last_cogs)}
            </div>
          </td>
        );

      case 'reorder_point':
        return (
          <td key={columnKey} className="px-3 py-2 whitespace-nowrap text-sm text-gray-900">
            {Math.round(item.reorder_point)}
          </td>
        );

      case 'status':
        return (
          <td key={columnKey} className="px-3 py-2 whitespace-nowrap">
            <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${getStatusStyles(item.status)}`}>
              {item.status === 'critical' && <AlertTriangle className="h-3 w-3 mr-1" />}
              {item.status === 'warning' && <Clock className="h-3 w-3 mr-1" />}
              {item.status.charAt(0).toUpperCase() + item.status.slice(1)}
            </span>
          </td>
        );

      case 'actions':
        return (
          <td key={columnKey} className="px-3 py-2 whitespace-nowrap">
            <button className="inline-flex items-center px-2 py-1 bg-blue-600 text-white text-xs rounded-md hover:bg-blue-700 transition-colors">
              <ShoppingCart className="h-3 w-3 mr-1" />
              Restock
            </button>
          </td>
        );

      default:
        return (
          <td key={columnKey} className="px-3 py-3 whitespace-nowrap text-sm text-gray-900">
            -
          </td>
        );
    }
  };

  const renderInsightsCell = (columnKey, item) => (
    <td key={columnKey} className="px-3 py-3 whitespace-nowrap text-sm text-gray-900">
      {/* Placeholder for insights data */}
      Coming Soon
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
          {loading && (
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
              <span className="ml-3 text-gray-600">Loading inventory analysis...</span>
            </div>
          )}

          {error && (
            <div className="text-center py-8">
              <AlertTriangle className="h-12 w-12 text-red-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">Failed to Load</h3>
              <p className="text-gray-600 mb-4">{error}</p>
              <button
                onClick={fetchAllProductsData}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
              >
                Retry
              </button>
            </div>
          )}

          {!loading && !error && allProductsData && (
            <>
              <div className="mb-6">
                <h3 className="text-lg font-medium text-gray-900 mb-2">Complete Inventory Analysis</h3>
                <p className="text-gray-600 mb-4">
                  Comprehensive view of all products with inventory levels, age analysis, and restock recommendations.
                </p>

                {/* Fallback Mode Indicator */}
                {allProductsData.fallback_mode && (
                  <div className="mb-4 p-3 bg-orange-50 border border-orange-200 rounded-lg">
                    <div className="flex items-center">
                      <AlertTriangle className="h-5 w-5 text-orange-600 mr-2" />
                      <div>
                        <p className="text-sm font-medium text-orange-800">
                          Demo Mode: Using Mock Data
                        </p>
                        <p className="text-xs text-orange-700 mt-1">
                          Backend endpoints are not available. Showing sample inventory age data for demonstration purposes.
                        </p>
                      </div>
                    </div>
                  </div>
                )}

                {/* Summary Stats */}
                {allProductsData.summary && (
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
                    <div className="bg-blue-50 rounded-lg p-4">
                      <div className="text-lg font-semibold text-blue-900">
                        {allProductsData.summary.total_products}
                      </div>
                      <div className="text-sm text-blue-700">Total Products</div>
                    </div>
                    <div className="bg-green-50 rounded-lg p-4">
                      <div className="text-lg font-semibold text-green-900">
                        {allProductsData.summary.average_age_days} days
                      </div>
                      <div className="text-sm text-green-700">Avg. Inventory Age</div>
                    </div>
                    <div className="bg-yellow-50 rounded-lg p-4">
                      <div className="text-lg font-semibold text-yellow-900">
                        {Math.round(allProductsData.summary.coverage_percentage)}%
                      </div>
                      <div className="text-sm text-yellow-700">Age Data Coverage</div>
                    </div>
                    <div className="bg-red-50 rounded-lg p-4">
                      <div className="text-lg font-semibold text-red-900">
                        {(allProductsData.summary.categories_breakdown?.aged || 0) + 
                         (allProductsData.summary.categories_breakdown?.old || 0) + 
                         (allProductsData.summary.categories_breakdown?.ancient || 0)}
                      </div>
                      <div className="text-sm text-red-700">Aged Products</div>
                    </div>
                  </div>
                )}
              </div>

              <StandardTable
                data={inventoryTableData}
                tableKey="all-products-inventory"
                columns={getInventoryColumns()}
                defaultColumnOrder={['product', 'current_stock', 'velocity', 'days_left', 'inventory_age', 'last_cogs', 'reorder_point', 'status', 'actions']}
                renderCell={renderInventoryCell}
                enableSearch={true}
                enableFilters={true}
                enableSorting={true}
                enableColumnReordering={true}
                enableColumnResetting={true}
                enableFullscreen={true}
                searchPlaceholder="Search by ASIN, product name..."
                searchFields={['asin', 'product_name']}
                filters={getInventoryFilters()}
                emptyIcon={Package}
                emptyTitle="No Inventory Data"
                emptyDescription="No inventory information available"
                title="Complete Inventory Analysis"
              />
            </>
          )}

          {!loading && !error && !allProductsData && (
            <div className="text-center py-12">
              <Package className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">No Data Available</h3>
              <p className="text-gray-600">
                Configure your data sources in Settings to see inventory analysis.
              </p>
            </div>
          )}
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