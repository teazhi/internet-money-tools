import React, { useState, useEffect, useMemo, useCallback } from 'react';
import axios from 'axios';
import { 
  BarChart3, 
  Package, 
  AlertTriangle,
  Calendar,
  ShoppingCart,
  Clock,
  ExternalLink
} from 'lucide-react';
import StandardTable from '../common/StandardTable';
import { useProductImages } from '../../hooks/useProductImages';
import { API_ENDPOINTS } from '../../config/api';

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
  const enhancedAnalytics = {};
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
    
    // Add enhanced analytics for mock data
    const currentStock = Math.floor(Math.random() * 200) + 10;
    enhancedAnalytics[asin] = {
      product_name: `Mock Product ${asin}`,
      current_stock: currentStock,
      velocity: {
        weighted_velocity: Math.random() * 5 + 0.5
      },
      restock: {
        current_stock: currentStock,
        monthly_purchase_adjustment: Math.floor(Math.random() * 50),
        source: 'mock_data'
      }
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
    fallback_mode: true,
    enhanced_analytics: enhancedAnalytics
  };
};

const AllProductAnalytics = () => {
  const [allProductsData, setAllProductsData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [sourcesLoading, setSourcesLoading] = useState(false);

  // Fetch comprehensive product data
  const fetchAllProductsData = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Try main endpoint first, fallback to demo, then fallback to mock data
      let response;
      try {
        console.log('Calling endpoint:', API_ENDPOINTS.ANALYTICS_INVENTORY_AGE);
        response = await axios.get(API_ENDPOINTS.ANALYTICS_INVENTORY_AGE, { 
          withCredentials: true
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
            console.log('Response appears to be truncated at 164KB limit');
            
            // If response is truncated, try to use demo mode as fallback
            console.log('Falling back to demo mode due to truncated response');
            try {
              response = await axios.get(API_ENDPOINTS.DEMO_ANALYTICS_INVENTORY_AGE, { 
                withCredentials: true 
              });
              console.log('✓ Successfully loaded demo inventory age data as fallback');
            } catch (demoError) {
              console.log('Demo endpoint also failed, using local mock data');
              response = {
                data: generateMockInventoryData()
              };
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
          response = await axios.get(API_ENDPOINTS.DEMO_ANALYTICS_INVENTORY_AGE, { 
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
      
      // Debug what we're setting
      console.log('Setting allProductsData with:', response.data);
      console.log('Type of data being set:', typeof response.data);
      
      // Ensure we have an object, not a string
      let dataToSet = response.data;
      if (typeof response.data === 'string') {
        console.log('Response data is a string, parsing it...');
        try {
          dataToSet = JSON.parse(response.data);
          console.log('Successfully parsed response data');
        } catch (e) {
          console.error('Failed to parse response data:', e);
          // Use mock data as fallback
          dataToSet = generateMockInventoryData();
        }
      }
      
      
      setAllProductsData(dataToSet);
      
    } catch (err) {
      setError(err.response?.data?.message || 'Failed to load product data');
    } finally {
      setLoading(false);
    }
  };

  // Function to extract URLs from a text string
  const extractUrlsFromText = (text) => {
    if (!text) return [];
    
    // Handle URLs that might be separated by spaces, semicolons, commas, or newlines
    const urlRegex = /https?:\/\/[^\s;,\n]+/gi;
    const urls = text.match(urlRegex) || [];
    
    // Clean URLs (remove trailing punctuation)
    return urls.map(url => url.replace(/[.,;]+$/, ''));
  };

  // Function to handle restock button click
  const handleRestockClick = async (asin, existingSourceLink) => {
    setSourcesLoading(true);
    
    // Strategy: Use existing source link immediately if available, then try to enhance with backend data
    const extractedUrls = extractUrlsFromText(existingSourceLink);
    
    // If we have a direct source link, open it immediately
    if (extractedUrls.length > 0) {
      extractedUrls.forEach(url => {
        window.open(url, '_blank');
      });
      setSourcesLoading(false);
      return;
    } else if (existingSourceLink && existingSourceLink.startsWith('http')) {
      // Direct URL in source link
      window.open(existingSourceLink, '_blank');
      setSourcesLoading(false);
      return;
    }
    
    // If no direct source link available, try backend API (this might be slow)
    try {
      const response = await axios.get(`/api/asin/${asin}/purchase-sources`, { withCredentials: true });
      const backendSources = response.data.sources || [];
      
      if (backendSources.length > 0) {
        backendSources.forEach(source => {
          window.open(source.url, '_blank');
        });
      } else {
        // Last resort: open Amazon product page
        window.open(`https://www.amazon.com/dp/${asin}`, '_blank');
      }
    } catch (error) {
      console.log('Backend source lookup failed, opening Amazon page:', error);
      // Fallback to Amazon product page
      window.open(`https://www.amazon.com/dp/${asin}`, '_blank');
    } finally {
      setSourcesLoading(false);
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

  // Extract retailer name from URL
  const extractRetailerFromUrl = useCallback((url) => {
    if (!url || typeof url !== 'string') return null;
    
    try {
      // Handle URLs with or without protocol
      const urlPattern = /(?:https?:\/\/)?(?:www\.)?([^\/\.\s]+)(?:\.[^\/\s]+)/;
      const match = url.match(urlPattern);
      
      if (match && match[1]) {
        // Extract the domain name before the TLD
        const domain = match[1].toLowerCase();
        
        // Capitalize first letter for display
        return domain.charAt(0).toUpperCase() + domain.slice(1);
      }
    } catch (e) {
      console.error('Error extracting retailer from URL:', e);
    }
    
    return null;
  }, []);

  // Prepare table data for inventory tab
  const inventoryTableData = useMemo(() => {
    if (!allProductsData?.age_analysis) {
      return [];
    }
    
    
    return Object.entries(allProductsData.age_analysis).map(([asin, ageInfo]) => ({
      id: asin,
      asin,
      product_name: allProductsData?.enhanced_analytics?.[asin]?.product_name || 
                   `Product ${asin}`,
      age_info: ageInfo,
      estimated_age_days: ageInfo.estimated_age_days || 0,
      age_category: ageInfo.age_category || 'unknown',
      confidence_score: ageInfo.confidence_score || 0,
      // Get real inventory data - current_stock should come directly from enhanced_analytics
      current_stock: allProductsData?.enhanced_analytics?.[asin]?.current_stock || 0,
      velocity: allProductsData?.enhanced_analytics?.[asin]?.velocity?.weighted_velocity || 0,
      amount_ordered: allProductsData?.enhanced_analytics?.[asin]?.restock?.monthly_purchase_adjustment || 0,
      days_left: Math.floor(Math.random() * 180) + 5,
      reorder_point: Math.floor(Math.random() * 50) + 10,
      last_cogs: Math.random() * 50 + 10,
      supplier_info: 'Various',
      // Retailer information extracted from source link
      source_link: allProductsData?.enhanced_analytics?.[asin]?.source_link || 
                   allProductsData?.enhanced_analytics?.[asin]?.cogs_data?.source_link || null,
      retailer: extractRetailerFromUrl(
        allProductsData?.enhanced_analytics?.[asin]?.source_link || 
        allProductsData?.enhanced_analytics?.[asin]?.cogs_data?.source_link
      ) || 'Unknown',
      retailer_display: extractRetailerFromUrl(
        allProductsData?.enhanced_analytics?.[asin]?.source_link || 
        allProductsData?.enhanced_analytics?.[asin]?.cogs_data?.source_link
      ) || 'Unknown',
      status: ageInfo.age_category === 'ancient' ? 'critical' : 
              ageInfo.age_category === 'old' ? 'warning' :
              ageInfo.age_category === 'aged' ? 'attention' : 'normal'
    }));
  }, [allProductsData, extractRetailerFromUrl]);

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

  const inventoryColumns = useMemo(() => {
    const cols = {
      product: { key: 'product', label: 'Product', sortKey: 'product_name', draggable: false, width: 'w-1/3' },
      current_stock: { key: 'current_stock', label: 'Stock', sortKey: 'current_stock', draggable: true, width: 'w-16' },
      velocity: { key: 'velocity', label: 'Velocity', sortKey: 'velocity', draggable: true, width: 'w-20' },
      amount_ordered: { key: 'amount_ordered', label: 'Ordered (2mo)', sortKey: 'amount_ordered', draggable: true, width: 'w-20' },
      days_left: { key: 'days_left', label: 'Days Left', sortKey: 'days_left', draggable: true, width: 'w-20' },
      inventory_age: { key: 'inventory_age', label: 'Age', sortKey: 'estimated_age_days', draggable: true, width: 'w-24' },
      last_cogs: { key: 'last_cogs', label: 'COGS', sortKey: 'last_cogs', draggable: true, width: 'w-20' },
      retailer: { key: 'retailer', label: 'Retailer', sortKey: 'retailer_display', draggable: true, width: 'w-24' },
      reorder_point: { key: 'reorder_point', label: 'Reorder', sortKey: 'reorder_point', draggable: true, width: 'w-20' },
      status: { key: 'status', label: 'Status', sortKey: 'status', draggable: true, width: 'w-20' },
      actions: { key: 'actions', label: 'Actions', sortKey: null, draggable: false, width: 'w-20' }
    };
    return cols;
  }, []);

  const getInsightsColumns = () => ({
    product: { key: 'product', label: 'Product', sortKey: 'product_name', draggable: true },
    insight_type: { key: 'insight_type', label: 'Type', sortKey: 'insight_type', draggable: true },
    recommendation: { key: 'recommendation', label: 'Recommendation', sortKey: null, draggable: true },
    priority: { key: 'priority', label: 'Priority', sortKey: 'priority', draggable: true },
    impact: { key: 'impact', label: 'Impact', sortKey: 'impact_score', draggable: true },
    action: { key: 'action', label: 'Action', sortKey: null, draggable: false }
  });

  const inventoryFilters = useMemo(() => {
    // Extract retailers directly from source links
    const allSourceLinks = Object.values(allProductsData?.enhanced_analytics || {})
      .map(item => item.source_link || item.cogs_data?.source_link)
      .filter(link => link && typeof link === 'string');
    
    // Extract unique retailer names from URLs
    const uniqueRetailers = [...new Set(
      allSourceLinks
        .map(link => extractRetailerFromUrl(link))
        .filter(retailer => retailer !== null)
    )].sort();
    
    const retailerOptions = uniqueRetailers.map(retailer => ({
      value: retailer,
      label: retailer
    }));

    return [
      {
        key: 'retailer_display',
        label: 'Retailer',
        allLabel: 'All Retailers',
        options: retailerOptions,
        filterFn: (item, value) => item.retailer_display === value
      },
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
  }, [allProductsData?.enhanced_analytics, extractRetailerFromUrl]);

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
    <td key={columnKey} className="px-2 py-1.5 whitespace-nowrap text-sm text-gray-900 border-r border-gray-200">
      {/* Placeholder for overview data */}
      Coming Soon
    </td>
  );

  const renderPerformanceCell = (columnKey, item) => (
    <td key={columnKey} className="px-2 py-1.5 whitespace-nowrap text-sm text-gray-900 border-r border-gray-200">
      {/* Placeholder for performance data */}
      Coming Soon
    </td>
  );

  const renderInventoryCell = (columnKey, item) => {
    switch (columnKey) {
      case 'product':
        return (
          <td key={columnKey} className="px-2 py-1.5 border-r border-gray-200">
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
          <td key={columnKey} className="px-2 py-1.5 whitespace-nowrap text-sm text-gray-900 border-r border-gray-200">
            {Math.round(item.current_stock)}
          </td>
        );

      case 'velocity':
        return (
          <td key={columnKey} className="px-2 py-1.5 whitespace-nowrap text-sm text-gray-900 border-r border-gray-200">
            {item.velocity.toFixed(1)}/day
          </td>
        );

      case 'amount_ordered':
        return (
          <td key={columnKey} className="px-2 py-1.5 whitespace-nowrap text-sm border-r border-gray-200">
            {item.amount_ordered > 0 ? (
              <div className="flex items-center space-x-1">
                <ShoppingCart className="h-3 w-3 text-purple-600" />
                <span className="text-purple-700 font-medium">
                  {item.amount_ordered}
                </span>
              </div>
            ) : (
              <span className="text-gray-400">-</span>
            )}
          </td>
        );

      case 'days_left':
        return (
          <td key={columnKey} className="px-2 py-1.5 whitespace-nowrap text-sm text-gray-900 border-r border-gray-200">
            {formatDays(item.days_left)}
          </td>
        );

      case 'inventory_age':
        return (
          <td key={columnKey} className="px-2 py-1.5 whitespace-nowrap border-r border-gray-200">
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
          <td key={columnKey} className="px-2 py-1.5 whitespace-nowrap text-sm border-r border-gray-200">
            <div className="text-green-700 font-medium">
              {formatCurrency(item.last_cogs)}
            </div>
          </td>
        );

      case 'retailer':
        return (
          <td key={columnKey} className="px-2 py-1.5 whitespace-nowrap text-sm border-r border-gray-200">
            <div className="flex items-center space-x-2">
              {item.source_link ? (
                <a 
                  href={item.source_link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center px-2 py-1 bg-blue-100 text-blue-800 text-xs font-medium rounded-md hover:bg-blue-200 transition-colors"
                  title={`View on ${item.retailer_display}`}
                >
                  <ExternalLink className="h-3 w-3 mr-1" />
                  {item.retailer_display}
                </a>
              ) : (
                <span className="text-gray-400">Unknown</span>
              )}
            </div>
          </td>
        );

      case 'reorder_point':
        return (
          <td key={columnKey} className="px-2 py-1.5 whitespace-nowrap text-sm text-gray-900 border-r border-gray-200">
            {Math.round(item.reorder_point)}
          </td>
        );

      case 'status':
        return (
          <td key={columnKey} className="px-2 py-1.5 whitespace-nowrap border-r border-gray-200">
            <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${getStatusStyles(item.status)}`}>
              {item.status === 'critical' && <AlertTriangle className="h-3 w-3 mr-1" />}
              {item.status === 'warning' && <Clock className="h-3 w-3 mr-1" />}
              {item.status.charAt(0).toUpperCase() + item.status.slice(1)}
            </span>
          </td>
        );

      case 'actions':
        return (
          <td key={columnKey} className="px-2 py-1.5 whitespace-nowrap">
            <button
              onClick={() => handleRestockClick(item.asin, allProductsData?.enhanced_analytics?.[item.asin]?.cogs_data?.source_link || null)}
              className="inline-flex items-center px-2 py-1 bg-blue-600 text-white text-xs rounded-md hover:bg-blue-700 transition-colors disabled:opacity-50"
              disabled={sourcesLoading}
              title={allProductsData?.enhanced_analytics?.[item.asin]?.cogs_data?.source_link ? "Open supplier link" : "Find purchase sources"}
            >
              <ShoppingCart className="h-3 w-3 mr-1" />
              Restock
            </button>
          </td>
        );

      default:
        return (
          <td key={columnKey} className="px-2 py-1.5 whitespace-nowrap text-sm text-gray-900 border-r border-gray-200">
            -
          </td>
        );
    }
  };

  const renderInsightsCell = (columnKey, item) => (
    <td key={columnKey} className="px-2 py-1.5 whitespace-nowrap text-sm text-gray-900 border-r border-gray-200">
      {/* Placeholder for insights data */}
      Coming Soon
    </td>
  );


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


      {/* Main Content */}
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

          {!loading && !error && allProductsData && allProductsData.age_analysis && (
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
                columns={inventoryColumns}
                defaultColumnOrder={['product', 'current_stock', 'velocity', 'amount_ordered', 'days_left', 'inventory_age', 'last_cogs', 'retailer', 'reorder_point', 'status', 'actions']}
                renderCell={renderInventoryCell}
                enableSearch={true}
                enableFilters={true}
                enableSorting={true}
                enableColumnReordering={true}
                enableColumnResetting={true}
                enableFullscreen={true}
                searchPlaceholder="Search by ASIN, product name..."
                searchFields={['asin', 'product_name', 'retailer_display']}
                filters={inventoryFilters}
                emptyIcon={Package}
                emptyTitle="No Inventory Data"
                emptyDescription="No inventory information available"
                title="Complete Inventory Analysis"
              />
            </>
          )}

          {!loading && !error && (!allProductsData || !allProductsData.age_analysis) && (
            <div className="text-center py-12">
              <Package className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">No Data Available</h3>
              <p className="text-gray-600">
                {allProductsData && !allProductsData.age_analysis ? 
                  'Invalid data format received. The response may have been truncated.' :
                  'Configure your data sources in Settings to see inventory analysis.'}
              </p>
              {allProductsData && !allProductsData.age_analysis && (
                <button
                  onClick={fetchAllProductsData}
                  className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
                >
                  Retry with Demo Data
                </button>
              )}
            </div>
          )}
        </div>
    </div>
  );
};

export default AllProductAnalytics;