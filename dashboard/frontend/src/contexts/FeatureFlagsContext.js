import React, { createContext, useContext, useState, useEffect } from 'react';
import axios from 'axios';

const FeatureFlagsContext = createContext();

export const useFeatureFlags = () => {
  const context = useContext(FeatureFlagsContext);
  if (!context) {
    throw new Error('useFeatureFlags must be used within a FeatureFlagsProvider');
  }
  return context;
};

export const FeatureFlagsProvider = ({ children }) => {
  const [features, setFeatures] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchUserFeatures = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await axios.get('/api/user/features', { 
        withCredentials: true 
      });
      
      setFeatures(response.data.features || {});
    } catch (err) {
      console.error('Error fetching user features:', err);
      setError(err.response?.data?.error || 'Failed to load features');
      // Set empty features on error to prevent app from breaking
      setFeatures({});
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUserFeatures();
  }, []);

  const hasFeatureAccess = (featureKey) => {
    const feature = features[featureKey];
    return feature?.has_access || false;
  };

  const isFeatureBeta = (featureKey) => {
    const feature = features[featureKey];
    return feature?.is_beta || false;
  };

  const getFeatureInfo = (featureKey) => {
    return features[featureKey] || null;
  };

  const refreshFeatures = () => {
    fetchUserFeatures();
  };

  const value = {
    features,
    loading,
    error,
    hasFeatureAccess,
    isFeatureBeta,
    getFeatureInfo,
    refreshFeatures
  };

  return (
    <FeatureFlagsContext.Provider value={value}>
      {children}
    </FeatureFlagsContext.Provider>
  );
};

export default FeatureFlagsContext;