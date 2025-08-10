// API Configuration
const getApiBaseUrl = () => {
  // Check if we're in production
  if (process.env.NODE_ENV === 'production') {
    // Use environment variable for production API URL
    return process.env.REACT_APP_API_URL || 'https://internet-money-tools-production.up.railway.app';
  }
  // Development URL - fallback to Railway for safety
  return 'https://internet-money-tools-production.up.railway.app';
};

export const API_BASE_URL = getApiBaseUrl();
export const API_ENDPOINTS = {
  // Auth endpoints
  DISCORD_AUTH: `${API_BASE_URL}/auth/discord`,
  DISCORD_CALLBACK: `${API_BASE_URL}/auth/discord/callback`,
  GOOGLE_AUTH: `${API_BASE_URL}/auth/google`,
  AMAZON_AUTH: `${API_BASE_URL}/auth/amazon-seller`,
  LOGOUT: `${API_BASE_URL}/auth/logout`,
  
  // User endpoints  
  USER: `${API_BASE_URL}/api/user`,
  
  // Analytics endpoints
  ANALYTICS_ORDERS: `${API_BASE_URL}/api/analytics/orders`,
  
  // Discount leads endpoints
  DISCOUNT_LEADS: `${API_BASE_URL}/api/discount-leads/fetch`,
  DISCOUNT_OPPORTUNITIES: `${API_BASE_URL}/api/discount-opportunities/analyze`,
  DISCOUNT_MONITORING_STATUS: `${API_BASE_URL}/api/admin/discount-monitoring/status`,
  DISCOUNT_MONITORING_TEST: `${API_BASE_URL}/api/admin/discount-monitoring/test`,
  
  // Settings endpoints
  SETTINGS: `${API_BASE_URL}/api/user/settings`,
  
  // Debug endpoints
  DEBUG_STOCK_COLUMNS: `${API_BASE_URL}/api/debug/stock-columns`,
  
  // Admin endpoints
  ADMIN_USERS: `${API_BASE_URL}/api/admin/users`,
  ADMIN_INVITATIONS: `${API_BASE_URL}/api/admin/invitations`,
  ADMIN_DISCORD_CONFIG: `${API_BASE_URL}/api/admin/discord-monitoring/config`,
  
  // Health check
  HEALTH: `${API_BASE_URL}/api/health`
};

export default API_BASE_URL;