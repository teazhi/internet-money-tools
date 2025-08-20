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
        const cachedImages = JSON.parse(localStorage.getItem('productImages') || '{}');
        const uncachedAsins = asins.filter(asin => {
          const cached = cachedImages[asin];
          if (cached && cached.timestamp && (Date.now() - cached.timestamp) < 24 * 60 * 60 * 1000) {
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
                    updated[asin] = result.image_url;
                    
                    // Cache the result
                    const newCache = { ...cachedImages };
                    newCache[asin] = {
                      url: result.image_url,
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
                      [asin]: response.data.image_url
                    }));
                    
                    // Cache individual result
                    const newCache = { ...JSON.parse(localStorage.getItem('productImages') || '{}') };
                    newCache[asin] = {
                      url: response.data.image_url,
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

// Hook for single product image
export const useProductImage = (asin) => {
  const [imageUrl, setImageUrl] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!asin) {
      setLoading(false);
      setError(true);
      return;
    }

    const fetchImage = async () => {
      setLoading(true);
      setError(false);
      setImageUrl(null);

      // Check localStorage cache first
      try {
        const cached = JSON.parse(localStorage.getItem('productImages') || '{}')[asin];
        if (cached && cached.timestamp && (Date.now() - cached.timestamp) < 24 * 60 * 60 * 1000) {
          setImageUrl(cached.url);
          setLoading(false);
          return;
        }
      } catch (e) {
        // Ignore cache errors
      }

      try {
        const response = await axios.get(`/api/product-image/${asin}`, { withCredentials: true });
        
        if (response.data && response.data.image_url) {
          setImageUrl(response.data.image_url);
          
          // Log method used for debugging
          if (response.data.method) {
            console.log(`Image for ${asin} loaded via: ${response.data.method}`);
          }
          
          // Cache the result
          try {
            const cache = JSON.parse(localStorage.getItem('productImages') || '{}');
            cache[asin] = {
              url: response.data.image_url,
              timestamp: Date.now(),
              method: response.data.method || 'unknown'
            };
            localStorage.setItem('productImages', JSON.stringify(cache));
          } catch (e) {
            // Ignore cache save errors
          }
        } else {
          console.error(`No image URL returned for ASIN ${asin}:`, response.data);
          setError(true);
        }
      } catch (err) {
        console.error(`Failed to fetch image for ASIN ${asin}:`, err.response?.data || err.message);
        
        // If backend failed, try a fallback URL directly
        const fallbackUrl = `https://m.media-amazon.com/images/P/${asin}.01._SX300_SY300_.jpg`;
        console.log(`Trying fallback URL for ${asin}: ${fallbackUrl}`);
        setImageUrl(fallbackUrl);
        
        // Don't set error since we're trying a fallback
      } finally {
        setLoading(false);
      }
    };

    fetchImage();
  }, [asin]);

  return { imageUrl, loading, error };
};