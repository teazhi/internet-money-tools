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

          {result.working_urls && result.working_urls.length > 0 && (
            <div className="mt-4">
              <h4 className="font-semibold mb-2">Working Image URLs ({result.working_urls.length} found):</h4>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {result.working_urls.map((urlData, index) => (
                  <div key={index} className="border border-gray-300 rounded p-3">
                    <div className="mb-2">
                      <img 
                        src={urlData.url} 
                        alt={`Pattern ${index + 1}`}
                        className="w-full h-32 object-contain border border-gray-200 rounded"
                        onError={(e) => {
                          e.target.style.display = 'none';
                          e.target.nextSibling.style.display = 'block';
                        }}
                      />
                      <div style={{display: 'none'}} className="text-red-500 text-xs">
                        Failed to load
                      </div>
                    </div>
                    <div className="text-xs">
                      <div className="font-medium text-green-600">✓ Valid Image</div>
                      <div className="text-gray-600">Size: {urlData.content_length} bytes</div>
                      <div className="text-gray-600">Type: {urlData.content_type}</div>
                      <div className="text-gray-500 break-all mt-1">{urlData.url}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {result.tested_patterns && (
            <div className="mt-4">
              <h4 className="font-semibold mb-2">All Tested Patterns:</h4>
              <div className="space-y-2">
                {result.tested_patterns.map((pattern, index) => (
                  <div key={index} className={`p-2 rounded text-sm ${pattern.valid_image ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'}`}>
                    <div className="flex items-center justify-between">
                      <span className={`font-medium ${pattern.valid_image ? 'text-green-600' : 'text-red-600'}`}>
                        {pattern.valid_image ? '✓' : '✗'} {pattern.status_code || 'Error'}
                      </span>
                      <span className="text-xs text-gray-500">
                        {pattern.content_length && `${pattern.content_length} bytes`}
                      </span>
                    </div>
                    <div className="text-gray-600 break-all mt-1">{pattern.url}</div>
                    {pattern.error && (
                      <div className="text-red-500 text-xs mt-1">Error: {pattern.error}</div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ImageTest;