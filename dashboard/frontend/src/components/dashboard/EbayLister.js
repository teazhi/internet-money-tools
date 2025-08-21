import React, { useState } from 'react';
import { 
  Search, 
  Package, 
  ExternalLink, 
  AlertTriangle,
  RefreshCw
} from 'lucide-react';
import axios from 'axios';

const EbayLister = () => {
  const [asin, setAsin] = useState('');
  const [loading, setLoading] = useState(false);
  const [productData, setProductData] = useState(null);
  const [error, setError] = useState('');

  const validateASIN = (asin) => {
    const asinPattern = /^[A-Z0-9]{10}$/;
    return asinPattern.test(asin.trim().toUpperCase());
  };

  const fetchProductData = async () => {
    if (!validateASIN(asin)) {
      setError('Please enter a valid ASIN (10 characters, letters and numbers only)');
      return;
    }

    setLoading(true);
    setError('');
    setProductData(null);

    try {
      // This would connect to your existing product data API
      const response = await axios.get(`/api/products/asin/${asin.trim().toUpperCase()}`, {
        withCredentials: true
      });

      console.log('eBay Lister Frontend: Received response:', response.data);

      if (response.data.success === true) {
        console.log('eBay Lister Frontend: Success! Setting product data');
        setProductData(response.data.product);
        setError(''); // Clear any previous errors
        // Show warning if there was a Sellerboard issue
        if (response.data.warning) {
          setError(`Warning: ${response.data.warning}`);
        }
      } else {
        console.log('eBay Lister Frontend: Response indicated failure, success value:', response.data.success);
        setError(response.data.message || 'Product not found');
      }
    } catch (err) {
      if (err.response?.status === 404) {
        const message = err.response.data?.message || 'Product not found. Please verify the ASIN is correct.';
        const debugInfo = err.response.data?.debug_info;
        
        if (debugInfo) {
          setError(`${message}\n\nDebug Info:\n- Total products in inventory: ${debugInfo.total_products}\n- Sample ASINs: ${debugInfo.sample_asins?.join(', ')}`);
        } else {
          setError(message);
        }
      } else if (err.response?.status === 400) {
        setError(err.response.data?.message || 'Configuration error. Please check your Sellerboard setup in Settings.');
      } else if (err.response?.data?.message) {
        setError(err.response.data.message);
      } else {
        setError('Failed to fetch product data. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };



  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      fetchProductData();
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-purple-500 to-purple-600 rounded-lg p-6 text-white">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-white/20 rounded-lg">
            <Package className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">eBay Research Tool</h1>
            <p className="text-purple-100">Research products and create eBay listings</p>
          </div>
        </div>
      </div>

      {/* ASIN Input */}
      <div className="card">
        <h2 className="heading-md mb-4">Enter Product ASIN</h2>
        <div className="flex space-x-3">
          <div className="flex-1">
            <input
              type="text"
              value={asin}
              onChange={(e) => setAsin(e.target.value.toUpperCase())}
              onKeyPress={handleKeyPress}
              placeholder="B08XYZABC1 (Enter 10-character ASIN)"
              className="input-field"
              maxLength={10}
              disabled={loading}
            />
            {error && (
              <div className="flex items-center mt-2 text-red-600">
                <AlertTriangle className="h-4 w-4 mr-1" />
                <span className="text-sm">{error}</span>
              </div>
            )}
          </div>
          <button
            onClick={fetchProductData}
            disabled={loading || !asin.trim()}
            className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
          >
            {loading ? (
              <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Search className="h-4 w-4 mr-2" />
            )}
            Lookup Product
          </button>
        </div>
      </div>

      {/* Product Information */}
      {productData && (
        <div className="card">
          <h3 className="heading-sm mb-4">Product Information</h3>
          <div className="grid md:grid-cols-2 gap-6">
            <div className="space-y-4">
              <div>
                <label className="label-text">Product Title</label>
                <p className="body-text text-gray-900 font-medium">{productData.title}</p>
              </div>
              
              <div>
                <label className="label-text">ASIN</label>
                <p className="body-text text-gray-900">{productData.asin}</p>
              </div>
              
              <div>
                <label className="label-text">Brand</label>
                <p className="body-text text-gray-900">{productData.brand || 'N/A'}</p>
              </div>
              
              <div>
                <label className="label-text">Category</label>
                <p className="body-text text-gray-900">{productData.category || 'N/A'}</p>
              </div>

              <div>
                <label className="label-text">Current Price</label>
                <p className="body-text text-gray-900">${productData.price || 'N/A'}</p>
              </div>
              
              {productData.current_stock !== undefined && (
                <div>
                  <label className="label-text">Current Stock</label>
                  <p className="body-text text-gray-900">{productData.current_stock} units</p>
                </div>
              )}
              
              {productData.weekly_sales !== undefined && (
                <div>
                  <label className="label-text">Weekly Sales</label>
                  <p className="body-text text-gray-900">{productData.weekly_sales} units/week</p>
                </div>
              )}
            </div>

            <div className="space-y-4">
              {productData.image_url && (
                <div>
                  <label className="label-text">Product Image</label>
                  <div className="mt-2">
                    <img 
                      src={productData.image_url} 
                      alt={productData.title}
                      className="w-32 h-32 object-cover rounded-lg border border-gray-200"
                    />
                  </div>
                </div>
              )}

              <div>
                <label className="label-text">Dimensions</label>
                <p className="body-text text-gray-900">
                  {productData.dimensions || 'Not available'}
                </p>
              </div>

              <div>
                <label className="label-text">Weight</label>
                <p className="body-text text-gray-900">
                  {productData.weight || 'Not available'}
                </p>
              </div>
            </div>
          </div>

          {/* Sellerboard Data Section */}
          {productData.sellerboard_data && (
            <div className="mt-6 pt-4 border-t border-gray-200">
              <h4 className="heading-sm mb-3 text-blue-800">Live Sellerboard Data</h4>
              <div className="bg-blue-50 rounded-lg p-4">
                <div className="grid md:grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="font-medium">Data Source:</span> Your Sellerboard Account
                  </div>
                  <div>
                    <span className="font-medium">Freshness:</span> {productData.sellerboard_data.data_freshness}
                  </div>
                  {productData.sellerboard_data.weekly_sales !== undefined && (
                    <div>
                      <span className="font-medium">Weekly Velocity:</span> {productData.sellerboard_data.weekly_sales} units
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Research Actions */}
          <div className="mt-6 pt-4 border-t border-gray-200">
            <h4 className="heading-sm mb-3 text-gray-800">Research & Create Listing</h4>
            <div className="grid md:grid-cols-2 gap-3">
              <a
                href={`https://www.amazon.com/dp/${productData.asin}`}
                target="_blank"
                rel="noopener noreferrer"
                className="btn-secondary flex items-center justify-center"
              >
                <ExternalLink className="h-4 w-4 mr-2" />
                View on Amazon
              </a>
              
              <a
                href={`https://www.ebay.com/sch/i.html?_nkw=${encodeURIComponent(productData.title)}&_sacat=0&_sop=15`}
                target="_blank"
                rel="noopener noreferrer"
                className="btn-secondary flex items-center justify-center bg-blue-600 hover:bg-blue-700 text-white"
              >
                <ExternalLink className="h-4 w-4 mr-2" />
                Research on eBay
              </a>
              
              <a
                href={`https://www.ebay.com/sch/i.html?_nkw=${productData.asin}&_sacat=0&_sop=15`}
                target="_blank"
                rel="noopener noreferrer"
                className="btn-secondary flex items-center justify-center bg-purple-600 hover:bg-purple-700 text-white"
              >
                <ExternalLink className="h-4 w-4 mr-2" />
                Search by ASIN
              </a>
              
              <a
                href="https://www.ebay.com/sell/create"
                target="_blank"
                rel="noopener noreferrer"
                className="btn-primary flex items-center justify-center bg-green-600 hover:bg-green-700"
              >
                <ExternalLink className="h-4 w-4 mr-2" />
                Create eBay Listing
              </a>
            </div>
          </div>
        </div>
      )}


      {/* Instructions */}
      <div className="card bg-blue-50 border border-blue-200">
        <h3 className="heading-sm mb-3 text-blue-800">How to Use</h3>
        <div className="space-y-2 text-sm text-blue-700">
          <p>1. Enter a valid Amazon ASIN from your inventory (10 characters)</p>
          <p>2. Click "Lookup Product" to fetch live data from your Sellerboard account</p>
          <p>3. Review the product details including current stock and sales velocity</p>
          <p>4. Use "Research on eBay" to analyze competitor listings and pricing</p>
          <p>5. Use "Search by ASIN" to find exact product matches on eBay</p>
          <p>6. Click "Create eBay Listing" to start creating your listing on eBay</p>
          <p><strong>Note:</strong> This tool uses your real Sellerboard data for accurate inventory and sales information.</p>
        </div>
      </div>
    </div>
  );
};

export default EbayLister;