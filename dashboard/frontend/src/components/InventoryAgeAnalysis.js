import React, { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import { 
  Package, 
  Calendar,
  TrendingDown,
  AlertTriangle,
  Clock,
  DollarSign,
  Filter,
  BarChart3,
  Target,
  Zap,
  Info
} from 'lucide-react';
import { useProductImage, useProductImages } from '../hooks/useProductImages';
import StandardTable from './common/StandardTable';

const InventoryAgeAnalysis = () => {
  const [ageData, setAgeData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedCategories, setSelectedCategories] = useState(['all']);
  const [showActionItems, setShowActionItems] = useState(false);

  // Fetch inventory age analysis
  useEffect(() => {
    fetchAgeAnalysis();
  }, []);

  const fetchAgeAnalysis = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await axios.get('/api/analytics/inventory-age', { 
        withCredentials: true 
      });
      
      setAgeData(response.data);
    } catch (err) {
      setError(err.response?.data?.message || 'Failed to load inventory age analysis');
    } finally {
      setLoading(false);
    }
  };

  // Extract ASINs for image loading
  const allAsins = useMemo(() => {
    if (!ageData?.age_analysis) return [];
    return Object.keys(ageData.age_analysis);
  }, [ageData]);

  const { images: batchImages, loading: imagesLoading } = useProductImages(allAsins);

  // Filter products by selected age categories
  const filteredProducts = useMemo(() => {
    if (!ageData?.age_analysis) return [];

    let products = Object.entries(ageData.age_analysis);

    if (!selectedCategories.includes('all')) {
      products = products.filter(([asin, data]) => 
        selectedCategories.includes(data.age_category)
      );
    }

    return products.map(([asin, ageInfo]) => ({
      asin,
      ...ageInfo,
      id: asin
    }));
  }, [ageData, selectedCategories]);

  // Age category stats
  const categoryStats = useMemo(() => {
    if (!ageData?.summary?.categories_breakdown) return {};
    return ageData.summary.categories_breakdown;
  }, [ageData]);

  // Table columns for age analysis
  const tableColumns = {
    product: { 
      key: 'product', 
      label: 'Product', 
      sortKey: 'asin', 
      draggable: false 
    },
    age: { 
      key: 'age', 
      label: 'Age', 
      sortKey: 'estimated_age_days', 
      draggable: true 
    },
    category: { 
      key: 'category', 
      label: 'Category', 
      sortKey: 'age_category', 
      draggable: true 
    },
    confidence: { 
      key: 'confidence', 
      label: 'Confidence', 
      sortKey: 'confidence_score', 
      draggable: true 
    },
    recommendations: { 
      key: 'recommendations', 
      label: 'Recommendations', 
      sortKey: null, 
      draggable: true 
    }
  };

  const defaultColumnOrder = ['product', 'age', 'category', 'confidence', 'recommendations'];

  // Render table cells
  const renderCell = (columnKey, product) => {
    switch (columnKey) {
      case 'product':
        return (
          <td key={columnKey} className="px-3 py-2">
            <div className="flex items-center space-x-3">
              <div className="flex-shrink-0">
                <ProductImage 
                  asin={product.asin}
                  batchImages={batchImages}
                  imagesLoading={imagesLoading}
                />
              </div>
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium text-gray-900 truncate">
                  {product.asin}
                </div>
                <div className="text-xs text-gray-500">
                  {product.data_sources?.join(', ') || 'No data sources'}
                </div>
              </div>
            </div>
          </td>
        );
      
      case 'age':
        return (
          <td key={columnKey} className="px-3 py-2">
            <div className="text-sm font-medium text-gray-900">
              {product.estimated_age_days ? `${product.estimated_age_days} days` : 'Unknown'}
            </div>
            {product.age_range?.variance > 0 && (
              <div className="text-xs text-gray-500">
                Range: {product.age_range.min}-{product.age_range.max} days
              </div>
            )}
          </td>
        );
      
      case 'category':
        return (
          <td key={columnKey} className="px-3 py-2">
            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getCategoryStyles(product.age_category)}`}>
              {getCategoryIcon(product.age_category)}
              <span className="ml-1">{getCategoryLabel(product.age_category)}</span>
            </span>
          </td>
        );
      
      case 'confidence':
        return (
          <td key={columnKey} className="px-3 py-2">
            <div className="flex items-center">
              <div className="w-12 bg-gray-200 rounded-full h-2 mr-2">
                <div 
                  className="bg-blue-600 h-2 rounded-full" 
                  style={{width: `${(product.confidence_score || 0) * 100}%`}}
                ></div>
              </div>
              <span className="text-sm text-gray-600">
                {Math.round((product.confidence_score || 0) * 100)}%
              </span>
            </div>
          </td>
        );
      
      case 'recommendations':
        return (
          <td key={columnKey} className="px-3 py-2">
            <div className="space-y-1">
              {(product.recommendations || []).slice(0, 2).map((rec, idx) => (
                <div key={idx} className="text-xs text-gray-600 bg-gray-50 px-2 py-1 rounded">
                  {rec}
                </div>
              ))}
              {(product.recommendations || []).length > 2 && (
                <div className="text-xs text-blue-600">
                  +{(product.recommendations || []).length - 2} more
                </div>
              )}
            </div>
          </td>
        );
      
      default:
        return <td key={columnKey}></td>;
    }
  };

  const getCategoryStyles = (category) => {
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

  const getCategoryIcon = (category) => {
    const iconProps = { className: 'h-3 w-3' };
    const icons = {
      'fresh': <Zap {...iconProps} />,
      'moderate': <Clock {...iconProps} />,
      'aged': <AlertTriangle {...iconProps} />,
      'old': <TrendingDown {...iconProps} />,
      'ancient': <Target {...iconProps} />,
      'unknown': <Info {...iconProps} />
    };
    return icons[category] || icons.unknown;
  };

  const getCategoryLabel = (category) => {
    if (!ageData?.age_categories?.[category]) return category;
    return ageData.age_categories[category].label;
  };

  // Category filter options
  const filterOptions = useMemo(() => {
    if (!ageData?.age_categories) return [];
    
    return [
      { value: 'all', label: 'All Categories' },
      ...Object.entries(ageData.age_categories).map(([key, config]) => ({
        value: key,
        label: `${config.label} (${categoryStats[key] || 0})`
      }))
    ];
  }, [ageData, categoryStats]);

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <span className="ml-3 text-gray-600">Analyzing inventory age...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <div className="text-center py-8">
          <Package className="h-12 w-12 text-red-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">Analysis Failed</h3>
          <p className="text-gray-600 mb-4">{error}</p>
          <button
            onClick={fetchAgeAnalysis}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            Retry Analysis
          </button>
        </div>
      </div>
    );
  }

  if (!ageData || !ageData.age_analysis) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <div className="text-center py-8">
          <Package className="h-12 w-12 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No Inventory Data</h3>
          <p className="text-gray-600">No inventory found for age analysis.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center">
            <Package className="h-8 w-8 text-blue-600" />
            <div className="ml-4">
              <h3 className="text-lg font-semibold text-gray-900">
                {ageData.summary.total_products}
              </h3>
              <p className="text-sm text-gray-600">Total Products</p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center">
            <Calendar className="h-8 w-8 text-green-600" />
            <div className="ml-4">
              <h3 className="text-lg font-semibold text-gray-900">
                {ageData.summary.average_age_days} days
              </h3>
              <p className="text-sm text-gray-600">Average Age</p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center">
            <BarChart3 className="h-8 w-8 text-orange-600" />
            <div className="ml-4">
              <h3 className="text-lg font-semibold text-gray-900">
                {Math.round(ageData.summary.coverage_percentage)}%
              </h3>
              <p className="text-sm text-gray-600">Data Coverage</p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center">
            <Target className="h-8 w-8 text-red-600" />
            <div className="ml-4">
              <h3 className="text-lg font-semibold text-gray-900">
                {ageData.total_action_items || 0}
              </h3>
              <p className="text-sm text-gray-600">Need Action</p>
            </div>
          </div>
        </div>
      </div>

      {/* Age Category Breakdown */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Inventory Age Breakdown</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
          {Object.entries(categoryStats).map(([category, count]) => {
            if (category === 'unknown') return null;
            const config = ageData.age_categories[category];
            if (!config) return null;
            
            return (
              <div key={category} className="text-center">
                <div 
                  className="w-full h-12 rounded-lg flex items-center justify-center text-white font-semibold text-lg"
                  style={{ backgroundColor: config.color }}
                >
                  {count}
                </div>
                <p className="text-xs text-gray-600 mt-2">{config.label}</p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Action Items Toggle */}
      {ageData.action_items && ageData.action_items.length > 0 && (
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <AlertTriangle className="h-5 w-5 text-orange-600 mr-2" />
              <h3 className="font-semibold text-gray-900">
                {ageData.total_action_items} Products Need Immediate Attention
              </h3>
            </div>
            <button
              onClick={() => setShowActionItems(!showActionItems)}
              className="px-4 py-2 bg-orange-600 text-white rounded-md hover:bg-orange-700 text-sm"
            >
              {showActionItems ? 'Hide' : 'Show'} Action Items
            </button>
          </div>
          
          {showActionItems && (
            <div className="mt-4 space-y-3">
              {ageData.action_items.slice(0, 5).map((item) => (
                <div key={item.asin} className="flex items-center justify-between p-3 bg-orange-50 rounded-lg">
                  <div className="flex items-center space-x-3">
                    <ProductImage asin={item.asin} batchImages={batchImages} imagesLoading={imagesLoading} />
                    <div>
                      <div className="font-medium text-gray-900">{item.asin}</div>
                      <div className="text-sm text-gray-600">
                        {item.age_days} days old • {item.current_stock} units • Urgency: {item.urgency_score}
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-medium text-gray-900">
                      ${(item.estimated_value || 0).toFixed(2)}
                    </div>
                    <div className="text-xs text-gray-500">Estimated Value</div>
                  </div>
                </div>
              ))}
              {ageData.action_items.length > 5 && (
                <p className="text-sm text-gray-600 text-center">
                  +{ageData.action_items.length - 5} more items need attention
                </p>
              )}
            </div>
          )}
        </div>
      )}

      {/* Main Table */}
      <div className="bg-white rounded-lg shadow">
        <div className="px-6 py-4 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-gray-900">Inventory Age Analysis</h3>
            
            {/* Category Filter */}
            <div className="flex items-center space-x-3">
              <Filter className="h-4 w-4 text-gray-500" />
              <select
                value={selectedCategories.includes('all') ? 'all' : selectedCategories[0]}
                onChange={(e) => {
                  const value = e.target.value;
                  setSelectedCategories(value === 'all' ? ['all'] : [value]);
                }}
                className="block w-48 pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm rounded-md"
              >
                {filterOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        <StandardTable
          data={filteredProducts}
          tableKey="inventory-age-analysis"
          columns={tableColumns}
          defaultColumnOrder={defaultColumnOrder}
          renderCell={renderCell}
          enableSearch={true}
          enableFilters={false}
          enableSorting={true}
          enableColumnReordering={true}
          enableColumnResetting={true}
          enableFullscreen={true}
          searchPlaceholder="Search products by ASIN..."
          searchFields={['asin']}
          emptyIcon={Package}
          emptyTitle="No Products Found"
          emptyDescription="No products match the selected age category filters"
          title=""
          className=""
        />
      </div>

      {/* Insights */}
      {ageData.summary.insights && ageData.summary.insights.length > 0 && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h3 className="font-semibold text-blue-900 mb-2 flex items-center">
            <Info className="h-4 w-4 mr-2" />
            Key Insights
          </h3>
          <ul className="space-y-1">
            {ageData.summary.insights.map((insight, idx) => (
              <li key={idx} className="text-sm text-blue-800">{insight}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

// Product Image Component (reused from SmartRestockAlerts)
const ProductImage = ({ asin, batchImages, imagesLoading }) => {
  const [imgError, setImgError] = useState(false);
  const [retryCount, setRetryCount] = useState(0);
  const { imageUrl: fallbackUrl, loading: fallbackLoading } = useProductImage(imgError && retryCount < 2 ? asin : null);
  
  if (!asin) {
    return (
      <div className="h-12 w-12 rounded-lg bg-red-100 border border-red-300 flex items-center justify-center" title="No ASIN provided">
        <span className="text-sm text-red-600">!</span>
      </div>
    );
  }

  const imageUrl = imgError && fallbackUrl ? fallbackUrl : batchImages?.[asin];
  const isLoading = (imagesLoading && !batchImages?.[asin]) || (imgError && fallbackLoading);
  
  if (isLoading) {
    return (
      <div className="h-12 w-12 rounded-lg bg-gray-100 border border-gray-200 flex items-center justify-center" title="Loading image...">
        <div className="h-4 w-4 bg-gray-300 rounded animate-pulse" />
      </div>
    );
  }

  if (!imageUrl || (imgError && !fallbackUrl)) {
    return (
      <div className="h-12 w-12 rounded-lg bg-gradient-to-br from-blue-50 to-indigo-100 border border-blue-200 flex items-center justify-center" 
           title={`Product: ${asin} - ${imgError ? 'Image failed to load' : 'No image available'}`}>
        <Package className="h-6 w-6 text-blue-600" />
      </div>
    );
  }

  return (
    <div className="h-12 w-12 rounded-lg overflow-hidden border border-gray-200 bg-white" title={`Product ${asin}`}>
      <img
        src={imageUrl}
        alt={`Product ${asin}`}
        className="h-full w-full object-cover"
        loading="lazy"
        onError={() => {
          if (retryCount < 2) {
            setRetryCount(prev => prev + 1);
            setImgError(true);
          } else {
            setImgError(true);
          }
        }}
        onLoad={() => {
          setImgError(false);
          setRetryCount(0);
        }}
      />
    </div>
  );
};

export default InventoryAgeAnalysis;