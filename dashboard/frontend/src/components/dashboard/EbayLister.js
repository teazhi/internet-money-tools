import React, { useState } from 'react';
import { 
  Search, 
  Package, 
  ExternalLink, 
  Copy, 
  CheckCircle, 
  AlertTriangle,
  RefreshCw,
  Image as ImageIcon,
  DollarSign,
  Tag
} from 'lucide-react';
import axios from 'axios';

const EbayLister = () => {
  const [asin, setAsin] = useState('');
  const [loading, setLoading] = useState(false);
  const [productData, setProductData] = useState(null);
  const [error, setError] = useState('');
  const [listingData, setListingData] = useState(null);
  const [generatingListing, setGeneratingListing] = useState(false);

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

      if (response.data.success) {
        setProductData(response.data.product);
        // Show warning if there was a Sellerboard issue
        if (response.data.warning) {
          setError(`Warning: ${response.data.warning}`);
        }
      } else {
        setError(response.data.message || 'Product not found');
      }
    } catch (err) {
      if (err.response?.status === 404) {
        setError('Product not found. Please verify the ASIN is correct.');
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

  const generateEbayListing = async () => {
    if (!productData) return;

    setGeneratingListing(true);
    setError('');

    try {
      const response = await axios.post('/api/ebay/generate-listing', {
        asin: asin.trim().toUpperCase(),
        productData: productData
      }, {
        withCredentials: true
      });

      if (response.data.success) {
        setListingData(response.data.listing);
      } else {
        setError(response.data.message || 'Failed to generate eBay listing');
      }
    } catch (err) {
      setError('Failed to generate eBay listing. Please try again.');
    } finally {
      setGeneratingListing(false);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
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
            <h1 className="text-2xl font-bold">eBay Lister</h1>
            <p className="text-purple-100">Create eBay listings from Amazon ASINs</p>
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

          <div className="mt-6 pt-4 border-t border-gray-200">
            <div className="flex space-x-3">
              <button
                onClick={generateEbayListing}
                disabled={generatingListing}
                className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
              >
                {generatingListing ? (
                  <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <ExternalLink className="h-4 w-4 mr-2" />
                )}
                Generate eBay Listing
              </button>
              
              <a
                href={`https://www.amazon.com/dp/${productData.asin}`}
                target="_blank"
                rel="noopener noreferrer"
                className="btn-secondary flex items-center"
              >
                <ExternalLink className="h-4 w-4 mr-2" />
                View on Amazon
              </a>
            </div>
          </div>
        </div>
      )}

      {/* Generated eBay Listing */}
      {listingData && (
        <div className="card">
          <h3 className="heading-sm mb-4 flex items-center">
            <CheckCircle className="h-5 w-5 text-green-500 mr-2" />
            Generated eBay Listing
          </h3>
          
          <div className="space-y-6">
            {/* Title */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="label-text">Title</label>
                <button
                  onClick={() => copyToClipboard(listingData.title)}
                  className="text-xs text-gray-500 hover:text-gray-700 flex items-center"
                >
                  <Copy className="h-3 w-3 mr-1" />
                  Copy
                </button>
              </div>
              <div className="p-3 bg-gray-50 rounded-lg">
                <p className="body-text">{listingData.title}</p>
              </div>
            </div>

            {/* Description */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="label-text">Description</label>
                <button
                  onClick={() => copyToClipboard(listingData.description)}
                  className="text-xs text-gray-500 hover:text-gray-700 flex items-center"
                >
                  <Copy className="h-3 w-3 mr-1" />
                  Copy
                </button>
              </div>
              <div className="p-3 bg-gray-50 rounded-lg max-h-64 overflow-y-auto">
                <div className="whitespace-pre-wrap body-text">{listingData.description}</div>
              </div>
            </div>

            {/* Suggested Pricing */}
            <div className="grid md:grid-cols-3 gap-4">
              <div>
                <label className="label-text">Suggested Starting Price</label>
                <div className="p-3 bg-green-50 rounded-lg">
                  <p className="heading-sm text-green-700">${listingData.suggestedPrice}</p>
                </div>
              </div>
              
              <div>
                <label className="label-text">Buy It Now Price</label>
                <div className="p-3 bg-blue-50 rounded-lg">
                  <p className="heading-sm text-blue-700">${listingData.buyItNowPrice}</p>
                </div>
              </div>
              
              <div>
                <label className="label-text">Shipping</label>
                <div className="p-3 bg-amber-50 rounded-lg">
                  <p className="heading-sm text-amber-700">{listingData.shipping}</p>
                </div>
              </div>
            </div>

            {/* Category and Item Specifics */}
            <div className="grid md:grid-cols-2 gap-6">
              <div>
                <label className="label-text">eBay Category</label>
                <div className="p-3 bg-gray-50 rounded-lg">
                  <p className="body-text">{listingData.category}</p>
                </div>
              </div>
              
              <div>
                <label className="label-text">Condition</label>
                <div className="p-3 bg-gray-50 rounded-lg">
                  <p className="body-text">{listingData.condition}</p>
                </div>
              </div>
            </div>

            {/* Item Specifics */}
            {listingData.itemSpecifics && (
              <div>
                <label className="label-text">Item Specifics</label>
                <div className="p-3 bg-gray-50 rounded-lg">
                  <div className="grid grid-cols-2 gap-2">
                    {Object.entries(listingData.itemSpecifics).map(([key, value]) => (
                      <div key={key} className="flex justify-between">
                        <span className="body-text font-medium">{key}:</span>
                        <span className="body-text text-gray-600">{value}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Action Buttons */}
            <div className="flex space-x-3 pt-4 border-t border-gray-200">
              <button className="btn-primary flex items-center">
                <ExternalLink className="h-4 w-4 mr-2" />
                Create eBay Listing
              </button>
              
              <button
                onClick={() => copyToClipboard(JSON.stringify(listingData, null, 2))}
                className="btn-secondary flex items-center"
              >
                <Copy className="h-4 w-4 mr-2" />
                Copy All Data
              </button>
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
          <p>4. Click "Generate eBay Listing" to create optimized listing content</p>
          <p>5. Copy and paste the generated content into your eBay listing</p>
          <p><strong>Note:</strong> This tool uses your real Sellerboard data, so only ASINs in your inventory will be found.</p>
        </div>
      </div>
    </div>
  );
};

export default EbayLister;