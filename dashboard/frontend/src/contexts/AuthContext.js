import React, { createContext, useContext, useState, useEffect } from 'react';
import axios from 'axios';

const AuthContext = createContext();

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    checkAuthStatus();
  }, []);

  const checkAuthStatus = async () => {
    try {

      const response = await axios.get('/api/user', { withCredentials: true });
      
      setUser(response.data);
    } catch (error) {

      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  const login = (invitationToken = null) => {
    const apiBaseUrl = process.env.REACT_APP_API_URL || 'https://internet-money-tools-production.up.railway.app';

    let authUrl = `${apiBaseUrl}/auth/discord`;
    if (invitationToken) {
      authUrl += `?invitation=${invitationToken}`;
    }
    
    window.location.href = authUrl;
  };

  const logout = async () => {
    try {
      await axios.get('/auth/logout', { withCredentials: true });
      setUser(null);
    } catch (error) {
      
    }
  };

  const updateUser = (userData) => {
    setUser(prev => ({ ...prev, ...userData }));
  };

  const refreshUser = async () => {
    try {
      const response = await axios.get('/api/user', { withCredentials: true });
      setUser(response.data);
      return response.data;
    } catch (error) {
      
      throw error;
    }
  };

  const value = {
    user,
    login,
    logout,
    updateUser,
    refreshUser,
    loading,
    isAuthenticated: !!user
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};