import React, { useState } from 'react';
import axios from 'axios';

const ImageTest = () => {
  const [asin, setAsin] = useState('B08N5WRWNW');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const testImage = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`/api/test-image/${asin}`, { withCredentials: true });
      setResult(response.data);
    } catch (error) {
      setResult({ error: error.message });
    } finally {
      setLoading(false);
    }
  };

  const testProductImage = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`/api/product-image/${asin}`, { withCredentials: true });
      setResult(response.data);
    } catch (error) {
      setResult({ error: error.message, response: error.response?.data });
    } finally {
      setLoading(false);
    }
  };

  const testImagePatterns = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`/api/test-image-patterns/${asin}`, { withCredentials: true });
      setResult(response.data);
    } catch (error) {
      setResult({ error: error.message, response: error.response?.data });
    } finally {
      setLoading(false);
    }
  };

  const checkImageStatus = async () => {
    setLoading(true);
    try {
      const response = await axios.get('/api/image-status', { withCredentials: true });
      setResult(response.data);
    } catch (error) {
      setResult({ error: error.message });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <h2 className="text-xl font-bold mb-4">Image API Test</h2>
      
      <div className="mb-4">
        <label className="block text-sm font-medium mb-2">ASIN:</label>
        <input
          type="text"
          value={asin}
          onChange={(e) => setAsin(e.target.value)}
          className="border border-gray-300 rounded px-3 py-2 w-full"
          placeholder="Enter ASIN (e.g., B08N5WRWNW)"
        />
      </div>

      <div className="space-x-4 mb-6">
        <button
          onClick={testImage}
          disabled={loading}
          className="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600 disabled:opacity-50"
        >
          Test Image URLs
        </button>
        
        <button
          onClick={testProductImage}
          disabled={loading}
          className="bg-green-500 text-white px-4 py-2 rounded hover:bg-green-600 disabled:opacity-50"
        >
          Test Product Image API
        </button>
        
        <button
          onClick={testImagePatterns}
          disabled={loading}
          className="bg-purple-500 text-white px-4 py-2 rounded hover:bg-purple-600 disabled:opacity-50"
        >
          Test All Patterns
        </button>
        
        <button
          onClick={checkImageStatus}
          disabled={loading}
          className="bg-gray-500 text-white px-4 py-2 rounded hover:bg-gray-600 disabled:opacity-50"
        >
          Check Rate Limit Status
        </button>
      </div>

      {loading && <p>Loading...</p>}

      {result && (
        <div className="mt-6">
          <h3 className="text-lg font-semibold mb-2">Result:</h3>
          <pre className="bg-gray-100 p-4 rounded overflow-auto text-sm">
            {JSON.stringify(result, null, 2)}
          </pre>
          
          {result.image_url && (
            <div className="mt-4">
              <h4 className="font-semibold mb-2">Image Preview:</h4>
              <img 
                src={result.image_url} 
                alt={`Product ${asin}`}
                className="border border-gray-300 rounded max-w-xs"
                onError={(e) => {
                  e.target.style.display = 'none';
                  e.target.nextSibling.style.display = 'block';
                }}
              />
              <div style={{display: 'none'}} className="text-red-500 text-sm">
                Image failed to load
              </div>
            </div>
          )}

          {result.working_url && (
            <div className="mt-4">
              <h4 className="font-semibold mb-2">Working URL Preview:</h4>
              <img 
                src={result.working_url} 
                alt={`Product ${asin}`}
                className="border border-gray-300 rounded max-w-xs"
                onError={(e) => {
                  e.target.style.display = 'none';
                  e.target.nextSibling.style.display = 'block';
                }}
              />
              <div style={{display: 'none'}} className="text-red-500 text-sm">
                Image failed to load
              </div>
            </div>
          )}

          {result.associate_widget_result && (
            <div className="mt-4">
              <h4 className="font-semibold mb-2">Associates Widget Result:</h4>
              <div className={`p-3 rounded ${result.associate_widget_result.valid ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'}`}>
                <div className="flex items-center mb-2">
                  <span className={`font-medium ${result.associate_widget_result.valid ? 'text-green-600' : 'text-red-600'}`}>
                    {result.associate_widget_result.valid ? '✓' : '✗'} Associates Widget {result.associate_widget_result.valid ? 'Available' : 'Failed'}
                  </span>
                </div>
                {result.associate_widget_result.valid && (
                  <div>
                    <img 
                      src={result.associate_widget_result.url} 
                      alt="Associates Widget"
                      className="w-24 h-24 object-contain border border-gray-200 rounded mb-2"
                    />
                    <div className="text-xs text-gray-600 break-all">{result.associate_widget_result.url}</div>
                  </div>
                )}
                {result.associate_widget_result.error && (
                  <div className="text-sm text-red-600">{result.associate_widget_result.error}</div>
                )}
              </div>
            </div>
          )}
          
          {result.recommendation && (
            <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded">
              <p className="text-sm text-blue-800">
                <strong>Recommendation:</strong> {result.recommendation}
              </p>
            </div>
          )}

          {result.html_scraping_result && (
            <div className="mt-4">
              <h4 className="font-semibold mb-2">HTML Scraping Result:</h4>
              <div className={`p-3 rounded ${result.html_scraping_result.valid_image ? 'bg-green-50 border border-green-200' : 'bg-yellow-50 border border-yellow-200'}`}>
                {result.html_scraping_result.valid_image ? (
                  <div>
                    <div className="flex items-center mb-2">
                      <span className="font-medium text-green-600">✓ HTML Scraping Success</span>
                    </div>
                    <div className="mb-2">
                      <img 
                        src={result.html_scraping_result.url} 
                        alt="Scraped from HTML"
                        className="w-24 h-24 object-contain border border-gray-200 rounded"
                        onError={(e) => {
                          e.target.style.display = 'none';
                          e.target.nextSibling.style.display = 'block';
                        }}
                      />
                      <div style={{display: 'none'}} className="text-red-500 text-xs">
                        Failed to load scraped image
                      </div>
                    </div>
                    <div className="text-xs space-y-1">
                      <div><strong>Selector:</strong> {result.html_scraping_result.selector}</div>
                      <div><strong>Attribute:</strong> {result.html_scraping_result.attribute_used}</div>
                      <div className="text-gray-600 break-all"><strong>URL:</strong> {result.html_scraping_result.url}</div>
                    </div>
                  </div>
                ) : (
                  <div>
                    <div className="flex items-center mb-2">
                      <span className="font-medium text-yellow-600">⚠ HTML Scraping Failed</span>
                    </div>
                    <div className="text-sm text-yellow-700">
                      {result.html_scraping_result.error}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

        </div>
      )}
    </div>
  );
};

export default ImageTest;