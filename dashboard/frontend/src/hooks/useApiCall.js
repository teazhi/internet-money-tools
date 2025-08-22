/**
 * Reusable API Call Hook
 * 
 * Provides standardized API calling with loading states, error handling,
 * and automatic retry logic. Safe refactor - doesn't change existing behavior.
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import axios from 'axios';

export const useApiCall = (options = {}) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  const abortControllerRef = useRef(null);
  
  const {
    onSuccess = () => {},
    onError = () => {},
    retryCount = 0,
    retryDelay = 1000,
    timeout = 30000
  } = options;

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  const execute = useCallback(async (config) => {
    // Cancel any ongoing request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    // Create new abort controller
    abortControllerRef.current = new AbortController();

    setLoading(true);
    setError(null);

    let lastError = null;
    let attempt = 0;

    while (attempt <= retryCount) {
      try {
        const response = await axios({
          ...config,
          timeout,
          signal: abortControllerRef.current.signal,
          withCredentials: true, // Standard for this app
        });

        setData(response.data);
        setLoading(false);
        onSuccess(response.data);
        
        return response.data;

      } catch (err) {
        lastError = err;
        
        // Don't retry if request was aborted
        if (err.name === 'AbortError' || err.code === 'ERR_CANCELED') {
          setLoading(false);
          return;
        }

        // Don't retry on 4xx errors (client errors)
        if (err.response && err.response.status >= 400 && err.response.status < 500) {
          break;
        }

        attempt++;
        
        // If we have more retries, wait before trying again
        if (attempt <= retryCount) {
          await new Promise(resolve => setTimeout(resolve, retryDelay * attempt));
        }
      }
    }

    // All attempts failed
    const errorMessage = lastError?.response?.data?.error || 
                        lastError?.message || 
                        'Request failed';
    
    setError(errorMessage);
    setLoading(false);
    onError(errorMessage);
    
    throw lastError;

  }, [retryCount, retryDelay, timeout, onSuccess, onError]);

  const reset = useCallback(() => {
    setData(null);
    setError(null);
    setLoading(false);
  }, []);

  return {
    data,
    loading,
    error,
    execute,
    reset
  };
};

/**
 * Specialized hook for GET requests
 */
export const useApiGet = (url, options = {}) => {
  const { execute, ...rest } = useApiCall(options);
  
  const get = useCallback((params = {}) => {
    return execute({
      method: 'GET',
      url,
      params
    });
  }, [execute, url]);

  return { get, ...rest };
};

/**
 * Specialized hook for POST requests
 */
export const useApiPost = (url, options = {}) => {
  const { execute, ...rest } = useApiCall(options);
  
  const post = useCallback((data = {}) => {
    return execute({
      method: 'POST',
      url,
      data
    });
  }, [execute, url]);

  return { post, ...rest };
};

/**
 * Specialized hook for PUT requests
 */
export const useApiPut = (url, options = {}) => {
  const { execute, ...rest } = useApiCall(options);
  
  const put = useCallback((data = {}) => {
    return execute({
      method: 'PUT',
      url,
      data
    });
  }, [execute, url]);

  return { put, ...rest };
};

/**
 * Specialized hook for DELETE requests
 */
export const useApiDelete = (url, options = {}) => {
  const { execute, ...rest } = useApiCall(options);
  
  const del = useCallback(() => {
    return execute({
      method: 'DELETE',
      url
    });
  }, [execute, url]);

  return { delete: del, ...rest };
};