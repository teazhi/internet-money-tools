import React, { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { Save, AlertCircle, CheckCircle, Settings as SettingsIcon, Mail, FileText, ToggleLeft, ToggleRight, Link, Clock, ShoppingBag, ExternalLink } from 'lucide-react';
import { API_ENDPOINTS } from '../../config/api';
import axios from 'axios';

// Common timezones for the selector
const COMMON_TIMEZONES = [
  { value: 'America/New_York', label: 'Eastern Time (ET)' },
  { value: 'America/Chicago', label: 'Central Time (CT)' },
  { value: 'America/Denver', label: 'Mountain Time (MT)' },
  { value: 'America/Los_Angeles', label: 'Pacific Time (PT)' },
  { value: 'America/Anchorage', label: 'Alaska Time (AKT)' },
  { value: 'Pacific/Honolulu', label: 'Hawaii Time (HST)' },
  { value: 'Europe/London', label: 'Greenwich Mean Time (GMT)' },
  { value: 'Europe/Paris', label: 'Central European Time (CET)' },
  { value: 'Europe/Berlin', label: 'Central European Time (CET)' },
  { value: 'Europe/Rome', label: 'Central European Time (CET)' },
  { value: 'Europe/Madrid', label: 'Central European Time (CET)' },
  { value: 'Europe/Moscow', label: 'Moscow Time (MSK)' },
  { value: 'Asia/Tokyo', label: 'Japan Standard Time (JST)' },
  { value: 'Asia/Shanghai', label: 'China Standard Time (CST)' },
  { value: 'Asia/Hong_Kong', label: 'Hong Kong Time (HKT)' },
  { value: 'Asia/Singapore', label: 'Singapore Time (SGT)' },
  { value: 'Asia/Dubai', label: 'Gulf Standard Time (GST)' },
  { value: 'Asia/Kolkata', label: 'India Standard Time (IST)' },
  { value: 'Australia/Sydney', label: 'Australian Eastern Time (AET)' },
  { value: 'Australia/Melbourne', label: 'Australian Eastern Time (AET)' },
  { value: 'Australia/Perth', label: 'Australian Western Time (AWT)' },
  { value: 'Pacific/Auckland', label: 'New Zealand Time (NZST)' },
  { value: 'America/Toronto', label: 'Eastern Time (Canada)' },
  { value: 'America/Vancouver', label: 'Pacific Time (Canada)' },
  { value: 'America/Sao_Paulo', label: 'Brasília Time (BRT)' },
  { value: 'America/Mexico_City', label: 'Central Time (Mexico)' },
  { value: 'Africa/Cairo', label: 'Eastern European Time (EET)' },
  { value: 'Africa/Johannesburg', label: 'South Africa Standard Time (SAST)' }
];

const Settings = () => {
  const { user, updateUser } = useAuth();
  const [formData, setFormData] = useState({
    email: '',
    listing_loader_key: '',
    sb_file_key: '',
    run_scripts: true,
    run_prep_center: false,
    sellerboard_orders_url: '',
    sellerboard_stock_url: '',
    timezone: '',
    enable_source_links: false,
    search_all_worksheets: false
  });
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState({ type: '', text: '' });
  const [amazonStatus, setAmazonStatus] = useState({ connected: false, loading: true });
  const [testingConnection, setTestingConnection] = useState(false);

  useEffect(() => {
    if (user?.user_record) {
      setFormData({
        email: user.user_record.email || '',
        listing_loader_key: user.user_record.listing_loader_key || '',
        sb_file_key: user.user_record.sb_file_key || '',
        run_scripts: user.user_record.run_scripts !== false,
        run_prep_center: user.user_record.run_prep_center !== false,
        sellerboard_orders_url: user.user_record.sellerboard_orders_url || '',
        sellerboard_stock_url: user.user_record.sellerboard_stock_url || '',
        timezone: user.user_record.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone,
        enable_source_links: user.user_record.enable_source_links || false,
        search_all_worksheets: user.user_record.search_all_worksheets || false
      });
    }
  }, [user]);

  // Load Amazon connection status
  useEffect(() => {
    const loadAmazonStatus = async () => {
      try {
        const response = await axios.get('/api/amazon-seller/status', { withCredentials: true });
        setAmazonStatus({ ...response.data, loading: false });
      } catch (error) {
        console.error('Failed to load Amazon status:', error);
        setAmazonStatus({ connected: false, loading: false });
      }
    };

    if (user) {
      loadAmazonStatus();
    }
  }, [user]);

  const handleConnectAmazon = () => {
    // Redirect to Amazon OAuth on backend
    window.location.href = API_ENDPOINTS.AMAZON_AUTH;
  };

  const handleDisconnectAmazon = async () => {
    if (!window.confirm('Are you sure you want to disconnect your Amazon Seller account? This will disable SP-API data access.')) {
      return;
    }

    try {
      await axios.post('/api/amazon-seller/disconnect', {}, { withCredentials: true });
      setAmazonStatus({ connected: false, loading: false });
      setMessage({ type: 'success', text: 'Amazon account disconnected successfully!' });
      
      // Update user context
      updateUser({
        amazon_connected: false,
        amazon_connected_at: null
      });
    } catch (error) {
      setMessage({ 
        type: 'error', 
        text: error.response?.data?.error || 'Failed to disconnect Amazon account' 
      });
    }
  };

  const handleTestConnection = async () => {
    setTestingConnection(true);
    setMessage({ type: '', text: '' });

    try {
      const response = await axios.get('/api/amazon-seller/test', { withCredentials: true });
      
      if (response.data.success) {
        setMessage({ 
          type: 'success', 
          text: `SP-API connection successful! (${response.data.sandbox_mode ? 'Sandbox' : 'Production'} mode)` 
        });
      } else {
        setMessage({ 
          type: 'error', 
          text: `Connection test failed: ${response.data.error}` 
        });
      }
    } catch (error) {
      setMessage({ 
        type: 'error', 
        text: error.response?.data?.error || 'Connection test failed' 
      });
    } finally {
      setTestingConnection(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage({ type: '', text: '' });

    try {
      const response = await axios.post('/api/user/profile', formData, { withCredentials: true });
      setMessage({ type: 'success', text: 'Settings updated successfully!' });
      
      // Update user context
      updateUser({
        user_record: {
          ...user.user_record,
          ...formData
        }
      });
    } catch (error) {
      setMessage({ 
        type: 'error', 
        text: error.response?.data?.error || 'Failed to update settings' 
      });
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center space-x-3">
        <SettingsIcon className="h-8 w-8 text-builders-500" />
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Account Settings</h1>
          <p className="text-gray-600">Manage your profile and bot configuration</p>
        </div>
      </div>

      {/* Settings Form */}
      <div className="card max-w-2xl">
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Message Display */}
          {message.text && (
            <div className={`flex items-center space-x-2 p-4 rounded-md ${
              message.type === 'success' 
                ? 'bg-green-50 text-green-800 border border-green-200' 
                : 'bg-red-50 text-red-800 border border-red-200'
            }`}>
              {message.type === 'success' ? (
                <CheckCircle className="h-5 w-5" />
              ) : (
                <AlertCircle className="h-5 w-5" />
              )}
              <span>{message.text}</span>
            </div>
          )}

          {/* Email Configuration */}
          <div>
            <label htmlFor="email" className="flex items-center space-x-2 text-sm font-medium text-gray-700 mb-2">
              <Mail className="h-4 w-4" />
              <span>Email Address</span>
            </label>
            <input
              type="email"
              id="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              className="input-field"
              placeholder="your-email@example.com"
              required
            />
            <p className="text-xs text-gray-500 mt-1">
              Email address where reports and notifications will be sent
            </p>
          </div>

          {/* Listing Loader Key */}
          <div>
            <label htmlFor="listing_loader_key" className="flex items-center space-x-2 text-sm font-medium text-gray-700 mb-2">
              <FileText className="h-4 w-4" />
              <span>Listing Loader Key</span>
            </label>
            <input
              type="text"
              id="listing_loader_key"
              name="listing_loader_key"
              value={formData.listing_loader_key}
              onChange={handleChange}
              className="input-field"
              placeholder="your-listing-loader-file"
            />
            <p className="text-xs text-gray-500 mt-1">
              Name of your listing loader file (without .xlsm extension)
            </p>
          </div>

          {/* Sellerboard File Key */}
          <div>
            <label htmlFor="sb_file_key" className="flex items-center space-x-2 text-sm font-medium text-gray-700 mb-2">
              <FileText className="h-4 w-4" />
              <span>Sellerboard File Key</span>
            </label>
            <input
              type="text"
              id="sb_file_key"
              name="sb_file_key"
              value={formData.sb_file_key}
              onChange={handleChange}
              className="input-field"
              placeholder="your-sellerboard-file"
            />
            <p className="text-xs text-gray-500 mt-1">
              Name of your sellerboard file (without .xlsx extension)
            </p>
          </div>

          {/* Sellerboard Orders URL */}
          <div>
            <label htmlFor="sellerboard_orders_url" className="flex items-center space-x-2 text-sm font-medium text-gray-700 mb-2">
              <Link className="h-4 w-4" />
              <span>Sellerboard Orders Report URL</span>
            </label>
            <input
              type="url"
              id="sellerboard_orders_url"
              name="sellerboard_orders_url"
              value={formData.sellerboard_orders_url}
              onChange={handleChange}
              className="input-field"
              placeholder="https://app.sellerboard.com/en/automation/reports?id=..."
            />
            <p className="text-xs text-gray-500 mt-1">
              The automation URL for your Sellerboard orders report (includes orders data for analytics)
            </p>
          </div>

          {/* Sellerboard Stock URL */}
          <div>
            <label htmlFor="sellerboard_stock_url" className="flex items-center space-x-2 text-sm font-medium text-gray-700 mb-2">
              <Link className="h-4 w-4" />
              <span>Sellerboard Stock Report URL</span>
            </label>
            <input
              type="url"
              id="sellerboard_stock_url"
              name="sellerboard_stock_url"
              value={formData.sellerboard_stock_url}
              onChange={handleChange}
              className="input-field"
              placeholder="https://app.sellerboard.com/en/automation/reports?id=..."
            />
            <p className="text-xs text-gray-500 mt-1">
              The automation URL for your Sellerboard stock report (includes inventory and stock data)
            </p>
          </div>

          {/* Timezone Selector */}
          <div>
            <label htmlFor="timezone" className="flex items-center space-x-2 text-sm font-medium text-gray-700 mb-2">
              <Clock className="h-4 w-4" />
              <span>Timezone</span>
            </label>
            <select
              id="timezone"
              name="timezone"
              value={formData.timezone}
              onChange={handleChange}
              className="input-field"
            >
              <option value="">Select your timezone...</option>
              {COMMON_TIMEZONES.map((tz) => (
                <option key={tz.value} value={tz.value}>
                  {tz.label}
                </option>
              ))}
            </select>
            <p className="text-xs text-gray-500 mt-1">
              Your timezone affects when the Overview switches from yesterday's to today's data (switches at 11:59 PM in your timezone)
            </p>
          </div>

          {/* Amazon Listing Loader & Sellerboard Toggle */}
          <div>
            <label className="flex items-center justify-between cursor-pointer">
              <div className="flex items-center space-x-2">
                {formData.run_scripts ? (
                  <ToggleRight className="h-6 w-6 text-green-500" />
                ) : (
                  <ToggleLeft className="h-6 w-6 text-gray-400" />
                )}
                <span className="text-sm font-medium text-gray-700">Amazon Listing Loader & Sellerboard Automation</span>
              </div>
              <input
                type="checkbox"
                name="run_scripts"
                checked={formData.run_scripts}
                onChange={handleChange}
                className="sr-only"
              />
            </label>
            <p className="text-xs text-gray-500 mt-1">
              Automatically run Amazon listing loader scripts and Sellerboard analytics
            </p>
          </div>

          {/* Prep Center Sheet Toggle */}
          <div>
            <label className="flex items-center justify-between cursor-pointer">
              <div className="flex items-center space-x-2">
                {formData.run_prep_center ? (
                  <ToggleRight className="h-6 w-6 text-green-500" />
                ) : (
                  <ToggleLeft className="h-6 w-6 text-gray-400" />
                )}
                <span className="text-sm font-medium text-gray-700">Prep Center Sheet Automation</span>
              </div>
              <input
                type="checkbox"
                name="run_prep_center"
                checked={formData.run_prep_center}
                onChange={handleChange}
                className="sr-only"
              />
            </label>
            <p className="text-xs text-gray-500 mt-1">
              Automatically update and upload prep center sheets
            </p>
          </div>

          {/* Source Links Toggle */}
          <div>
            <label className="flex items-center justify-between cursor-pointer">
              <div className="flex items-center space-x-2">
                {formData.enable_source_links ? (
                  <ToggleRight className="h-6 w-6 text-green-500" />
                ) : (
                  <ToggleLeft className="h-6 w-6 text-gray-400" />
                )}
                <span className="text-sm font-medium text-gray-700">Source Links from Google Sheet</span>
              </div>
              <input
                type="checkbox"
                name="enable_source_links"
                checked={formData.enable_source_links}
                onChange={handleChange}
                className="sr-only"
              />
            </label>
            <p className="text-xs text-gray-500 mt-1">
              Pull COGS and Source links from your Google Sheet for restock recommendations (disabled by default for privacy)
            </p>
          </div>

          {/* Search All Worksheets Toggle - only show when source links are enabled */}
          {formData.enable_source_links && (
            <div>
              <label className="flex items-center justify-between cursor-pointer">
                <div className="flex items-center space-x-2">
                  {formData.search_all_worksheets ? (
                    <ToggleRight className="h-6 w-6 text-green-500" />
                  ) : (
                    <ToggleLeft className="h-6 w-6 text-gray-400" />
                  )}
                  <span className="text-sm font-medium text-gray-700">Search All Worksheets</span>
                </div>
                <input
                  type="checkbox"
                  name="search_all_worksheets"
                  checked={formData.search_all_worksheets}
                  onChange={handleChange}
                  className="sr-only"
                />
              </label>
              <p className="text-xs text-gray-500 mt-1">
                Search through all worksheets in your Google Sheet for COGS data (instead of just the mapped worksheet). All worksheets must have the same column structure: Date, Store and Source Link, ASIN, COGS.
              </p>
            </div>
          )}

          {/* Submit Button */}
          <div className="flex justify-end">
            <button
              type="submit"
              disabled={loading}
              className="btn-primary flex items-center space-x-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Save className="h-4 w-4" />
              <span>{loading ? 'Saving...' : 'Save Settings'}</span>
            </button>
          </div>
        </form>
      </div>

      {/* Account Information */}
      <div className="card max-w-2xl">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Account Information</h3>
        <div className="space-y-4">
          <div className="flex justify-between items-center py-2 border-b border-gray-200">
            <span className="text-sm font-medium text-gray-600">Discord Username</span>
            <span className="text-sm text-gray-900">{user?.discord_username}</span>
          </div>
          <div className="flex justify-between items-center py-2 border-b border-gray-200">
            <span className="text-sm font-medium text-gray-600">Discord ID</span>
            <span className="text-sm text-gray-900">{user?.discord_id}</span>
          </div>
          <div className="flex justify-between items-center py-2 border-b border-gray-200">
            <span className="text-sm font-medium text-gray-600">Google Account</span>
            <span className={`text-sm ${user?.google_linked ? 'text-green-600' : 'text-red-600'}`}>
              {user?.google_linked ? 'Connected' : 'Not Connected'}
            </span>
          </div>
          <div className="flex justify-between items-center py-2 border-b border-gray-200">
            <span className="text-sm font-medium text-gray-600">Sheet Configuration</span>
            <span className={`text-sm ${user?.sheet_configured ? 'text-green-600' : 'text-red-600'}`}>
              {user?.sheet_configured ? 'Configured' : 'Not Configured'}
            </span>
          </div>
          <div className="flex justify-between items-center py-2 border-b border-gray-200">
            <span className="text-sm font-medium text-gray-600">Amazon Seller Account</span>
            <span className={`text-sm ${amazonStatus.connected ? 'text-green-600' : 'text-red-600'}`}>
              {amazonStatus.loading ? 'Loading...' : (amazonStatus.connected ? 'Connected' : 'Not Connected')}
            </span>
          </div>
          <div className="flex justify-between items-center py-2">
            <span className="text-sm font-medium text-gray-600">Profile Status</span>
            <span className={`text-sm ${user?.profile_configured ? 'text-green-600' : 'text-red-600'}`}>
              {user?.profile_configured ? 'Complete' : 'Incomplete'}
            </span>
          </div>
        </div>
      </div>

      {/* Amazon Connection */}
      <div className="card max-w-2xl">
        <div className="flex items-center space-x-3 mb-4">
          <ShoppingBag className="h-5 w-5 text-orange-500" />
          <h3 className="text-lg font-semibold text-gray-900">Amazon Seller Connection</h3>
        </div>
        
        {amazonStatus.loading ? (
          <div className="text-center py-4">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-builders-500 mx-auto"></div>
            <p className="text-sm text-gray-500 mt-2">Loading connection status...</p>
          </div>
        ) : user?.is_admin ? (
          amazonStatus.connected ? (
          <div className="bg-green-50 border border-green-200 rounded-md p-4">
            <div className="flex items-start space-x-3">
              <CheckCircle className="h-5 w-5 text-green-500 mt-0.5" />
              <div className="flex-1">
                <h4 className="text-sm font-medium text-green-900">Amazon Account Connected</h4>
                <p className="text-sm text-green-700 mb-3">
                  Your Amazon Seller account is connected and ready to use. Analytics data will now come directly from Amazon's SP-API instead of Sellerboard.
                </p>
                {amazonStatus.connected_at && (
                  <p className="text-xs text-green-600 mb-3">
                    Connected on: {new Date(amazonStatus.connected_at).toLocaleDateString()}
                  </p>
                )}
                {amazonStatus.selling_partner_id && (
                  <p className="text-xs text-green-600 mb-3">
                    Seller ID: {amazonStatus.selling_partner_id}
                  </p>
                )}
                <button 
                  onClick={handleDisconnectAmazon}
                  className="text-sm bg-red-600 hover:bg-red-700 text-white px-3 py-1 rounded-md transition-colors duration-200"
                >
                  Disconnect Amazon Account
                </button>
              </div>
            </div>
          </div>
        ) : (
          <div className="bg-blue-50 border border-blue-200 rounded-md p-4">
            <div className="flex items-start space-x-3">
              <AlertCircle className="h-5 w-5 text-blue-500 mt-0.5" />
              <div className="flex-1">
                <h4 className="text-sm font-medium text-blue-900">Amazon SP-API Available</h4>
                <p className="text-sm text-blue-700 mb-3">
                  Amazon SP-API is currently configured through shared credentials. Your analytics data comes directly from Amazon's API.
                  Individual account connection is available for production apps.
                </p>
                <div className="text-xs text-blue-600 mb-3 space-y-1">
                  <p>• ✅ Real-time order and inventory data</p>
                  <p>• ✅ Direct Amazon API integration</p>
                  <p>• ✅ More accurate than Sellerboard exports</p>
                  <p>• 🔄 Shared credentials ({amazonStatus.sandbox_mode ? 'sandbox' : 'production'} mode)</p>
                  {amazonStatus.env_credentials_available && <p>• ✅ Environment credentials loaded</p>}
                </div>
                <div className="flex space-x-2">
                  <button 
                    onClick={handleTestConnection}
                    disabled={testingConnection}
                    className="flex items-center space-x-2 text-sm bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white px-3 py-2 rounded-md transition-colors duration-200"
                  >
                    {testingConnection ? (
                      <>
                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                        <span>Testing...</span>
                      </>
                    ) : (
                      <>
                        <CheckCircle className="h-4 w-4" />
                        <span>Test Connection</span>
                      </>
                    )}
                  </button>
                  <button 
                    onClick={handleConnectAmazon}
                    disabled
                    className="flex items-center space-x-2 text-sm bg-gray-400 text-white px-3 py-2 rounded-md cursor-not-allowed opacity-50"
                  >
                    <ExternalLink className="h-4 w-4" />
                    <span>Individual Connection (Coming Soon)</span>
                  </button>
                </div>
                <p className="text-xs text-blue-600 mt-2">
                  Individual account connection will be available when the SP-API app moves to production status.
                </p>
              </div>
            </div>
          </div>
          )
        ) : (
          <div className="bg-gray-50 border border-gray-200 rounded-md p-4">
            <div className="flex items-start space-x-3">
              <ShoppingBag className="h-5 w-5 text-gray-500 mt-0.5" />
              <div className="flex-1">
                <h4 className="text-sm font-medium text-gray-900">Sellerboard Integration Active</h4>
                <p className="text-sm text-gray-700 mb-3">
                  Your analytics are powered by Sellerboard data. Configure your Sellerboard URLs in the settings above to get started.
                </p>
                <div className="text-xs text-gray-600 mb-3 space-y-1">
                  <p>• ✅ Reliable order and inventory data</p>
                  <p>• ✅ Proven analytics pipeline</p>
                  <p>• ✅ Full restock and stock alerts</p>
                  <p>• 📊 Sellerboard export integration</p>
                </div>
                <div className="text-xs text-gray-500">
                  Amazon SP-API integration is available for admin users and will be rolled out to all users once testing is complete.
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Danger Zone */}
      <div className="card max-w-2xl border-red-200">
        <h3 className="text-lg font-semibold text-red-900 mb-4">Danger Zone</h3>
        <div className="bg-red-50 border border-red-200 rounded-md p-4">
          <div className="flex items-start space-x-3">
            <AlertCircle className="h-5 w-5 text-red-500 mt-0.5" />
            <div>
              <h4 className="text-sm font-medium text-red-900">Reset Configuration</h4>
              <p className="text-sm text-red-700 mb-3">
                This will remove all your saved settings, Google account links, and sheet configurations. 
                This action cannot be undone.
              </p>
              <button className="text-sm bg-red-600 hover:bg-red-700 text-white px-3 py-1 rounded-md transition-colors duration-200">
                Reset All Settings
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Settings;