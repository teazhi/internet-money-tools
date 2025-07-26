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
      console.log('Checking auth status...');
      console.log('Making request to:', axios.defaults.baseURL + '/api/user');
      const response = await axios.get('/api/user', { withCredentials: true });
      console.log('Auth check response:', response.data);
      setUser(response.data);
    } catch (error) {
      console.error('Auth check failed:', error);
      console.error('Error status:', error.response?.status);
      console.error('Error data:', error.response?.data);
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  const login = () => {
    const apiBaseUrl = process.env.REACT_APP_API_URL || 'https://internet-money-tools-production.up.railway.app';
    console.log('Environment REACT_APP_API_URL:', process.env.REACT_APP_API_URL);
    console.log('Using API URL for Discord auth:', apiBaseUrl);
    window.location.href = `${apiBaseUrl}/auth/discord`;
  };

  const logout = async () => {
    try {
      await axios.get('/auth/logout', { withCredentials: true });
      setUser(null);
    } catch (error) {
      console.error('Logout error:', error);
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
      console.error('Failed to refresh user data:', error);
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