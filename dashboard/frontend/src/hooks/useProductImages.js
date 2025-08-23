import { useState, useEffect } from 'react';
import axios from 'axios';

// Hook for efficiently loading multiple product images
export const useProductImages = (asins) => {
  const [images, setImages] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!asins || asins.length === 0) return;

    const fetchImages = async () => {
      setLoading(true);
      setError(null);
      
      try {
        // Filter out ASINs we already have cached
        let cachedImages = {};
        try {
          cachedImages = JSON.parse(localStorage.getItem('productImages') || '{}');
        } catch (e) {
          console.warn('Corrupted image cache, clearing:', e);
          localStorage.removeItem('productImages');
          cachedImages = {};
        }
        
        const uncachedAsins = asins.filter(asin => {
          const cached = cachedImages[asin];
          if (cached && cached.timestamp && cached.url && (Date.now() - cached.timestamp) < 24 * 60 * 60 * 1000) {
            return false; // Still valid in cache
          }
          return true;
        });

        // Load cached images immediately
        const imageResults = { ...images };
        asins.forEach(asin => {
          const cached = cachedImages[asin];
          if (cached && cached.timestamp && (Date.now() - cached.timestamp) < 24 * 60 * 60 * 1000) {
            imageResults[asin] = cached.url;
          }
        });
        setImages(imageResults);

        // Fetch uncached images in smaller batches to avoid rate limits
        if (uncachedAsins.length > 0) {
          const batchSize = 5; // Reduced batch size
          for (let i = 0; i < uncachedAsins.length; i += batchSize) {
            const batch = uncachedAsins.slice(i, i + batchSize);
            
            console.log(`Fetching batch ${Math.floor(i/batchSize) + 1}/${Math.ceil(uncachedAsins.length/batchSize)} with ${batch.length} ASINs`);
            
            try {
              const response = await axios.post('/api/product-images/batch', {
                asins: batch
              }, { withCredentials: true });

              const batchResults = response.data.results;
              
              // Update state with new images
              setImages(prev => {
                const updated = { ...prev };
                Object.keys(batchResults).forEach(asin => {
                  const result = batchResults[asin];
                  if (result.image_url) {
                    // Use public proxy endpoint for better reliability
                    updated[asin] = `/api/product-image/${asin}/proxy/public`;
                    
                    // Cache the result
                    const newCache = { ...cachedImages };
                    newCache[asin] = {
                      url: `/api/product-image/${asin}/proxy/public`,
                      timestamp: Date.now()
                    };
                    localStorage.setItem('productImages', JSON.stringify(newCache));
                  }
                });
                return updated;
              });
              
              // Add delay between batches to avoid overwhelming the backend
              if (i + batchSize < uncachedAsins.length) {
                await new Promise(resolve => setTimeout(resolve, 1000));
              }
              
            } catch (batchError) {
              console.warn('Batch image fetch failed:', batchError);
              // Fall back to individual requests for this batch
              for (const asin of batch) {
                try {
                  const response = await axios.get(`/api/product-image/${asin}`, { withCredentials: true });
                  if (response.data.image_url) {
                    setImages(prev => ({
                      ...prev,
                      [asin]: `/api/product-image/${asin}/proxy/public`
                    }));
                    
                    // Cache individual result
                    const newCache = { ...JSON.parse(localStorage.getItem('productImages') || '{}') };
                    newCache[asin] = {
                      url: `/api/product-image/${asin}/proxy/public`,
                      timestamp: Date.now()
                    };
                    localStorage.setItem('productImages', JSON.stringify(newCache));
                  }
                } catch (individualError) {
                  console.warn(`Failed to fetch image for ${asin}:`, individualError);
                }
              }
            }
          }
        }
      } catch (err) {
        setError(err.message || 'Failed to fetch product images');
      } finally {
        setLoading(false);
      }
    };

    fetchImages();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [asins.join(',')]); // Dependency on ASINs array

  return { images, loading, error };
};

// Hook for single product image with queue-based processing
export const useProductImage = (asin) => {
  const [imageUrl, setImageUrl] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [queuePosition, setQueuePosition] = useState(null);

  useEffect(() => {
    if (!asin) {
      setLoading(false);
      setError(true);
      return;
    }

    let checkInterval;

    const fetchImage = async () => {
      setLoading(true);
      setError(false);
      setImageUrl(null);

      // Check localStorage cache first
      try {
        const cached = JSON.parse(localStorage.getItem('productImages') || '{}')[asin];
        if (cached && cached.timestamp && (Date.now() - cached.timestamp) < 24 * 60 * 60 * 1000 && cached.url) {
          setImageUrl(cached.url);
          setLoading(false);
          return;
        }
      } catch (e) {
        // Clear corrupted cache
        console.warn('Corrupted image cache, clearing:', e);
        try {
          localStorage.removeItem('productImages');
        } catch (clearError) {
          // Ignore clear errors
        }
      }

      try {
        // Initial request - this will queue the image for processing
        const response = await axios.get(`/api/product-image/${asin}`, { withCredentials: true });
        
        if (response.data) {
          if (response.data.cached && response.data.image_url) {
            // Use proxy endpoint to avoid CORS issues
            setImageUrl(`/api/product-image/${asin}/proxy/public`);
            setLoading(false);
          } else if (response.data.method === 'queued_for_processing') {
            // Queued for processing - show placeholder and start checking
            setImageUrl(response.data.image_url); // Placeholder
            setQueuePosition(response.data.queue_position);
            
            // Start periodic checking for the real image with exponential backoff
            let checkCount = 0;
            checkInterval = setInterval(async () => {
              try {
                const checkResponse = await axios.post('/api/check-images', {
                  asins: [asin]
                }, { withCredentials: true });
                
                const result = checkResponse.data.results[asin];
                if (result && result.ready) {
                  // Use proxy endpoint for the fetched image
                  setImageUrl(`/api/product-image/${asin}/proxy/public`);
                  setLoading(false);
                  setQueuePosition(null);
                  
                  // Cache the result
                  try {
                    const cache = JSON.parse(localStorage.getItem('productImages') || '{}');
                    cache[asin] = {
                      url: `/api/product-image/${asin}/proxy/public`,
                      timestamp: Date.now(),
                      method: 'queue_processed'
                    };
                    localStorage.setItem('productImages', JSON.stringify(cache));
                  } catch (e) {
                    // Ignore cache save errors
                  }
                  
                  clearInterval(checkInterval);
                } else if (result && result.queue_position) {
                  setQueuePosition(result.queue_position);
                }
                
                checkCount++;
                // Stop checking after 10 attempts (50 seconds) to prevent infinite loops
                if (checkCount >= 10) {
                  clearInterval(checkInterval);
                  setError(true);
                  setLoading(false);
                  setQueuePosition(null);
                }
              } catch (checkErr) {
                console.warn(`Failed to check image status for ${asin}:`, checkErr);
                checkCount++;
                if (checkCount >= 5) {
                  clearInterval(checkInterval);
                  setError(true);
                  setLoading(false);
                }
              }
            }, 3000); // Check every 3 seconds instead of 5
            
            setLoading(false);
          } else if (response.data.image_url) {
            // Use proxy endpoint for any returned image URL
            setImageUrl(`/api/product-image/${asin}/proxy/public`);
            setLoading(false);
          } else {
            // No image found
            setError(true);
            setImageUrl(null);
            setLoading(false);
          }
        }
      } catch (err) {
        console.error(`Failed to fetch image for ASIN ${asin}:`, err.response?.data || err.message);
        
        // Set error state instead of placeholder
        setError(true);
        setImageUrl(null);
        setLoading(false);
      }
    };

    fetchImage();

    // Cleanup interval on unmount
    return () => {
      if (checkInterval) {
        clearInterval(checkInterval);
      }
    };
  }, [asin]);

  return { imageUrl, loading, error, queuePosition };
};