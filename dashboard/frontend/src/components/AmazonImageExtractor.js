import React, { useState, useEffect } from 'react';

const AmazonImageExtractor = ({ asin, onImageFound, onError }) => {
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!asin) {
      onError?.();
      return;
    }

    const extractImage = async () => {
      try {
        // Create hidden iframe to load Amazon page
        const iframe = document.createElement('iframe');
        iframe.style.display = 'none';
        iframe.style.position = 'absolute';
        iframe.style.left = '-9999px';
        iframe.style.width = '1px';
        iframe.style.height = '1px';
        
        document.body.appendChild(iframe);

        const amazonUrl = `https://www.amazon.com/dp/${asin}`;
        
        // Set up promise to wait for iframe load
        const loadPromise = new Promise((resolve, reject) => {
          const timeout = setTimeout(() => {
            reject(new Error('Timeout'));
          }, 10000);

          iframe.onload = () => {
            clearTimeout(timeout);
            try {
              // Wait a bit for content to render
              setTimeout(() => {
                try {
                  const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
                  
                  // Look for the selector you identified
                  const imgTagWrapper = iframeDoc.querySelector('#imgTagWrapperId');
                  if (imgTagWrapper) {
                    const img = imgTagWrapper.querySelector('img');
                    if (img) {
                      const imageUrl = img.getAttribute('data-old-hires') || 
                                     img.getAttribute('data-a-hires') ||
                                     img.getAttribute('src') ||
                                     img.getAttribute('data-src');
                      
                      if (imageUrl && imageUrl.startsWith('http')) {
                        resolve(imageUrl);
                        return;
                      }
                    }
                  }
                  
                  reject(new Error('Image not found in iframe'));
                } catch (e) {
                  reject(e);
                }
              }, 2000);
            } catch (e) {
              clearTimeout(timeout);
              reject(e);
            }
          };

          iframe.onerror = () => {
            clearTimeout(timeout);
            reject(new Error('Failed to load iframe'));
          };
        });

        iframe.src = amazonUrl;
        
        try {
          const imageUrl = await loadPromise;
          onImageFound?.(imageUrl);
        } catch (error) {
          console.warn(`Failed to extract image for ${asin}:`, error);
          onError?.();
        } finally {
          // Clean up
          document.body.removeChild(iframe);
          setLoading(false);
        }

      } catch (error) {
        console.error(`Error setting up iframe for ${asin}:`, error);
        onError?.();
        setLoading(false);
      }
    };

    extractImage();
  }, [asin, onImageFound, onError]);

  return null; // This component doesn't render anything visible
};

export default AmazonImageExtractor;