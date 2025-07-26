// API Configuration
const getApiBaseUrl = () => {
  // Check if we're in production
  if (process.env.NODE_ENV === 'production') {
    // Use environment variable for production API URL
    return process.env.REACT_APP_API_URL || 'https://internet-money-tools-production.up.railway.app';
  }
  // Development URL
  return 'http://localhost:5000';
};

export const API_BASE_URL = getApiBaseUrl();
export const API_ENDPOINTS = {
  // Auth endpoints
  DISCORD_AUTH: `${API_BASE_URL}/auth/discord`,
  DISCORD_CALLBACK: `${API_BASE_URL}/auth/discord/callback`,
  GOOGLE_AUTH: `${API_BASE_URL}/auth/google`,
  LOGOUT: `${API_BASE_URL}/auth/logout`,
  
  // User endpoints  
  USER: `${API_BASE_URL}/api/user`,
  
  // Analytics endpoints
  ANALYTICS_ORDERS: `${API_BASE_URL}/api/analytics/orders`,
  
  // Settings endpoints
  SETTINGS: `${API_BASE_URL}/api/user/settings`,
  
  // Debug endpoints
  DEBUG_STOCK_COLUMNS: `${API_BASE_URL}/api/debug/stock-columns`,
  
  // Health check
  HEALTH: `${API_BASE_URL}/api/health`
};

export default API_BASE_URL;