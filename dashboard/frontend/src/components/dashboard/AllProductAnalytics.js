import React, { useState, useEffect, useMemo, useCallback } from 'react';
import axios from 'axios';
import { 
  BarChart3, 
  Package, 
  AlertTriangle,
  Calendar,
  ShoppingCart,
  Clock,
  ExternalLink,
  TrendingUp,
  TrendingDown,
  DollarSign,
  Download,
  Filter,
  Activity
} from 'lucide-react';
import StandardTable from '../common/StandardTable';
// Removed image fetching to improve performance
// import { useProductImages } from '../../hooks/useProductImages';
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
    
    // Add enhanced analytics for mock data with safe calculations
    const currentStock = Math.max(Math.floor(Math.random() * 200) + 10, 1);
    const velocity = Math.max(Math.random() * 5 + 0.5, 0.1);
    const cogs = Math.max(Math.random() * 30 + 5, 1);
    const sellingPrice = Math.max(cogs * (1.5 + Math.random()), cogs + 1);
    const fbaFee = Math.max(sellingPrice * 0.15, 0.01);
    
    enhancedAnalytics[asin] = {
      product_name: `Mock Product ${asin}`,
      current_stock: currentStock,
      velocity: {
        weighted_velocity: velocity,
        velocity_30d: velocity * 0.9,
        velocity_7d: velocity * 1.1
      },
      restock: {
        current_stock: currentStock,
        monthly_purchase_adjustment: Math.floor(Math.random() * 50),
        source: 'mock_data'
      },
      sales_data: {
        units_sold_30d: Math.floor(velocity * 30),
        units_sold_7d: Math.floor(velocity * 7),
        revenue_30d: velocity * 30 * sellingPrice,
        revenue_7d: velocity * 7 * sellingPrice,
        selling_price: sellingPrice,
        fba_fee: fbaFee
      },
      profitability: {
        cogs: cogs,
        profit_margin: sellingPrice > 0 ? Math.max(((sellingPrice - cogs - fbaFee) / sellingPrice) * 100, -100) : 0,
        profit_per_unit: Math.max(sellingPrice - cogs - fbaFee, -cogs),
        roi: cogs > 0 ? Math.max(((sellingPrice - cogs - fbaFee) / cogs) * 100, -100) : 0
      },
      inventory_health: {
        inventory_value: Math.max(currentStock * cogs, 0),
        turnover_rate: currentStock > 0 ? Math.max((velocity * 30) / currentStock, 0) : 0,
        excess_inventory: currentStock > velocity * 90,
        stockout_risk: currentStock < velocity * 14
      },
      ranking: {
        bsr: Math.floor(Math.random() * 100000) + 1000,
        bsr_category: 'Electronics',
        reviews_count: Math.floor(Math.random() * 1000) + 10,
        rating: 3.5 + Math.random() * 1.5
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
  const [selectedMetric, setSelectedMetric] = useState('all');
  const [exportLoading, setExportLoading] = useState(false);

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
            console.log('Error details:', e.message);
            
            // Check if it's a syntax error that might indicate truncation
            if (e.message.includes('Unexpected end of JSON input') || 
                e.message.includes('Unexpected token') ||
                e.message.includes('position')) {
              console.log('JSON parsing failed - likely due to large response size or truncation');
              console.log('Response length:', response.data.length);
              
              // Try to find where the JSON becomes invalid
              let validJson = response.data;
              
              // If the response looks like it starts with valid JSON, try to find where it breaks
              if (response.data.startsWith('{')) {
                // Try parsing progressively smaller chunks to find the largest valid JSON
                let chunkSize = response.data.length;
                let lastValidSize = 0;
                
                while (chunkSize > 1000 && lastValidSize === 0) {
                  try {
                    const chunk = response.data.substring(0, chunkSize);
                    JSON.parse(chunk);
                    lastValidSize = chunkSize;
                    break;
                  } catch (chunkError) {
                    chunkSize = Math.floor(chunkSize * 0.9);
                  }
                }
                
                if (lastValidSize > 0) {
                  console.log(`Found valid JSON up to position ${lastValidSize}`);
                  validJson = response.data.substring(0, lastValidSize);
                }
              }
              
              // Try parsing the potentially truncated but valid JSON
              try {
                const parsed = JSON.parse(validJson);
                console.log('Successfully parsed truncated response');
                console.log('Parsed keys:', Object.keys(parsed));
                response.data = parsed;
              } catch (truncError) {
                console.error('Even truncated parsing failed:', truncError);
                // Fall back to demo mode as last resort for parsing issues
                console.log('Falling back to demo mode due to parsing failure');
                throw e; // Re-throw to trigger demo fallback
              }
            } else {
              throw e; // Re-throw if it's not a truncation issue
            }
          }
        }
        
        // Validate that we got a proper response structure
        if (!response.data || typeof response.data !== 'object') {
          throw new Error('Invalid response structure - not an object');
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
        
        // If we successfully parsed the response and it has the expected structure, use it
        if (response.data.age_analysis || response.data.enhanced_analytics) {
          console.log('✓ Successfully validated response structure');
        } else {
          console.log('⚠️ Response missing expected keys, but proceeding anyway');
        }
        
      } catch (mainError) {
        console.log('Main endpoint failed:', mainError);
        console.log('Error type:', mainError.constructor.name);
        console.log('Error message:', mainError.message);
        
        // Handle specific error types
        if (mainError.response) {
          console.log('HTTP error status:', mainError.response.status);
          console.log('HTTP error data:', mainError.response.data);
          
          // Check for specific Sellerboard URL errors
          const errorData = mainError.response.data;
          if (errorData && errorData.action_required === 'update_sellerboard_urls') {
            // Don't fall back to demo mode for configuration issues
            throw new Error(errorData.message || 'Sellerboard URLs need to be updated');
          }
        }
        
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
      console.log('Setting allProductsData with keys:', Object.keys(response.data || {}));
      console.log('Type of data being set:', typeof response.data);
      
      // At this point, response.data should already be a parsed object
      setAllProductsData(response.data);
      
    } catch (err) {
      console.log('Final error handler:', err);
      
      // Handle specific error messages
      let errorMessage = err.message || err.response?.data?.message || 'Failed to load product data';
      
      // Check for Sellerboard URL errors
      if (err.response?.data?.action_required === 'update_sellerboard_urls') {
        errorMessage = `${err.response.data.message} Go to Settings to update your Sellerboard URLs.`;
      } else if (errorMessage.includes('Sellerboard URLs need to be updated')) {
        errorMessage = `${errorMessage} Please go to Settings to update your Sellerboard URLs.`;
      }
      
      setError(errorMessage);
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

  // Function to handle restock button click - now opens only one link per unique retailer
  const handleRestockClick = async (asin, product) => {
    setSourcesLoading(true);
    
    // Get unique source links (one per retailer) from the product
    const uniqueSourceLinks = product.all_source_links || [];
    const primarySourceLink = product.source_link;
    
    // Collect valid URLs (these are already unique per retailer from backend)
    const validUrls = [];
    
    // Add all unique source links (already filtered by backend to one per retailer)
    uniqueSourceLinks.forEach(link => {
      if (link && link.trim() && link.startsWith('http')) {
        validUrls.push(link.trim());
      }
    });
    
    // Add primary source link if not already included and is valid
    if (primarySourceLink && primarySourceLink.startsWith('http') && !validUrls.includes(primarySourceLink)) {
      validUrls.push(primarySourceLink);
    }
    
    // If we have source links, open them (one per unique retailer)
    if (validUrls.length > 0) {
      validUrls.forEach(url => {
        window.open(url, '_blank');
      });
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

  // Removed image loading for performance
  // const allAsins = useMemo(() => {
  //   if (!allProductsData?.age_analysis) return [];
  //   return Object.keys(allProductsData.age_analysis);
  // }, [allProductsData]);

  // const { images: batchImages, loading: imagesLoading } = useProductImages(allAsins);

  // Export functionality with robust error handling
  const handleExport = useCallback(async (filteredData) => {
    if (!filteredData || filteredData.length === 0) {
      alert('No data to export. Please check your filters and try again.');
      return;
    }

    setExportLoading(true);
    try {
      // Prepare CSV data
      const headers = [
        'ASIN',
        'Product Name',
        'Current Stock',
        'Velocity (per day)',
        'Days Left',
        'Age (days)',
        'Age Category',
        'COGS',
        'Selling Price',
        'Profit Margin %',
        'ROI %',
        'Units Sold (30d)',
        'Revenue (30d)',
        'BSR',
        'Rating',
        'Reviews',
        'Inventory Value',
        'Turnover Rate',
        'Retailer',
        'Status'
      ];
      
      const rows = filteredData.map(item => {
        try {
          return [
            item.asin || '',
            (item.product_name || '').replace(/"/g, '""'), // Escape quotes in product names
            safeNumber(item.current_stock, 0),
            safeNumber(item.velocity, 0).toFixed(2),
            safeNumber(item.days_left, 999),
            safeNumber(item.estimated_age_days, 0),
            item.age_category || 'unknown',
            safeNumber(item.last_cogs, 0).toFixed(2),
            safeNumber(item.selling_price, 0) > 0 ? safeNumber(item.selling_price, 0).toFixed(2) : 'N/A',
            safeNumber(item.profit_margin, 0) > 0 ? safeNumber(item.profit_margin, 0).toFixed(2) : 'N/A',
            safeNumber(item.roi, 0) > 0 ? safeNumber(item.roi, 0).toFixed(2) : 'N/A',
            safeNumber(item.units_sold_30d, 0) > 0 ? safeNumber(item.units_sold_30d, 0) : 'N/A',
            safeNumber(item.revenue_30d, 0) > 0 ? safeNumber(item.revenue_30d, 0).toFixed(2) : 'N/A',
            item.bsr && item.bsr > 0 ? safeNumber(item.bsr, 0) : 'N/A',
            safeNumber(item.rating, 0) > 0 ? safeNumber(item.rating, 0).toFixed(1) : 'N/A',
            safeNumber(item.reviews_count, 0) > 0 ? safeNumber(item.reviews_count, 0) : 'N/A',
            safeNumber(item.inventory_value, 0).toFixed(2),
            safeNumber(item.turnover_rate, 0).toFixed(1),
            (item.retailer_display || 'Unknown').replace(/"/g, '""'), // Escape quotes
            item.status || 'normal'
          ];
        } catch (rowError) {
          console.warn('Error processing row for export:', item.asin, rowError);
          return [
            item.asin || '',
            'Export Error',
            '0', '0', '999', '0', 'unknown', '0', 'N/A', 'N/A', 'N/A', 'N/A', 'N/A', 'N/A', 'N/A', 'N/A', '0', '0', 'Unknown', 'normal'
          ];
        }
      });
      
      // Convert to CSV with proper escaping
      const csvContent = [
        headers.join(','),
        ...rows.map(row => row.map(cell => {
          const cellStr = String(cell);
          // Escape commas, quotes, and newlines
          if (cellStr.includes(',') || cellStr.includes('"') || cellStr.includes('\n')) {
            return `"${cellStr.replace(/"/g, '""')}"`;
          }
          return cellStr;
        }).join(','))
      ].join('\n');
      
      // Validate CSV content
      if (csvContent.length < 100) { // Basic sanity check
        throw new Error('Generated CSV content appears to be too small');
      }
      
      // Download file
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const link = document.createElement('a');
      
      // Check if browser supports download
      if (!link.download !== undefined) {
        throw new Error('Browser does not support file downloads');
      }
      
      const url = URL.createObjectURL(blob);
      link.setAttribute('href', url);
      link.setAttribute('download', `product_analytics_${new Date().toISOString().split('T')[0]}.csv`);
      link.style.visibility = 'hidden';
      document.body.appendChild(link);
      link.click();
      
      // Cleanup
      setTimeout(() => {
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
      }, 100);
      
    } catch (error) {
      console.error('Export failed:', error);
      alert(`Export failed: ${error.message}. Please try again or contact support.`);
    } finally {
      setExportLoading(false);
    }
  }, []);

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

  // Safe number conversion with fallback
  const safeNumber = (value, fallback = 0) => {
    if (value === null || value === undefined || isNaN(Number(value))) {
      return fallback;
    }
    const num = Number(value);
    return isFinite(num) ? num : fallback;
  };

  // Safe division with infinity protection
  const safeDivide = (numerator, denominator, fallback = 999) => {
    const num = safeNumber(numerator, 0);
    const den = safeNumber(denominator, 0);
    if (den === 0) return fallback;
    const result = num / den;
    return isFinite(result) ? result : fallback;
  };

  // Prepare table data for inventory tab
  const inventoryTableData = useMemo(() => {
    if (!allProductsData?.age_analysis) {
      return [];
    }
    
    try {
      return Object.entries(allProductsData.age_analysis).map(([asin, ageInfo]) => {
        // Safe extraction of nested data with null checks
        const enhancedData = allProductsData?.enhanced_analytics?.[asin] || {};
        const velocity = safeNumber(enhancedData?.velocity?.weighted_velocity, 0);
        const currentStock = safeNumber(enhancedData?.current_stock, 0);
        const salesData = enhancedData?.sales_data || {};
        const profitability = enhancedData?.profitability || {};
        const inventoryHealth = enhancedData?.inventory_health || {};
        const ranking = enhancedData?.ranking || {};
        
        // Safe calculations with proper fallbacks
        const cogs = safeNumber(profitability?.cogs || enhancedData?.cogs_data?.cogs, 0);
        const sellingPrice = safeNumber(salesData?.selling_price, 0);
        const profitMargin = safeNumber(profitability?.profit_margin, 0);
        const roi = safeNumber(profitability?.roi, 0);
        const bsr = safeNumber(ranking?.bsr, null);
        const rating = safeNumber(ranking?.rating, 0);
        const reviewsCount = safeNumber(ranking?.reviews_count, 0);
        
        // Safe inventory calculations
        const inventoryValue = safeNumber(inventoryHealth?.inventory_value, 0) || (currentStock * cogs);
        const turnoverRate = safeNumber(inventoryHealth?.turnover_rate, 0) || safeDivide(velocity * 30, currentStock, 0);
        const daysLeft = safeDivide(currentStock, velocity, 999);
        const reorderPoint = safeNumber(enhancedData?.restock?.suggested_quantity, 0) || Math.floor(velocity * 30);
        
        return {
          id: asin,
          asin,
          product_name: enhancedData?.product_name || enhancedData?.cogs_data?.product_name || `Product ${asin}`,
          age_info: ageInfo || {},
          estimated_age_days: safeNumber(ageInfo?.estimated_age_days, 0),
          age_category: ageInfo?.age_category || 'unknown',
          confidence_score: safeNumber(ageInfo?.confidence_score, 0),
          // Basic inventory data
          current_stock: currentStock,
          velocity: velocity,
          amount_ordered: safeNumber(enhancedData?.restock?.monthly_purchase_adjustment, 0),
          days_left: Math.floor(daysLeft),
          reorder_point: Math.floor(reorderPoint),
          // Financial data
          last_cogs: cogs,
          selling_price: sellingPrice,
          profit_margin: profitMargin,
          profit_per_unit: safeNumber(profitability?.profit_per_unit, 0),
          roi: roi,
          // Sales performance
          units_sold_30d: safeNumber(salesData?.units_sold_30d, 0),
          units_sold_7d: safeNumber(salesData?.units_sold_7d, 0),
          revenue_30d: safeNumber(salesData?.revenue_30d, 0),
          revenue_7d: safeNumber(salesData?.revenue_7d, 0),
          velocity_30d: safeNumber(enhancedData?.velocity?.velocity_30d, velocity),
          velocity_7d: safeNumber(enhancedData?.velocity?.velocity_7d, velocity),
          // Inventory health metrics
          inventory_value: inventoryValue,
          turnover_rate: turnoverRate,
          excess_inventory: Boolean(inventoryHealth?.excess_inventory),
          stockout_risk: Boolean(inventoryHealth?.stockout_risk),
          // Amazon ranking and reviews
          bsr: bsr,
          bsr_category: ranking?.bsr_category || 'Unknown',
          reviews_count: reviewsCount,
          rating: rating,
          // Retailer information - now with unique retailers and their source links
          source_link: enhancedData?.source_link || enhancedData?.cogs_data?.source_link || null,
          all_source_links: Array.isArray(enhancedData?.all_source_links) ? enhancedData.all_source_links : [],
          retailer: enhancedData?.retailer || extractRetailerFromUrl(enhancedData?.source_link) || 'Unknown',
          retailer_display: enhancedData?.retailer_display || extractRetailerFromUrl(enhancedData?.source_link) || 'Unknown',
          all_retailers: Array.isArray(enhancedData?.all_retailers) ? enhancedData.all_retailers : ['Unknown'],
          all_retailer_displays: Array.isArray(enhancedData?.all_retailer_displays) ? enhancedData.all_retailer_displays : ['Unknown'],
          retailer_to_source_map: enhancedData?.retailer_to_source_map || {},
          // Status calculation with more nuanced logic
          status: (() => {
            try {
              const ageCategory = ageInfo?.age_category || 'unknown';
              const hasExcess = Boolean(inventoryHealth?.excess_inventory);
              const hasStockoutRisk = Boolean(inventoryHealth?.stockout_risk);
              const lowMargin = profitMargin > 0 && profitMargin < 15;
              
              if (ageCategory === 'ancient' || (hasExcess && velocity < 1)) return 'critical';
              if (ageCategory === 'old' || hasStockoutRisk) return 'warning';
              if (ageCategory === 'aged' || lowMargin) return 'attention';
              return 'normal';
            } catch (statusError) {
              console.warn('Status calculation error for', asin, statusError);
              return 'normal';
            }
          })()
        };
      });
    } catch (error) {
      console.error('Error processing inventory table data:', error);
      return [];
    }
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
      product: { key: 'product', label: 'Product', sortKey: 'product_name', draggable: false, width: 'w-1/4' },
      current_stock: { key: 'current_stock', label: 'Stock', sortKey: 'current_stock', draggable: true, width: 'w-16' },
      velocity: { key: 'velocity', label: 'Velocity', sortKey: 'velocity', draggable: true, width: 'w-20' },
      days_left: { key: 'days_left', label: 'Days Left', sortKey: 'days_left', draggable: true, width: 'w-20' },
      inventory_age: { key: 'inventory_age', label: 'Age', sortKey: 'estimated_age_days', draggable: true, width: 'w-24' },
      // Financial columns
      selling_price: { key: 'selling_price', label: 'Price', sortKey: 'selling_price', draggable: true, width: 'w-18' },
      last_cogs: { key: 'last_cogs', label: 'COGS', sortKey: 'last_cogs', draggable: true, width: 'w-18' },
      profit_margin: { key: 'profit_margin', label: 'Margin %', sortKey: 'profit_margin', draggable: true, width: 'w-20' },
      roi: { key: 'roi', label: 'ROI %', sortKey: 'roi', draggable: true, width: 'w-18' },
      // Sales performance
      units_sold_30d: { key: 'units_sold_30d', label: 'Units (30d)', sortKey: 'units_sold_30d', draggable: true, width: 'w-20' },
      revenue_30d: { key: 'revenue_30d', label: 'Revenue (30d)', sortKey: 'revenue_30d', draggable: true, width: 'w-24' },
      // Amazon metrics
      bsr: { key: 'bsr', label: 'BSR', sortKey: 'bsr', draggable: true, width: 'w-20' },
      rating: { key: 'rating', label: 'Rating', sortKey: 'rating', draggable: true, width: 'w-18' },
      reviews_count: { key: 'reviews_count', label: 'Reviews', sortKey: 'reviews_count', draggable: true, width: 'w-18' },
      // Inventory health
      inventory_value: { key: 'inventory_value', label: 'Inv. Value', sortKey: 'inventory_value', draggable: true, width: 'w-20' },
      turnover_rate: { key: 'turnover_rate', label: 'Turnover', sortKey: 'turnover_rate', draggable: true, width: 'w-20' },
      // Existing columns
      amount_ordered: { key: 'amount_ordered', label: 'Ordered (2mo)', sortKey: 'amount_ordered', draggable: true, width: 'w-20' },
      retailer: { key: 'retailer', label: 'Retailer', sortKey: 'retailer_display', draggable: true, width: 'w-24' },
      reorder_point: { key: 'reorder_point', label: 'Reorder', sortKey: 'reorder_point', draggable: true, width: 'w-20' },
      status: { key: 'status', label: 'Status', sortKey: 'status', draggable: true, width: 'w-20' },
      actions: { key: 'actions', label: 'Actions', sortKey: null, draggable: false, width: 'w-20' }
    };
    return cols;
  }, []);

  // Dynamic column order based on selected metric
  const getColumnOrder = useMemo(() => {
    switch (selectedMetric) {
      case 'inventory':
        return ['product', 'current_stock', 'velocity', 'days_left', 'inventory_age', 'turnover_rate', 'amount_ordered', 'reorder_point', 'retailer', 'status', 'actions'];
      case 'profitability':
        return ['product', 'selling_price', 'last_cogs', 'profit_margin', 'roi', 'revenue_30d', 'units_sold_30d', 'inventory_value', 'status', 'actions'];
      case 'sales':
        return ['product', 'units_sold_30d', 'revenue_30d', 'velocity', 'selling_price', 'profit_margin', 'current_stock', 'status', 'actions'];
      case 'amazon':
        return ['product', 'bsr', 'rating', 'reviews_count', 'units_sold_30d', 'revenue_30d', 'velocity', 'status', 'actions'];
      default:
        return ['product', 'current_stock', 'velocity', 'profit_margin', 'units_sold_30d', 'days_left', 'inventory_age', 'bsr', 'status', 'actions'];
    }
  }, [selectedMetric]);

  const getInsightsColumns = () => ({
    product: { key: 'product', label: 'Product', sortKey: 'product_name', draggable: true },
    insight_type: { key: 'insight_type', label: 'Type', sortKey: 'insight_type', draggable: true },
    recommendation: { key: 'recommendation', label: 'Recommendation', sortKey: null, draggable: true },
    priority: { key: 'priority', label: 'Priority', sortKey: 'priority', draggable: true },
    impact: { key: 'impact', label: 'Impact', sortKey: 'impact_score', draggable: true },
    action: { key: 'action', label: 'Action', sortKey: null, draggable: false }
  });

  const inventoryFilters = useMemo(() => {
    // Extract all unique retailers from all products
    const allRetailers = new Set();
    
    Object.values(allProductsData?.enhanced_analytics || {}).forEach(item => {
      // Add retailers from all_retailer_displays
      if (item.all_retailer_displays && Array.isArray(item.all_retailer_displays)) {
        item.all_retailer_displays.forEach(retailer => {
          if (retailer && retailer !== 'Unknown') {
            allRetailers.add(retailer);
          }
        });
      }
    });
    
    // Convert to sorted array
    const uniqueRetailers = [...allRetailers].sort();
    
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
        filterFn: (item, value) => {
          try {
            if (!item || !value) return false;
            // Check if any of the product's retailers match the filter
            if (item.all_retailer_displays && Array.isArray(item.all_retailer_displays)) {
              return item.all_retailer_displays.some(retailer => retailer === value);
            }
            // Fallback to single retailer check
            return item.retailer_display === value;
          } catch (error) {
            console.warn('Retailer filter error:', error);
            return false;
          }
        }
      },
      {
        key: 'age_category',
        label: 'Age',
        allLabel: 'All Ages',
        options: [
          { value: 'fresh', label: 'Fresh (0-30 days)' },
          { value: 'moderate', label: 'Moderate (31-90 days)' },
          { value: 'aged', label: 'Aged (91-180 days)' },
          { value: 'old', label: 'Old (181-365 days)' },
          { value: 'ancient', label: 'Ancient (365+ days)' },
          { value: 'unknown', label: 'Unknown Age' }
        ],
        filterFn: (item, value) => {
          try {
            return item?.age_category === value;
          } catch (error) {
            console.warn('Age category filter error:', error);
            return false;
          }
        }
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
        filterFn: (item, value) => {
          try {
            return item?.status === value;
          } catch (error) {
            console.warn('Status filter error:', error);
            return false;
          }
        }
      },
      {
        key: 'profit_margin',
        label: 'Margin',
        allLabel: 'All Margins',
        options: [
          { value: 'high', label: 'High (>30%)' },
          { value: 'good', label: 'Good (20-30%)' },
          { value: 'fair', label: 'Fair (10-20%)' },
          { value: 'low', label: 'Low (<10%)' }
        ],
        filterFn: (item, value) => {
          try {
            const margin = safeNumber(item?.profit_margin, 0);
            switch (value) {
              case 'high': return margin > 30;
              case 'good': return margin >= 20 && margin <= 30;
              case 'fair': return margin >= 10 && margin < 20;
              case 'low': return margin < 10;
              default: return true;
            }
          } catch (error) {
            console.warn('Profit margin filter error:', error);
            return false;
          }
        }
      },
      {
        key: 'velocity',
        label: 'Velocity',
        allLabel: 'All Velocities',
        options: [
          { value: 'fast', label: 'Fast (>5/day)' },
          { value: 'good', label: 'Good (2-5/day)' },
          { value: 'slow', label: 'Slow (0.5-2/day)' },
          { value: 'very_slow', label: 'Very Slow (<0.5/day)' }
        ],
        filterFn: (item, value) => {
          try {
            const velocity = safeNumber(item?.velocity, 0);
            switch (value) {
              case 'fast': return velocity > 5;
              case 'good': return velocity >= 2 && velocity <= 5;
              case 'slow': return velocity >= 0.5 && velocity < 2;
              case 'very_slow': return velocity < 0.5;
              default: return true;
            }
          } catch (error) {
            console.warn('Velocity filter error:', error);
            return false;
          }
        }
      },
      {
        key: 'inventory_health',
        label: 'Health',
        allLabel: 'All Health',
        options: [
          { value: 'healthy', label: 'Healthy' },
          { value: 'stockout_risk', label: 'Stockout Risk' },
          { value: 'excess_inventory', label: 'Excess Inventory' },
          { value: 'slow_moving', label: 'Slow Moving' }
        ],
        filterFn: (item, value) => {
          try {
            const stockoutRisk = Boolean(item?.stockout_risk);
            const excessInventory = Boolean(item?.excess_inventory);
            const turnoverRate = safeNumber(item?.turnover_rate, 0);
            const daysLeft = safeNumber(item?.days_left, 999);
            
            switch (value) {
              case 'healthy': return !stockoutRisk && !excessInventory && turnoverRate >= 4;
              case 'stockout_risk': return stockoutRisk || daysLeft < 14;
              case 'excess_inventory': return excessInventory || daysLeft > 90;
              case 'slow_moving': return turnoverRate < 4;
              default: return true;
            }
          } catch (error) {
            console.warn('Inventory health filter error:', error);
            return false;
          }
        }
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

  // Product Image Component - Using only placeholder icons for performance
  const ProductImage = ({ asin }) => {
    return (
      <div className="h-12 w-12 rounded-lg bg-gradient-to-br from-blue-50 to-indigo-100 border border-blue-200 flex items-center justify-center">
        <Package className="h-6 w-6 text-blue-600" />
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

  // Format currency with safe parsing
  const formatCurrency = (amount) => {
    try {
      const num = safeNumber(amount, 0);
      return `$${num.toFixed(2)}`;
    } catch (error) {
      console.warn('Currency formatting error:', error);
      return '$0.00';
    }
  };

  // Format days with safe parsing
  const formatDays = (days) => {
    try {
      const num = safeNumber(days, 0);
      if (num < 1) return '< 1 day';
      if (num === 1) return '1 day';
      return `${Math.round(num)} days`;
    } catch (error) {
      console.warn('Days formatting error:', error);
      return '0 days';
    }
  };

  // Render functions for different tabs
  const renderOverviewCell = (columnKey, item) => (
    <td key={columnKey} className="px-2 py-1.5 whitespace-nowrap text-sm text-gray-900">
      {/* Placeholder for overview data */}
      Coming Soon
    </td>
  );

  const renderPerformanceCell = (columnKey, item) => (
    <td key={columnKey} className="px-2 py-1.5 whitespace-nowrap text-sm text-gray-900">
      {/* Placeholder for performance data */}
      Coming Soon
    </td>
  );

  const renderInventoryCell = (columnKey, item) => {
    try {
      // Safety check for item
      if (!item || typeof item !== 'object') {
        return (
          <td key={columnKey} className="px-2 py-1.5 whitespace-nowrap text-sm text-gray-400">
            -
          </td>
        );
      }

      switch (columnKey) {
      case 'product':
        return (
          <td key={columnKey} className="px-2 py-1.5 h-16">
            <div className="flex items-center space-x-3 h-full">
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
              <div className="min-w-0 flex-1 overflow-hidden">
                <div className="text-sm font-medium text-gray-900 leading-tight">
                  <a 
                    href={`https://www.amazon.com/dp/${item.asin}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="hover:text-blue-600 transition-colors block line-clamp-2 overflow-hidden"
                    title={item.product_name}
                    style={{
                      display: '-webkit-box',
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: 'vertical',
                      overflow: 'hidden',
                      maxHeight: '2.5rem'
                    }}
                  >
                    {item.product_name}
                  </a>
                </div>
                <div className="text-xs text-gray-500 truncate">{item.asin}</div>
              </div>
            </div>
          </td>
        );

      case 'current_stock':
        return (
          <td key={columnKey} className="px-2 py-1.5 whitespace-nowrap text-sm text-gray-900">
            {Math.round(item.current_stock)}
          </td>
        );

      case 'velocity':
        return (
          <td key={columnKey} className="px-2 py-1.5 whitespace-nowrap text-sm text-gray-900">
            {item.velocity.toFixed(1)}/day
          </td>
        );

      case 'amount_ordered':
        return (
          <td key={columnKey} className="px-2 py-1.5 whitespace-nowrap text-sm">
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
          <td key={columnKey} className="px-2 py-1.5 whitespace-nowrap text-sm text-gray-900">
            {formatDays(item.days_left)}
          </td>
        );

      case 'inventory_age':
        return (
          <td key={columnKey} className="px-2 py-1.5 whitespace-nowrap">
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
          <td key={columnKey} className="px-2 py-1.5 whitespace-nowrap text-sm">
            <div className="text-green-700 font-medium">
              {formatCurrency(item.last_cogs)}
            </div>
          </td>
        );

      case 'retailer':
        return (
          <td key={columnKey} className="px-2 py-1.5 whitespace-normal text-sm">
            <div className="flex flex-wrap gap-1">
              {item.all_retailer_displays && item.all_retailer_displays.length > 0 && item.all_retailer_displays[0] !== 'Unknown' ? (
                item.all_retailer_displays.map((retailerDisplay, idx) => {
                  // Get the corresponding retailer key and its source link
                  const retailerKey = item.all_retailers?.[idx];
                  const sourceLink = item.retailer_to_source_map?.[retailerKey] || item.all_source_links?.[idx] || item.source_link;
                  
                  return (
                    <a 
                      key={`${retailerDisplay}-${idx}`}
                      href={sourceLink || '#'}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center px-2 py-1 bg-blue-100 text-blue-800 text-xs font-medium rounded-md hover:bg-blue-200 transition-colors"
                      title={`View on ${retailerDisplay}`}
                      onClick={sourceLink ? undefined : (e) => e.preventDefault()}
                    >
                      <ExternalLink className="h-3 w-3 mr-1" />
                      {retailerDisplay}
                    </a>
                  );
                })
              ) : (
                <span className="text-gray-400">Unknown</span>
              )}
            </div>
          </td>
        );

      case 'reorder_point':
        return (
          <td key={columnKey} className="px-2 py-1.5 whitespace-nowrap text-sm text-gray-900">
            {Math.round(item.reorder_point)}
          </td>
        );

      case 'status':
        return (
          <td key={columnKey} className="px-2 py-1.5 whitespace-nowrap">
            <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${getStatusStyles(item.status)}`}>
              {item.status === 'critical' && <AlertTriangle className="h-3 w-3 mr-1" />}
              {item.status === 'warning' && <Clock className="h-3 w-3 mr-1" />}
              {item.status.charAt(0).toUpperCase() + item.status.slice(1)}
            </span>
          </td>
        );

      case 'selling_price':
        return (
          <td key={columnKey} className="px-2 py-1.5 whitespace-nowrap text-sm">
            <div className="text-blue-700 font-medium">
              {item.selling_price > 0 ? formatCurrency(item.selling_price) : '-'}
            </div>
          </td>
        );

      case 'profit_margin':
        return (
          <td key={columnKey} className="px-2 py-1.5 whitespace-nowrap text-sm">
            {item.profit_margin > 0 ? (
              <div className="flex items-center space-x-1">
                {item.profit_margin > 25 ? (
                  <TrendingUp className="h-3 w-3 text-green-600" />
                ) : item.profit_margin < 10 ? (
                  <TrendingDown className="h-3 w-3 text-red-600" />
                ) : (
                  <Activity className="h-3 w-3 text-yellow-600" />
                )}
                <span className={`font-medium ${
                  item.profit_margin > 25 ? 'text-green-700' :
                  item.profit_margin < 10 ? 'text-red-700' : 'text-yellow-700'
                }`}>
                  {safeNumber(item.profit_margin, 0).toFixed(1)}%
                </span>
              </div>
            ) : (
              <span className="text-gray-400">-</span>
            )}
          </td>
        );

      case 'roi':
        return (
          <td key={columnKey} className="px-2 py-1.5 whitespace-nowrap text-sm">
            {item.roi > 0 ? (
              <div className={`font-medium ${
                item.roi > 50 ? 'text-green-700' :
                item.roi < 20 ? 'text-red-700' : 'text-yellow-700'
              }`}>
                {safeNumber(item.roi, 0).toFixed(1)}%
              </div>
            ) : (
              <span className="text-gray-400">-</span>
            )}
          </td>
        );

      case 'units_sold_30d':
        return (
          <td key={columnKey} className="px-2 py-1.5 whitespace-nowrap text-sm text-gray-900">
            {safeNumber(item.units_sold_30d, 0) > 0 ? safeNumber(item.units_sold_30d, 0).toLocaleString() : '-'}
          </td>
        );

      case 'revenue_30d':
        return (
          <td key={columnKey} className="px-2 py-1.5 whitespace-nowrap text-sm">
            <div className="text-green-700 font-medium">
              {item.revenue_30d > 0 ? formatCurrency(safeNumber(item.revenue_30d, 0)) : '-'}
            </div>
          </td>
        );

      case 'bsr':
        return (
          <td key={columnKey} className="px-2 py-1.5 whitespace-nowrap text-sm">
            {item.bsr && item.bsr > 0 ? (
              <div className="flex items-center space-x-1">
                <span className={`font-medium ${
                  item.bsr < 10000 ? 'text-green-700' :
                  item.bsr < 50000 ? 'text-yellow-700' : 'text-red-700'
                }`}>
                  #{safeNumber(item.bsr, 0).toLocaleString()}
                </span>
              </div>
            ) : (
              <span className="text-gray-400">-</span>
            )}
          </td>
        );

      case 'rating':
        return (
          <td key={columnKey} className="px-2 py-1.5 whitespace-nowrap text-sm">
            {item.rating > 0 ? (
              <div className="flex items-center space-x-1">
                <span className={`font-medium ${
                  item.rating >= 4.5 ? 'text-green-700' :
                  item.rating >= 4.0 ? 'text-yellow-700' : 'text-red-700'
                }`}>
                  {safeNumber(item.rating, 0).toFixed(1)}
                </span>
                <span className="text-yellow-500">★</span>
              </div>
            ) : (
              <span className="text-gray-400">-</span>
            )}
          </td>
        );

      case 'reviews_count':
        return (
          <td key={columnKey} className="px-2 py-1.5 whitespace-nowrap text-sm text-gray-900">
            {safeNumber(item.reviews_count, 0) > 0 ? safeNumber(item.reviews_count, 0).toLocaleString() : '-'}
          </td>
        );

      case 'inventory_value':
        return (
          <td key={columnKey} className="px-2 py-1.5 whitespace-nowrap text-sm">
            <div className="text-purple-700 font-medium">
              {formatCurrency(safeNumber(item.inventory_value, 0))}
            </div>
          </td>
        );

      case 'turnover_rate':
        return (
          <td key={columnKey} className="px-2 py-1.5 whitespace-nowrap text-sm">
            <div className={`font-medium ${
              item.turnover_rate > 6 ? 'text-green-700' :
              item.turnover_rate > 4 ? 'text-yellow-700' : 'text-red-700'
            }`}>
              {safeNumber(item.turnover_rate, 0).toFixed(1)}x
            </div>
          </td>
        );

      case 'actions':
        return (
          <td key={columnKey} className="px-2 py-1.5 whitespace-nowrap">
            <button
              onClick={() => handleRestockClick(item.asin, item)}
              className="inline-flex items-center px-2 py-1 bg-blue-600 text-white text-xs rounded-md hover:bg-blue-700 transition-colors disabled:opacity-50"
              disabled={sourcesLoading}
              title={item.all_source_links?.length > 0 ? `Open ${item.all_source_links.length} retailer link(s)` : "Find purchase sources"}
            >
              <ShoppingCart className="h-3 w-3 mr-1" />
              Restock
            </button>
          </td>
        );

      default:
        return (
          <td key={columnKey} className="px-2 py-1.5 whitespace-nowrap text-sm text-gray-900">
            -
          </td>
        );
      }
    } catch (error) {
      console.warn('Render cell error for column:', columnKey, error);
      return (
        <td key={columnKey} className="px-2 py-1.5 whitespace-nowrap text-sm text-red-400">
          Error
        </td>
      );
    }
  };

  const renderInsightsCell = (columnKey, item) => (
    <td key={columnKey} className="px-2 py-1.5 whitespace-nowrap text-sm text-gray-900">
      {/* Placeholder for insights data */}
      Coming Soon
    </td>
  );


  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <BarChart3 className="h-8 w-8 text-builders-500" />
          <div>
            <h1 className="text-2xl font-bold text-gray-900">All Product Analytics</h1>
            <p className="text-gray-600">Comprehensive analytics dashboard for all your products</p>
          </div>
        </div>
        
        {/* Header Controls */}
        {!loading && !error && allProductsData && allProductsData.age_analysis && (
          <div className="flex items-center space-x-3">
            {/* Metric Selector */}
            <div className="flex items-center space-x-2">
              <Filter className="h-4 w-4 text-gray-500" />
              <select
                value={selectedMetric}
                onChange={(e) => setSelectedMetric(e.target.value)}
                className="text-sm border border-gray-300 rounded-md px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="all">All Metrics</option>
                <option value="inventory">Inventory Focus</option>
                <option value="profitability">Profitability Focus</option>
                <option value="sales">Sales Performance</option>
                <option value="amazon">Amazon Metrics</option>
              </select>
            </div>
            
            {/* Export Button */}
            <button
              onClick={() => handleExport(inventoryTableData)}
              disabled={exportLoading}
              className="inline-flex items-center px-3 py-1.5 bg-green-600 text-white text-sm rounded-md hover:bg-green-700 transition-colors disabled:opacity-50"
              title="Export filtered data to CSV"
            >
              <Download className="h-4 w-4 mr-2" />
              {exportLoading ? 'Exporting...' : 'Export CSV'}
            </button>
          </div>
        )}
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

                {/* Quick Action Cards */}
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
                  <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="text-lg font-semibold text-red-900">
                          {inventoryTableData.filter(item => item.status === 'critical').length}
                        </div>
                        <div className="text-sm text-red-700">Critical Issues</div>
                      </div>
                      <AlertTriangle className="h-8 w-8 text-red-600" />
                    </div>
                    <div className="text-xs text-red-600 mt-2">Needs immediate attention</div>
                  </div>
                  
                  <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="text-lg font-semibold text-yellow-900">
                          {inventoryTableData.filter(item => item.stockout_risk || item.days_left < 14).length}
                        </div>
                        <div className="text-sm text-yellow-700">Low Stock</div>
                      </div>
                      <Clock className="h-8 w-8 text-yellow-600" />
                    </div>
                    <div className="text-xs text-yellow-600 mt-2">Under 14 days left</div>
                  </div>
                  
                  <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="text-lg font-semibold text-purple-900">
                          {inventoryTableData.filter(item => item.days_left <= 30 && item.days_left > 14).length}
                        </div>
                        <div className="text-sm text-purple-700">Restock Soon</div>
                      </div>
                      <ShoppingCart className="h-8 w-8 text-purple-600" />
                    </div>
                    <div className="text-xs text-purple-600 mt-2">14-30 days of stock left</div>
                  </div>
                  
                  <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="text-lg font-semibold text-blue-900">
                          ${inventoryTableData.reduce((sum, item) => sum + (item.inventory_value || 0), 0).toLocaleString()}
                        </div>
                        <div className="text-sm text-blue-700">Total Inventory</div>
                      </div>
                      <DollarSign className="h-8 w-8 text-blue-600" />
                    </div>
                    <div className="text-xs text-blue-600 mt-2">Current inventory value</div>
                  </div>
                </div>
              </div>

              <StandardTable
                data={inventoryTableData}
                tableKey="all-products-inventory"
                columns={inventoryColumns}
                defaultColumnOrder={getColumnOrder}
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