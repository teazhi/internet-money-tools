import React, { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { Save, AlertCircle, CheckCircle, Settings as SettingsIcon, Mail, FileText, ToggleLeft, ToggleRight, Link, Clock, ShoppingBag, ExternalLink, Eye, TestTube, Play, RefreshCw, Database } from 'lucide-react';
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
  const [demoMode, setDemoMode] = useState(false);
  const [formData, setFormData] = useState({
    email: '',
    listing_loader_key: '',
    sb_file_key: '',
    run_scripts: true,
    run_prep_center: false,
    sellerboard_orders_url: '',
    sellerboard_stock_url: '',
    sellerboard_cogs_url: '',
    timezone: '',
    enable_source_links: false,
    search_all_worksheets: false,
    disable_sp_api: false,
    amazon_lead_time_days: 90
  });
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState({ type: '', text: '' });
  const [amazonStatus, setAmazonStatus] = useState({ connected: false, loading: true });
  const [testingConnection, setTestingConnection] = useState(false);
  const [sellerboardUpdate, setSellerboardUpdate] = useState({ 
    loading: false, 
    status: '', 
    fullUpdate: false 
  });

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
        sellerboard_cogs_url: user.user_record.sellerboard_cogs_url || '',
        timezone: user.user_record.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone,
        enable_source_links: user.user_record.enable_source_links || false,
        search_all_worksheets: user.user_record.search_all_worksheets || false,
        disable_sp_api: user.user_record.disable_sp_api || false,
        amazon_lead_time_days: user.user_record.amazon_lead_time_days || 90
      });
    }
  }, [user]);

  // Check demo mode status
  useEffect(() => {
    const checkDemoMode = async () => {
      try {
        const response = await axios.get('/api/demo/status');
        setDemoMode(response.data.demo_mode);
      } catch (error) {
        // Failed to check demo mode - continue silently
      }
    };
    checkDemoMode();
  }, []);

  // Toggle demo mode
  const toggleDemoMode = async () => {
    try {
      const endpoint = demoMode ? '/api/demo/disable' : '/api/demo/enable';
      const response = await axios.post(endpoint);
      setDemoMode(response.data.demo_mode);
      setMessage({ 
        type: 'success', 
        text: response.data.message 
      });
    } catch (error) {
      setMessage({ 
        type: 'error', 
        text: 'Failed to toggle demo mode' 
      });
    }
  };

  // Load Amazon connection status
  useEffect(() => {
    const loadAmazonStatus = async () => {
      try {
        const response = await axios.get('/api/amazon-seller/status', { withCredentials: true });
        setAmazonStatus({ ...response.data, loading: false });
      } catch (error) {
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

  const handleDisconnectGoogle = async () => {
    if (!window.confirm('Are you sure you want to disconnect your Google account? This will reset your sheet configuration and require re-authorization with write permissions.')) {
      return;
    }
    try {
      await axios.post('/api/google/disconnect', {}, { withCredentials: true });
      setMessage({ type: 'success', text: 'Google account disconnected successfully!' });
      
      // Update user context
      updateUser({
        google_linked: false,
        sheet_configured: false
      });
    } catch (error) {
      setMessage({ 
        type: 'error', 
        text: error.response?.data?.error || 'Failed to disconnect Google account' 
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
      // For subusers, only send timezone update
      const dataToSend = user?.user_type === 'subuser' 
        ? { timezone: formData.timezone }
        : formData;
        
      const response = await axios.post('/api/user/profile', dataToSend, { withCredentials: true });
      setMessage({ 
        type: 'success', 
        text: user?.user_type === 'subuser' ? 'Timezone updated successfully!' : 'Settings updated successfully!' 
      });
      
      // Update user context
      updateUser({
        user_record: {
          ...user.user_record,
          ...dataToSend
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

  const handleManualSellerboardUpdate = async (fullUpdate = false) => {
    setSellerboardUpdate({ loading: true, status: 'Initiating update...', fullUpdate });
    setMessage({ type: '', text: '' });

    try {
      const response = await axios.post('/api/admin/manual-sellerboard-update', {
        full_update: fullUpdate
      }, { withCredentials: true });

      if (response.data.success) {
        setSellerboardUpdate({ 
          loading: false, 
          status: 'Update completed successfully!', 
          fullUpdate: false 
        });
        setMessage({ 
          type: 'success', 
          text: `Sellerboard ${fullUpdate ? 'full' : 'incremental'} update completed! Check your email for the updated file.` 
        });
      } else {
        throw new Error(response.data.error || 'Update failed');
      }
    } catch (error) {
      setSellerboardUpdate({ 
        loading: false, 
        status: 'Update failed', 
        fullUpdate: false 
      });
      setMessage({ 
        type: 'error', 
        text: error.response?.data?.error || 'Failed to trigger Sellerboard update' 
      });
    }
  };


  return (
    <div className="space-y-6">
      {/* Subuser Indicator Banner */}
      {user?.user_type === 'subuser' && (
        <div className="bg-blue-50 border border-blue-200 rounded-md p-4">
          <div className="flex items-center space-x-3">
            <Eye className="h-5 w-5 text-blue-600" />
            <div>
              <p className="text-sm font-medium text-blue-800">
                Assistant Account: Settings are managed by the main account holder
              </p>
              <p className="text-xs text-blue-700">
                You can only modify your timezone preference. All other settings are inherited from the main account.
              </p>
            </div>
          </div>
        </div>
      )}
      
      {/* Header */}
      <div className="flex items-center space-x-3">
        <SettingsIcon className="h-8 w-8 text-builders-500" />
        <div>
          <h1 className="text-xl font-bold text-gray-900">Account Settings</h1>
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
              {user?.user_type === 'subuser' && (
                <span className="text-xs text-gray-500 italic">(Managed by main user)</span>
              )}
            </label>
            <input
              type="email"
              id="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              disabled={user?.user_type === 'subuser'}
              className={`input-field ${user?.user_type === 'subuser' ? 'bg-gray-100 cursor-not-allowed' : ''}`}
              placeholder="your-email@example.com"
              required
            />
            <p className="text-xs text-gray-500 mt-1">
              Email address where reports and notifications will be sent
            </p>
          </div>

          {/* Listing Loader Key - Hidden for subusers */}
          {user?.user_type !== 'subuser' && (
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
          )}

          {/* Sellerboard File Key - Hidden for subusers */}
          {user?.user_type !== 'subuser' && (
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
          )}

          {/* Sellerboard URLs - Hidden for subusers */}
          {user?.user_type !== 'subuser' && (
            <>
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

              {/* Sellerboard COGS URL */}
              <div>
                <label htmlFor="sellerboard_cogs_url" className="flex items-center space-x-2 text-sm font-medium text-gray-700 mb-2">
                  <ShoppingBag className="h-4 w-4" />
                  <span>Sellerboard COGS Report URL (Cost of Goods Sold)</span>
                </label>
                <input
                  type="url"
                  id="sellerboard_cogs_url"
                  name="sellerboard_cogs_url"
                  value={formData.sellerboard_cogs_url}
                  onChange={handleChange}
                  className="input-field"
                  placeholder="https://app.sellerboard.com/en/automation/reports?id=..."
                />
                <div className="text-xs text-gray-500 mt-1">
                  <p className="mb-1">Complete inventory data for Missing Listings feature (includes all products, not just in-stock items)</p>
                  <p className="text-amber-600">
                    <strong>Important:</strong> Use the report URL format, NOT the direct download link. 
                    Go to Reports → Cost of Goods Sold → Share/Export → Copy the "Automated Report URL"
                  </p>
                </div>
              </div>
          </>
          )}

          {/* Timezone Selector */}
          <div>
            <label htmlFor="timezone" className="flex items-center space-x-2 text-sm font-medium text-gray-700 mb-2">
              <Clock className="h-4 w-4" />
              <span>Timezone</span>
              {user?.user_type === 'subuser' && (
                <span className="text-xs text-green-600 italic">(You can edit this)</span>
              )}
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

          {/* Amazon Lead Time Setting */}
          <div>
            <label htmlFor="amazon_lead_time_days" className="flex items-center space-x-2 text-sm font-medium text-gray-700 mb-2">
              <ShoppingBag className="h-4 w-4" />
              <span>Amazon Lead Time (Days)</span>
            </label>
            <input
              type="number"
              id="amazon_lead_time_days"
              name="amazon_lead_time_days"
              value={formData.amazon_lead_time_days}
              onChange={handleChange}
              min="30"
              max="180"
              step="1"
              className="input-field"
              placeholder="90"
            />
            <p className="text-xs text-gray-500 mt-1">
              How many days it takes for Amazon to receive and process your inventory shipments (affects restock recommendations)
            </p>
            <div className="text-xs text-gray-400 mt-1">
              <span className="font-medium">Common values:</span> 60 days (2 months), 90 days (3 months), 120 days (4 months)
            </div>
          </div>

          {/* Automation Toggles - Hidden for subusers */}
          {user?.user_type !== 'subuser' && (
            <>
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
          </>
          )}

          {/* Search All Worksheets Toggle - only show when source links are enabled and user is not subuser */}
          {user?.user_type !== 'subuser' && formData.enable_source_links && (
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
                Search through all worksheets in your Google Sheet for COGS and purchase data (instead of just the mapped worksheet). All worksheets must have columns that match your column mapping configuration above.
              </p>
            </div>
          )}

          {/* SP-API Disable Toggle (Admin Only) */}
          {user?.is_admin && (
            <div>
              <label className="flex items-center space-x-3 cursor-pointer">
                <div className="flex items-center">
                  {formData.disable_sp_api ? (
                    <ToggleRight className="h-6 w-6 text-red-500" />
                  ) : (
                    <ToggleLeft className="h-6 w-6 text-gray-400" />
                  )}
                  <span className="text-sm font-medium text-gray-700">Disable SP-API (Admin)</span>
                </div>
                <input
                  type="checkbox"
                  name="disable_sp_api"
                  checked={formData.disable_sp_api}
                  onChange={handleChange}
                  className="sr-only"
                />
              </label>
              <p className="text-xs text-gray-500 mt-1">
                Disable Amazon SP-API integration and use Sellerboard data only (even for admin users). Useful for testing or when SP-API is having issues.
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
              <span>{loading ? 'Saving...' : (user?.user_type === 'subuser' ? 'Save Timezone' : 'Save Settings')}</span>
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
            <div className="flex items-center space-x-2">
              <span className={`text-sm ${user?.google_linked ? 'text-green-600' : 'text-red-600'}`}>
                {user?.google_linked ? 'Connected' : 'Not Connected'}
              </span>
              {user?.google_linked && (
                <button
                  onClick={handleDisconnectGoogle}
                  className="text-xs bg-red-600 hover:bg-red-700 text-white px-2 py-1 rounded transition-colors duration-200"
                >
                  Disconnect
                </button>
              )}
            </div>
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
          <h3 className="text-sm font-semibold text-gray-900">Amazon Seller Connection</h3>
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

      {/* Manual Sellerboard Update - Only show for non-subusers */}
      {user?.user_type !== 'subuser' && (
        <div className="card max-w-2xl border-green-200">
          <div className="flex items-center space-x-3 mb-4">
            <Database className="h-5 w-5 text-green-500" />
            <h3 className="text-sm font-semibold text-green-900">Sellerboard Manual Update</h3>
          </div>
          
          <div className="bg-green-50 border border-green-200 rounded-md p-4">
            <div className="flex items-start space-x-3">
              <RefreshCw className="h-5 w-5 text-green-500 mt-0.5" />
              <div className="flex-1">
                <h4 className="text-sm font-medium text-green-900">Manual COGS Update</h4>
                <p className="text-sm text-green-700 mb-3">
                  Manually trigger a Sellerboard Cost of Goods update using your latest purchase data. 
                  The updated file will be sent to your email address.
                </p>
                
                {sellerboardUpdate.status && (
                  <div className={`text-sm p-2 rounded mb-3 ${
                    sellerboardUpdate.status.includes('successfully') 
                      ? 'bg-green-100 text-green-800' 
                      : sellerboardUpdate.status.includes('failed')
                      ? 'bg-red-100 text-red-800'
                      : 'bg-blue-100 text-blue-800'
                  }`}>
                    {sellerboardUpdate.status}
                  </div>
                )}
                
                <div className="flex flex-col sm:flex-row gap-2">
                  <button 
                    onClick={() => handleManualSellerboardUpdate(false)}
                    disabled={sellerboardUpdate.loading}
                    className="flex items-center space-x-2 text-sm bg-green-600 hover:bg-green-700 disabled:bg-green-400 text-white px-3 py-2 rounded-md transition-colors duration-200"
                  >
                    {sellerboardUpdate.loading && !sellerboardUpdate.fullUpdate ? (
                      <>
                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                        <span>Processing...</span>
                      </>
                    ) : (
                      <>
                        <Play className="h-4 w-4" />
                        <span>Quick Update</span>
                      </>
                    )}
                  </button>
                  
                  <button 
                    onClick={() => handleManualSellerboardUpdate(true)}
                    disabled={sellerboardUpdate.loading}
                    className="flex items-center space-x-2 text-sm bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white px-3 py-2 rounded-md transition-colors duration-200"
                  >
                    {sellerboardUpdate.loading && sellerboardUpdate.fullUpdate ? (
                      <>
                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                        <span>Processing...</span>
                      </>
                    ) : (
                      <>
                        <Database className="h-4 w-4" />
                        <span>Full Update</span>
                      </>
                    )}
                  </button>
                </div>
                
                <div className="text-xs text-green-600 mt-3 space-y-1">
                  <p><strong>Quick Update:</strong> Processes purchases since last update (faster)</p>
                  <p><strong>Full Update:</strong> Processes all purchase data regardless of date (thorough)</p>
                  <p className="text-green-500">• Updated Sellerboard file will be emailed to you</p>
                  <p className="text-green-500">• AI uploader template included for new products</p>
                  <p className="text-green-500">• Uses your configured Sellerboard COGS URL</p>
                </div>
                
                {!formData.sellerboard_cogs_url && (
                  <div className="text-xs text-amber-600 mt-2 p-2 bg-amber-50 rounded border border-amber-200">
                    <strong>Note:</strong> Configure your Sellerboard COGS URL above to use this feature.
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Demo Mode Controls */}
      <div className="card max-w-2xl border-blue-200">
        <h3 className="text-sm font-semibold text-blue-900 mb-4 flex items-center space-x-2">
          <TestTube className="h-4 w-4" />
          <span>Demo Mode</span>
        </h3>
        <div className="bg-blue-50 border border-blue-200 rounded-md p-4">
          <div className="flex items-start space-x-3">
            <Eye className="h-5 w-5 text-blue-500 mt-0.5" />
            <div className="flex-1">
              <h4 className="text-sm font-medium text-blue-900">Demonstration Mode</h4>
              <p className="text-sm text-blue-700 mb-3">
                {demoMode 
                  ? "Demo mode is currently enabled. All data is simulated for demonstration purposes."
                  : "Demo mode is disabled. Using real application data."
                }
              </p>
              <button 
                onClick={toggleDemoMode}
                className={`text-sm px-3 py-1 rounded-md transition-colors duration-200 ${
                  demoMode 
                    ? "bg-red-600 hover:bg-red-700 text-white" 
                    : "bg-blue-600 hover:bg-blue-700 text-white"
                }`}
              >
                {demoMode ? "Disable Demo Mode" : "Enable Demo Mode"}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Danger Zone */}
      <div className="card max-w-2xl border-red-200">
        <h3 className="text-sm font-semibold text-red-900 mb-4">Danger Zone</h3>
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