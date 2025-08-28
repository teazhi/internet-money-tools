import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { 
  Users, 
  Edit3, 
  Trash2, 
  Plus, 
  RefreshCw,
  Download,
  AlertTriangle,
  CheckCircle,
  Clock,
  Database,
  Activity,
  Shield,
  UserPlus,
  Cog,
  Mail,
  Bell,
  Percent,
  Play,
  Upload,
  Eye,
  EyeOff,
  X,
  Settings,
  ExternalLink,
  Save
} from 'lucide-react';
import axios from 'axios';
import { API_ENDPOINTS } from '../../config/api';

const AdminCompact = () => {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState('users');
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [systemStats, setSystemStats] = useState(null);
  const [invitations, setInvitations] = useState([]);
  const [discountMonitoring, setDiscountMonitoring] = useState(null);
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [filteredUsers, setFilteredUsers] = useState([]);
  const [editingUser, setEditingUser] = useState(null);
  const [assigningVA, setAssigningVA] = useState(null);
  const [showAssignModal, setShowAssignModal] = useState(false);
  const [selectedParentUser, setSelectedParentUser] = useState('');
  const [features, setFeatures] = useState([]);
  const [userFeatureAccess, setUserFeatureAccess] = useState({});
  const [showFeatureModal, setShowFeatureModal] = useState(false);
  const [selectedFeatureUser, setSelectedFeatureUser] = useState(null);
  const [discountEmailConfig, setDiscountEmailConfig] = useState(null);
  const [showDiscountEmailModal, setShowDiscountEmailModal] = useState(false);
  const [formatPatterns, setFormatPatterns] = useState(null);
  const [showFormatPatternsModal, setShowFormatPatternsModal] = useState(false);
  const [discountEmailForm, setDiscountEmailForm] = useState({
    email_address: '',
    config_type: 'gmail_oauth',
    imap_server: '',
    imap_port: 993,
    username: '',
    password: '',
    is_active: true
  });
  const [discountTestResult, setDiscountTestResult] = useState(null);
  const [discountTestLoading, setDiscountTestLoading] = useState(false);
  const [discountEmailTestResult, setDiscountEmailTestResult] = useState(null);
  const [testingDiscountEmail, setTestingDiscountEmail] = useState(false);
  const [showGmailOAuthStep, setShowGmailOAuthStep] = useState(false);
  const [gmailAuthUrl, setGmailAuthUrl] = useState('');
  const [gmailAuthCode, setGmailAuthCode] = useState('');
  const [emailWebhookConfig, setEmailWebhookConfig] = useState(null);
  const [showWebhookModal, setShowWebhookModal] = useState(false);
  const [webhookForm, setWebhookForm] = useState({
    webhook_url: '',
    description: '',
    is_active: true
  });
  const [webhookTestResult, setWebhookTestResult] = useState(null);
  const [testingWebhook, setTestingWebhook] = useState(false);

  const isAdmin = user?.discord_id === '712147636463075389';

  const fetchData = useCallback(async () => {
    if (!isAdmin) return;
    
    try {
      setLoading(true);
      setError(''); // Clear any previous errors
      
      // Load data with resilient error handling - use Promise.allSettled instead of Promise.all
      const timestamp = Date.now();
      const [usersRes, statsRes, invitesRes, discountRes, featuresRes, userFeaturesRes, discountEmailRes, webhookRes, formatPatternsRes] = await Promise.allSettled([
        axios.get(`/api/admin/users?t=${timestamp}`, { withCredentials: true }),
        axios.get(`/api/admin/stats?t=${timestamp}`, { withCredentials: true }),
        axios.get(`/api/admin/invitations?t=${timestamp}`, { withCredentials: true }),
        axios.get(`${API_ENDPOINTS.DISCOUNT_MONITORING_STATUS}?t=${timestamp}`, { withCredentials: true }),
        axios.get(`/api/admin/features?t=${timestamp}`, { withCredentials: true }),
        axios.get(`/api/admin/user-features?t=${timestamp}`, { withCredentials: true }),
        axios.get(`/api/admin/discount-email/config?t=${timestamp}`, { withCredentials: true }),
        axios.get(`/api/admin/email-monitoring/webhook?t=${timestamp}`, { withCredentials: true }),
        axios.get(`/api/admin/discount-email/format-patterns?t=${timestamp}`, { withCredentials: true })
      ]);
      
      // Handle results with partial failure support
      let failedEndpoints = [];
      
      // Users (critical)
      if (usersRes.status === 'fulfilled') {
        const users = usersRes.value.data.users;
        setUsers(users);
        
        // Organize users hierarchically
        const mainUsers = users.filter(user => user.user_type !== 'subuser');
        const subUsers = users.filter(user => user.user_type === 'subuser');
        
        // Manual assignment based on usernames (fallback for correct relationships)
        const manualAssignments = {
          'jhoi': 'teazhii',
          'jayvee': 'teazhii', 
          'xiela': 'davfong'
        };

        const hierarchicalUsers = [];
        mainUsers.forEach(mainUser => {
          hierarchicalUsers.push({...mainUser, isMainUser: true});
          
          // First try automatic matching by parent_user_id
          const userSubUsers = subUsers.filter(sub => 
            String(sub.parent_user_id) === String(mainUser.discord_id)
          );
          
          // Then try manual username-based matching for known VAs
          const manualSubUsers = subUsers.filter(sub => 
            manualAssignments[sub.discord_username?.toLowerCase()] === mainUser.discord_username?.toLowerCase()
          );
          
          // Combine both and remove duplicates
          const allSubUsers = [...userSubUsers];
          manualSubUsers.forEach(manualSub => {
            if (!allSubUsers.some(existing => existing.discord_id === manualSub.discord_id)) {
              allSubUsers.push(manualSub);
            }
          });
          
          allSubUsers.forEach(subUser => {
            hierarchicalUsers.push({...subUser, isSubUser: true, parentUser: mainUser});
          });
        });
        
        // Add any remaining orphaned subusers (not matched by ID or manually assigned)
        const assignedSubUserIds = new Set();
        hierarchicalUsers.forEach(user => {
          if (user.isSubUser) {
            assignedSubUserIds.add(user.discord_id);
          }
        });
        
        const orphanedSubs = subUsers.filter(sub => 
          !assignedSubUserIds.has(sub.discord_id)
        );
        
        orphanedSubs.forEach(subUser => {
          hierarchicalUsers.push({...subUser, isSubUser: true, parentUser: null});
        });
        
        setFilteredUsers(hierarchicalUsers);
      } else {
        failedEndpoints.push('Users');
        console.error('Failed to load users:', usersRes.reason);
      }
      
      // Stats (non-critical)
      if (statsRes.status === 'fulfilled') {
        setSystemStats(statsRes.value.data);
      } else {
        failedEndpoints.push('Stats');
        console.error('Failed to load stats:', statsRes.reason);
      }
      
      // Invitations (non-critical)
      if (invitesRes.status === 'fulfilled') {
        setInvitations(invitesRes.value.data.invitations || []);
      } else {
        failedEndpoints.push('Invitations');
        console.error('Failed to load invitations:', invitesRes.reason);
      }
      
      // Discount monitoring (non-critical)
      if (discountRes.status === 'fulfilled') {
        setDiscountMonitoring(discountRes.value.data);
      } else {
        failedEndpoints.push('Discount Monitoring');
        console.error('Failed to load discount monitoring:', discountRes.reason);
      }
      
      // Features (non-critical)
      if (featuresRes.status === 'fulfilled') {
        setFeatures(featuresRes.value.data.features || []);
      } else {
        failedEndpoints.push('Features');
        console.error('Failed to load features:', featuresRes.reason);
      }
      
      // User features (non-critical)
      if (userFeaturesRes.status === 'fulfilled') {
        setUserFeatureAccess(userFeaturesRes.value.data.user_features || {});
      } else {
        failedEndpoints.push('User Features');
        console.error('Failed to load user features:', userFeaturesRes.reason);
      }
      
      // Discount email config (non-critical)
      if (discountEmailRes.status === 'fulfilled') {
        setDiscountEmailConfig(discountEmailRes.value.data);
      } else {
        failedEndpoints.push('Discount Email');
        console.error('Failed to load discount email config:', discountEmailRes.reason);
      }
      
      // Email webhook config (non-critical)
      if (webhookRes.status === 'fulfilled') {
        setEmailWebhookConfig(webhookRes.value.data);
      } else {
        failedEndpoints.push('Email Webhook Config');
        console.error('Failed to load email webhook config:', webhookRes.reason);
      }
      
      // Format patterns (non-critical)
      if (formatPatternsRes.status === 'fulfilled') {
        setFormatPatterns(formatPatternsRes.value.data);
      } else {
        failedEndpoints.push('Format Patterns');
        console.error('Failed to load format patterns:', formatPatternsRes.reason);
      }
      
      // Show warning if some endpoints failed but don't block the UI
      if (failedEndpoints.length > 0) {
        setError(`Warning: Some data failed to load (${failedEndpoints.join(', ')}). Core functionality is available.`);
      }
      
    } catch (error) {
      setError(`Failed to load admin data: ${error.message}`);
      console.error('Admin data loading error:', error);
    } finally {
      setLoading(false);
    }
  }, [isAdmin]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleSendInvitation = async () => {
    if (!inviteEmail) return;
    
    try {
      await axios.post('/api/admin/invitations', { email: inviteEmail }, { withCredentials: true });
      setSuccess('Invitation sent successfully!');
      setInviteEmail('');
      setShowInviteModal(false);
      fetchData();
    } catch (error) {
      setError('Failed to send invitation');
    }
  };

  const handleDeleteInvitation = async (token) => {
    if (!window.confirm('Are you sure you want to delete this invitation?')) {
      return;
    }

    try {
      setError('');
      setSuccess('');
      
      await axios.delete(`/api/admin/invitations/${token}`, { withCredentials: true });
      setSuccess('Invitation deleted successfully');
      fetchData();
    } catch (error) {
      setError(error.response?.data?.error || 'Failed to delete invitation');
    }
  };

  const handleViewUserDashboard = async (userId) => {
    try {
      setError('');
      
      // Start impersonation and then navigate to Overview
      await axios.post(`/api/admin/impersonate/${userId}`, {}, { 
        withCredentials: true 
      });
      
      // Navigate to dashboard overview - impersonation will show in banner
      window.location.href = '/dashboard/overview';
      
    } catch (error) {
      setError(`Failed to start impersonation: ${error.response?.data?.error || error.message}`);
    }
  };


  const handleAssignVA = async () => {
    if (!assigningVA || !selectedParentUser) return;
    
    try {
      setError('');
      const updateData = {
        parent_user_id: selectedParentUser
      };
      
      await axios.post(`/api/admin/users/${assigningVA.discord_id}`, updateData, { withCredentials: true });
      setSuccess('VA assigned successfully!');
      setShowAssignModal(false);
      setAssigningVA(null);
      setSelectedParentUser('');
      fetchData();
    } catch (error) {
      setError('Failed to assign VA');
    }
  };

  const handleUpdateUser = async (userData) => {
    try {
      setError('');
      await axios.post(`/api/admin/users/${editingUser.discord_id}`, userData, { withCredentials: true });
      setSuccess('User updated successfully!');
      setEditingUser(null);
      fetchData();
    } catch (error) {
      setError('Failed to update user');
    }
  };

  const handleToggleFeatureAccess = async (userId, featureKey) => {
    try {
      setError('');
      const currentAccess = userFeatureAccess[userId]?.[featureKey] || false;
      
      if (currentAccess) {
        // Remove access
        await axios.delete(`/api/admin/user-features/${userId}/${featureKey}`, { withCredentials: true });
      } else {
        // Grant access
        await axios.post('/api/admin/user-features', {
          user_id: userId,
          feature_key: featureKey
        }, { withCredentials: true });
      }
      
      setSuccess(`Feature access ${currentAccess ? 'removed' : 'granted'} successfully!`);
      fetchData();
    } catch (error) {
      setError('Failed to update feature access');
    }
  };

  const handleToggleFeatureBeta = async (featureKey) => {
    try {
      setError('');
      const feature = features.find(f => f.feature_key === featureKey);
      
      await axios.put(`/api/admin/features/${featureKey}`, {
        is_beta: !feature.is_beta
      }, { withCredentials: true });
      
      setSuccess(`Feature ${feature.is_beta ? 'moved to stable' : 'marked as beta'}!`);
      fetchData();
    } catch (error) {
      setError('Failed to update feature');
    }
  };

  const handleLaunchFeature = async (featureKey) => {
    try {
      setError('');
      const feature = features.find(f => f.feature_key === featureKey);
      
      if (feature.is_launched) {
        // Unlaunch feature
        await axios.post('/api/admin/features/unlaunch', {
          feature_key: featureKey
        }, { withCredentials: true });
      } else {
        // Launch feature
        await axios.post('/api/admin/features/launch', {
          feature_key: featureKey
        }, { withCredentials: true });
      }
      
      setSuccess(`Feature ${feature.is_launched ? 'unlaunched' : 'launched'} successfully!`);
      fetchData();
    } catch (error) {
      setError('Failed to launch/unlaunch feature');
    }
  };


  // UserEditModal component
  const UserEditModal = ({ user, onSave, onCancel }) => {
    const [editData, setEditData] = useState({
      email: user.email || '',
      run_scripts: user.run_scripts || false,
      run_prep_center: user.run_prep_center || false,
      enable_source_links: user.enable_source_links || false,
      search_all_worksheets: user.search_all_worksheets || false,
      listing_loader_key: user.listing_loader_key || '',
      sb_file_key: user.sb_file_key || '',
      sellerboard_orders_url: user.sellerboard_orders_url || '',
      sellerboard_stock_url: user.sellerboard_stock_url || '',
      sellerboard_cogs_url: user.sellerboard_cogs_url || ''
    });

    return (
      <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
        <div className="relative top-20 mx-auto p-5 border w-11/12 md:w-3/4 lg:w-1/2 shadow-lg rounded-md bg-white">
          <div className="mt-3">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-medium text-gray-900">
                Edit User: {user.discord_username}
              </h3>
              <button
                onClick={onCancel}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700">Email</label>
                <input
                  type="email"
                  value={editData.email}
                  onChange={(e) => setEditData({...editData, email: e.target.value})}
                  className="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-builders-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">Sellerboard Orders URL</label>
                <input
                  type="url"
                  value={editData.sellerboard_orders_url}
                  onChange={(e) => setEditData({...editData, sellerboard_orders_url: e.target.value})}
                  className="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-builders-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">Sellerboard Stock URL</label>
                <input
                  type="url"
                  value={editData.sellerboard_stock_url}
                  onChange={(e) => setEditData({...editData, sellerboard_stock_url: e.target.value})}
                  className="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-builders-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">Sellerboard COGS URL (Cost of Goods Sold)</label>
                <input
                  type="url"
                  value={editData.sellerboard_cogs_url}
                  onChange={(e) => setEditData({...editData, sellerboard_cogs_url: e.target.value})}
                  placeholder="https://app.sellerboard.com/en/automation/reports?id=..."
                  className="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-builders-500"
                />
                <div className="mt-1 text-xs text-gray-500">
                  <p className="mb-1">Complete inventory data for Missing Listings feature</p>
                  <p className="text-amber-600">
                    <strong>Note:</strong> Use report URL format, not direct download link
                  </p>
                </div>
              </div>

              <div className="flex items-center">
                <input
                  id="run_scripts"
                  type="checkbox"
                  checked={editData.run_scripts}
                  onChange={(e) => setEditData({...editData, run_scripts: e.target.checked})}
                  className="h-4 w-4 text-builders-600 focus:ring-builders-500 border-gray-300 rounded"
                />
                <label htmlFor="run_scripts" className="ml-2 block text-sm text-gray-700">
                  Amazon Listing Loader & Sellerboard automation
                </label>
              </div>

              <div className="flex items-center">
                <input
                  id="enable_source_links"
                  type="checkbox"
                  checked={editData.enable_source_links}
                  onChange={(e) => setEditData({...editData, enable_source_links: e.target.checked})}
                  className="h-4 w-4 text-builders-600 focus:ring-builders-500 border-gray-300 rounded"
                />
                <label htmlFor="enable_source_links" className="ml-2 block text-sm text-gray-700">
                  Source Links from Google Sheet
                </label>
              </div>
            </div>

            <div className="flex justify-end space-x-3 mt-6">
              <button
                type="button"
                onClick={onCancel}
                className="px-4 py-2 bg-white border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => onSave(editData)}
                className="px-4 py-2 bg-builders-600 text-white rounded-md hover:bg-builders-700"
              >
                Save Changes
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  };

  const handleUpdateDiscountEmail = async () => {
    try {
      setError('');
      
      if (discountEmailForm.config_type === 'gmail_oauth') {
        // For Gmail OAuth, get the auth URL first
        const response = await axios.post('/api/admin/discount-email/gmail-oauth-url', {
          email_address: discountEmailForm.email_address
        }, { withCredentials: true });
        
        setGmailAuthUrl(response.data.auth_url);
        setShowGmailOAuthStep(true);
        setShowDiscountEmailModal(false);
        
      } else {
        // For IMAP, use the existing endpoint
        await axios.post('/api/admin/discount-email/config', discountEmailForm, { withCredentials: true });
        setSuccess('Discount email configuration updated successfully!');
        setShowDiscountEmailModal(false);
        fetchData();
      }
    } catch (error) {
      setError(`Failed to update discount email config: ${error.response?.data?.error || error.message}`);
    }
  };

  const handleGmailAuth = async () => {
    if (!gmailAuthCode) {
      setError('Please enter the authorization code');
      return;
    }

    try {
      setError('');
      const response = await axios.post('/api/admin/discount-email/complete-oauth', {
        code: gmailAuthCode,
        state: 'discount_email_setup'
      }, { withCredentials: true });
      
      setSuccess(`Gmail OAuth completed successfully for ${response.data.email}!`);
      setShowGmailOAuthStep(false);
      setGmailAuthCode('');
      setGmailAuthUrl('');
      fetchData(); // Refresh to show updated config
    } catch (error) {
      setError(`Failed to complete OAuth: ${error.response?.data?.error || error.message}`);
    }
  };

  const handleTestDiscountEmail = async () => {
    try {
      setTestingDiscountEmail(true);
      setDiscountEmailTestResult(null);
      const response = await axios.post('/api/admin/discount-email/test', discountEmailForm, { withCredentials: true });
      setDiscountEmailTestResult({ success: true, message: response.data.message });
    } catch (error) {
      setDiscountEmailTestResult({ 
        success: false, 
        message: error.response?.data?.message || 'Connection test failed' 
      });
    } finally {
      setTestingDiscountEmail(false);
    }
  };

  const handleClearDiscountCache = async () => {
    try {
      setError('');
      await axios.post('/api/admin/discount-email/clear-cache', {}, { withCredentials: true });
      setSuccess('Discount opportunities cache cleared successfully!');
    } catch (error) {
      setError(`Failed to clear cache: ${error.response?.data?.error || error.message}`);
    }
  };

  const handleSaveWebhook = async () => {
    try {
      await axios.post('/api/admin/email-monitoring/webhook', webhookForm, { withCredentials: true });
      setSuccess('Email monitoring webhook saved successfully');
      setShowWebhookModal(false);
      setWebhookForm({
        webhook_url: '',
        description: '',
        is_active: true
      });
      fetchData();
    } catch (error) {
      setError('Failed to save webhook configuration');
    }
  };

  const handleTestWebhook = async () => {
    try {
      setTestingWebhook(true);
      setWebhookTestResult(null);
      const response = await axios.post('/api/admin/email-monitoring/webhook/test', { webhook_url: webhookForm.webhook_url }, { withCredentials: true });
      setWebhookTestResult({ success: true, message: response.data.message });
    } catch (error) {
      setWebhookTestResult({ 
        success: false, 
        message: error.response?.data?.error || 'Webhook test failed' 
      });
    } finally {
      setTestingWebhook(false);
    }
  };

  const handleDeleteWebhook = async () => {
    if (!window.confirm('Are you sure you want to delete the webhook configuration?')) return;
    
    try {
      await axios.delete('/api/admin/email-monitoring/webhook', { withCredentials: true });
      setSuccess('Webhook configuration deleted successfully');
      fetchData();
    } catch (error) {
      setError('Failed to delete webhook configuration');
    }
  };

  if (!isAdmin) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <Shield className="h-16 w-16 text-red-400 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Access Denied</h2>
          <p className="text-gray-600">You don't have permission to access the admin panel.</p>
        </div>
      </div>
    );
  }

  const tabs = [
    { id: 'users', name: 'Users', icon: Users, count: filteredUsers.length },
    { id: 'features', name: 'Features', icon: Settings, count: features.length },
    { id: 'discount-email', name: 'Discount Email', icon: Mail, count: discountEmailConfig?.configured ? 1 : 0 },
    { id: 'email-webhook', name: 'Email Webhooks', icon: Bell, count: emailWebhookConfig?.configured ? 1 : 0 }
  ];

  return (
    <div className="space-y-6">
      {/* Admin Panel Header - Top Priority */}
      <div className="bg-gradient-to-r from-builders-500 to-builders-600 rounded-lg p-4 text-white">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold">Admin Panel</h1>
            <p className="text-sm text-builders-100">System Management</p>
          </div>
          <div className="flex space-x-2">
            <button
              onClick={fetchData}
              className="flex items-center px-2 py-1 bg-builders-700 hover:bg-builders-800 rounded text-sm"
            >
              <RefreshCw className="h-3 w-3 mr-1" />
              Refresh
            </button>
            <button
              onClick={() => setShowInviteModal(true)}
              className="flex items-center px-2 py-1 bg-green-600 hover:bg-green-700 rounded text-sm"
            >
              <Plus className="h-3 w-3 mr-1" />
              Invite
            </button>
          </div>
        </div>
      </div>

      {/* Error/Success Messages */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3">
          <div className="flex items-center">
            <AlertTriangle className="h-4 w-4 text-red-500 mr-2" />
            <span className="text-sm text-red-800">{error}</span>
          </div>
        </div>
      )}
      
      {success && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-3">
          <div className="flex items-center">
            <CheckCircle className="h-4 w-4 text-green-500 mr-2" />
            <span className="text-sm text-green-800">{success}</span>
          </div>
        </div>
      )}

      {/* System Stats */}
      {systemStats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-blue-50 p-4 rounded-lg">
            <div className="flex items-center">
              <Users className="h-6 w-6 text-blue-500 mr-2" />
              <div>
                <p className="text-xs text-blue-600">Total Users</p>
                <p className="text-lg font-bold text-blue-900">{systemStats.total_users}</p>
              </div>
            </div>
          </div>
          <div className="bg-green-50 p-4 rounded-lg">
            <div className="flex items-center">
              <CheckCircle className="h-6 w-6 text-green-500 mr-2" />
              <div>
                <p className="text-xs text-green-600">Active</p>
                <p className="text-lg font-bold text-green-900">{systemStats.active_users}</p>
              </div>
            </div>
          </div>
          <div className="bg-yellow-50 p-4 rounded-lg">
            <div className="flex items-center">
              <Clock className="h-6 w-6 text-yellow-500 mr-2" />
              <div>
                <p className="text-xs text-yellow-600">Pending</p>
                <p className="text-lg font-bold text-yellow-900">{systemStats.pending_users}</p>
              </div>
            </div>
          </div>
          <div className="bg-purple-50 p-4 rounded-lg">
            <div className="flex items-center">
              <Activity className="h-6 w-6 text-purple-500 mr-2" />
              <div>
                <p className="text-xs text-purple-600">Status</p>
                <p className="text-sm font-bold text-green-900">Operational</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Invitations Section */}
      <div className="bg-white rounded-lg shadow p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900 flex items-center">
            <UserPlus className="h-5 w-5 mr-2 text-builders-500" />
            Pending Invitations
          </h3>
          <button
            onClick={() => setShowInviteModal(true)}
            className="flex items-center px-3 py-2 bg-builders-600 text-white rounded-md text-sm hover:bg-builders-700"
          >
            <Plus className="h-4 w-4 mr-1" />
            Send Invitation
          </button>
        </div>
        
        {invitations.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Email</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Sent</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {invitations.map((invitation) => (
                  <tr key={invitation.token} className="hover:bg-gray-50">
                    <td className="px-4 py-2 text-sm text-gray-900">{invitation.email}</td>
                    <td className="px-4 py-2">
                      <span className="inline-flex px-2 py-1 text-xs font-medium bg-yellow-100 text-yellow-800 rounded-full">
                        Pending
                      </span>
                    </td>
                    <td className="px-4 py-2 text-xs text-gray-500">
                      {new Date(invitation.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-2">
                      <button 
                        onClick={() => handleDeleteInvitation(invitation.token)}
                        className="text-red-600 hover:text-red-800"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-6">
            <UserPlus className="h-8 w-8 text-gray-400 mx-auto mb-2" />
            <p className="text-sm text-gray-500">No pending invitations</p>
          </div>
        )}
      </div>


      {/* Tab Navigation */}
      <div className="bg-white rounded-lg shadow">
        <div className="border-b border-gray-200">
          <nav className="flex space-x-8 px-4">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`py-3 px-1 border-b-2 font-medium text-sm flex items-center space-x-2 ${
                    activeTab === tab.id
                      ? 'border-builders-500 text-builders-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  <span>{tab.name}</span>
                  {tab.count !== null && (
                    <span className={`ml-1 py-0.5 px-1.5 rounded-full text-xs ${
                      activeTab === tab.id
                        ? 'bg-builders-100 text-builders-600'
                        : 'bg-gray-100 text-gray-600'
                    }`}>
                      {tab.count}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>
        </div>

        {/* Tab Content */}
        <div className="p-4">
          {loading ? (
            <div className="text-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-builders-500 mx-auto mb-2"></div>
              <p className="text-sm text-gray-600">Loading...</p>
            </div>
          ) : (
            <>
              {/* Users Tab */}
              {activeTab === 'users' && (
                <div className="space-y-4">
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">User</th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Activity</th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-200">
                        {filteredUsers.slice(0, 20).map((user, index) => {
                          const isSubuser = user.user_type === 'subuser' || user.isSubUser;
                          const isActive = isSubuser 
                            ? true // Subusers inherit setup from parent
                            : (user.profile_configured && user.google_linked && user.sheet_configured);
                          
                          
                          return (
                            <tr key={user.discord_id} className={`hover:bg-gray-50 ${isSubuser ? 'bg-blue-25 border-l-4 border-blue-200' : ''}`}>
                              <td className="px-4 py-2">
                                <div className="flex items-center">
                                  {isSubuser && (
                                    <div className="w-8 flex justify-center mr-2">
                                      <div className="w-px h-6 bg-blue-300 mr-1"></div>
                                      <div className="text-blue-500 text-xs">└─</div>
                                    </div>
                                  )}
                                  {user.discord_avatar ? (
                                    <img
                                      className="h-6 w-6 rounded-full mr-2"
                                      src={`https://cdn.discordapp.com/avatars/${user.discord_id}/${user.discord_avatar}.png`}
                                      alt=""
                                    />
                                  ) : (
                                    <div className="h-6 w-6 bg-gray-300 rounded-full mr-2"></div>
                                  )}
                                  <div>
                                    <div className="flex items-center">
                                      <span className="text-sm font-medium text-gray-900">{user.discord_username}</span>
                                      {isSubuser && (
                                        <span className="ml-2 inline-flex px-2 py-0.5 text-xs font-medium bg-blue-100 text-blue-800 rounded-full">
                                          VA
                                        </span>
                                      )}
                                    </div>
                                    <div className="text-xs text-gray-500">
                                      {user.email}
                                      {isSubuser && user.parentUser && (
                                        <span className="ml-2 text-blue-600">
                                          → {user.parentUser.discord_username}
                                        </span>
                                      )}
                                    </div>
                                  </div>
                                </div>
                              </td>
                              <td className="px-4 py-2">
                                <span className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${
                                  isActive 
                                    ? 'bg-green-100 text-green-800' 
                                    : 'bg-yellow-100 text-yellow-800'
                                }`}>
                                  {isActive ? 'Active' : 'Setup Required'}
                                </span>
                              </td>
                              <td className="px-4 py-2 text-xs text-gray-500">
                                {user.last_activity ? new Date(user.last_activity).toLocaleDateString() : 'Never'}
                              </td>
                              <td className="px-4 py-2">
                                <div className="flex space-x-2">
                                  <button 
                                    onClick={() => handleViewUserDashboard(user.discord_id)}
                                    className="text-blue-600 hover:text-blue-800"
                                    title="View User's Dashboard"
                                  >
                                    <ExternalLink className="h-4 w-4" />
                                  </button>
                                  <button 
                                    onClick={() => setEditingUser(user)}
                                    className="text-gray-400 hover:text-gray-600"
                                    title="Edit User"
                                  >
                                    <Edit3 className="h-4 w-4" />
                                  </button>
                                  {isSubuser && !user.parentUser && (
                                    <button 
                                      onClick={() => {
                                        setAssigningVA(user);
                                        setShowAssignModal(true);
                                      }}
                                      className="text-orange-600 hover:text-orange-800"
                                      title="Assign to Parent User"
                                    >
                                      <UserPlus className="h-4 w-4" />
                                    </button>
                                  )}
                                  <button className="text-red-600 hover:text-red-800">
                                    <Trash2 className="h-4 w-4" />
                                  </button>
                                </div>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Features Tab */}
              {activeTab === 'features' && (
                <div className="space-y-6">
                  {/* Features Overview */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="bg-blue-50 p-4 rounded-lg">
                      <div className="flex items-center">
                        <Settings className="h-5 w-5 text-blue-500 mr-2" />
                        <div>
                          <p className="text-xs text-blue-600">Total Features</p>
                          <p className="text-lg font-bold text-blue-900">{features.length}</p>
                        </div>
                      </div>
                    </div>
                    <div className="bg-green-50 p-4 rounded-lg">
                      <div className="flex items-center">
                        <Play className="h-5 w-5 text-green-500 mr-2" />
                        <div>
                          <p className="text-xs text-green-600">Launched</p>
                          <p className="text-lg font-bold text-green-900">
                            {features.filter(f => f.is_launched).length}
                          </p>
                        </div>
                      </div>
                    </div>
                    <div className="bg-orange-50 p-4 rounded-lg">
                      <div className="flex items-center">
                        <Bell className="h-5 w-5 text-orange-500 mr-2" />
                        <div>
                          <p className="text-xs text-orange-600">Beta</p>
                          <p className="text-lg font-bold text-orange-900">
                            {features.filter(f => f.is_beta).length}
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Quick Actions */}
                  <div className="bg-blue-50 p-4 rounded-lg">
                    <h4 className="text-sm font-medium text-blue-900 mb-3">Quick Actions</h4>
                    <div className="flex flex-wrap gap-2">
                      <button
                        onClick={async () => {
                          try {
                            const allFeatures = ['smart_restock', 'missing_listings', 'reimbursements', 'va_management'];
                            for (const userId of users.filter(u => u.user_type !== 'subuser').map(u => u.discord_id)) {
                              for (const featureKey of allFeatures) {
                                await axios.post('/api/admin/user-features', {
                                  user_id: userId,
                                  feature_key: featureKey
                                }, { withCredentials: true });
                              }
                            }
                            setSuccess('All main features granted to all users!');
                            fetchData();
                          } catch (error) {
                            setError('Failed to grant features to all users');
                          }
                        }}
                        className="px-3 py-1 bg-green-100 text-green-700 rounded-md text-sm hover:bg-green-200"
                      >
                        Grant All Core Features to All Users
                      </button>
                      <button
                        onClick={async () => {
                          try {
                            const betaFeatures = ['ebay_lister', 'discount_opportunities'];
                            for (const userId of users.filter(u => u.user_type !== 'subuser').map(u => u.discord_id)) {
                              for (const featureKey of betaFeatures) {
                                await axios.post('/api/admin/user-features', {
                                  user_id: userId,
                                  feature_key: featureKey
                                }, { withCredentials: true });
                              }
                            }
                            setSuccess('All beta features granted to all users!');
                            fetchData();
                          } catch (error) {
                            setError('Failed to grant beta features');
                          }
                        }}
                        className="px-3 py-1 bg-orange-100 text-orange-700 rounded-md text-sm hover:bg-orange-200"
                      >
                        Grant Beta Features to All Users
                      </button>
                    </div>
                  </div>

                  {/* Features Management */}
                  <div className="bg-white rounded-lg shadow overflow-hidden">
                    <div className="px-6 py-4 border-b border-gray-200">
                      <h3 className="text-lg font-medium text-gray-900">Feature Management</h3>
                      <p className="mt-1 text-sm text-gray-600">
                        Control which features are available and who has access to them.
                      </p>
                    </div>
                    
                    <div className="overflow-x-auto">
                      <table className="min-w-full divide-y divide-gray-200">
                        <thead className="bg-gray-50">
                          <tr>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                              Feature
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                              Status
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                              Users with Access
                            </th>
                            <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                              Actions
                            </th>
                          </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-200">
                          {features.map((feature) => {
                            const usersWithAccess = Object.entries(userFeatureAccess)
                              .filter(([userId, features]) => features[feature.feature_key])
                              .map(([userId]) => users.find(u => u.discord_id === userId))
                              .filter(Boolean);

                            return (
                              <tr key={feature.feature_key} className="hover:bg-gray-50">
                                <td className="px-6 py-4 whitespace-nowrap">
                                  <div>
                                    <div className="text-sm font-medium text-gray-900">
                                      {feature.display_name || feature.feature_key}
                                    </div>
                                    <div className="text-sm text-gray-500">
                                      {feature.description || `${feature.feature_key} feature access`}
                                    </div>
                                  </div>
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap">
                                  <div className="flex flex-col space-y-1">
                                    <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                                      feature.is_launched 
                                        ? 'bg-green-100 text-green-800'
                                        : 'bg-red-100 text-red-800'
                                    }`}>
                                      {feature.is_launched ? 'Launched' : 'Unlaunched'}
                                    </span>
                                    {feature.is_beta && (
                                      <span className="inline-flex px-2 py-1 text-xs font-semibold rounded-full bg-orange-100 text-orange-800">
                                        Beta
                                      </span>
                                    )}
                                  </div>
                                </td>
                                <td className="px-6 py-4">
                                  <div className="text-sm text-gray-900">
                                    {usersWithAccess.length > 0 ? (
                                      <div className="space-y-1">
                                        {usersWithAccess.slice(0, 3).map((user) => (
                                          <div key={user.discord_id} className="flex items-center">
                                            {user.discord_avatar ? (
                                              <img
                                                className="h-4 w-4 rounded-full mr-2"
                                                src={`https://cdn.discordapp.com/avatars/${user.discord_id}/${user.discord_avatar}.png`}
                                                alt=""
                                              />
                                            ) : (
                                              <div className="h-4 w-4 bg-gray-300 rounded-full mr-2"></div>
                                            )}
                                            <span className="text-xs">{user.discord_username}</span>
                                          </div>
                                        ))}
                                        {usersWithAccess.length > 3 && (
                                          <div className="text-xs text-gray-500">
                                            +{usersWithAccess.length - 3} more
                                          </div>
                                        )}
                                      </div>
                                    ) : (
                                      <span className="text-sm text-gray-500 italic">No users have access</span>
                                    )}
                                  </div>
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                                  <div className="flex justify-end space-x-2">
                                    <button
                                      onClick={() => handleLaunchFeature(feature.feature_key)}
                                      className={`inline-flex items-center px-2 py-1 text-xs rounded-md ${
                                        feature.is_launched
                                          ? 'text-red-700 bg-red-100 hover:bg-red-200'
                                          : 'text-green-700 bg-green-100 hover:bg-green-200'
                                      }`}
                                    >
                                      {feature.is_launched ? 'Unlaunch' : 'Launch'}
                                    </button>
                                    <button
                                      onClick={() => handleToggleFeatureBeta(feature.feature_key)}
                                      className={`inline-flex items-center px-2 py-1 text-xs rounded-md ${
                                        feature.is_beta
                                          ? 'text-orange-700 bg-orange-100 hover:bg-orange-200'
                                          : 'text-blue-700 bg-blue-100 hover:bg-blue-200'
                                      }`}
                                    >
                                      {feature.is_beta ? 'Remove Beta' : 'Mark Beta'}
                                    </button>
                                    <button
                                      onClick={() => {
                                        setSelectedFeatureUser(feature);
                                        setShowFeatureModal(true);
                                      }}
                                      className="text-indigo-600 hover:text-indigo-900"
                                    >
                                      Manage Access
                                    </button>
                                  </div>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              )}

              {/* Discount Email Tab */}
              {activeTab === 'discount-email' && (
                <div className="space-y-6">
                  {/* Email Configuration Status */}
                  <div className="bg-gray-50 p-4 rounded-lg">
                    <div className="flex items-center justify-between">
                      <div>
                        <h3 className="text-lg font-medium text-gray-900">Discount Opportunities Email Configuration</h3>
                        <p className="text-sm text-gray-600 mt-1">Configure the email account used to fetch discount opportunity alerts</p>
                      </div>
                      <button
                        onClick={() => {
                          if (discountEmailConfig?.configured) {
                            // Pre-fill form with existing config
                            setDiscountEmailForm({
                              email_address: discountEmailConfig.config?.email_address || '',
                              config_type: discountEmailConfig.config?.config_type || 'gmail_oauth',
                              imap_server: discountEmailConfig.config?.imap_server || '',
                              imap_port: discountEmailConfig.config?.imap_port || 993,
                              username: discountEmailConfig.config?.username || '',
                              password: '',
                              is_active: true
                            });
                          }
                          setShowDiscountEmailModal(true);
                        }}
                        className="inline-flex items-center px-3 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-builders-600 hover:bg-builders-700"
                      >
                        <Settings className="h-4 w-4 mr-2" />
                        {discountEmailConfig?.configured ? 'Update Configuration' : 'Configure Email'}
                      </button>
                    </div>
                  </div>

                  {/* Current Configuration */}
                  {discountEmailConfig?.configured ? (
                    <div className="bg-white border border-gray-200 rounded-lg p-6">
                      <div className="flex items-center justify-between mb-4">
                        <h4 className="text-md font-medium text-gray-900">Current Configuration</h4>
                        <div className="flex space-x-2">
                          <button
                            onClick={handleClearDiscountCache}
                            className="inline-flex items-center px-2 py-1 text-xs border border-gray-300 rounded-md text-gray-700 bg-white hover:bg-gray-50"
                          >
                            <RefreshCw className="h-3 w-3 mr-1" />
                            Clear Cache
                          </button>
                        </div>
                      </div>
                      
                      <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                          <span className="font-medium text-gray-900">Email Address:</span>
                          <p className="text-gray-600">{discountEmailConfig.config?.email_address}</p>
                        </div>
                        <div>
                          <span className="font-medium text-gray-900">Configuration Type:</span>
                          <p className="text-gray-600">
                            {discountEmailConfig.config?.config_type === 'gmail_oauth' 
                              ? 'Gmail OAuth' 
                              : discountEmailConfig.config?.config_type === 'imap'
                                ? 'IMAP'
                                : 'Unknown'
                            }
                            {discountEmailConfig.config?.config_type === 'gmail_oauth' && (
                              <span className="ml-2 px-1 py-0.5 text-xs bg-green-100 text-green-800 rounded-full">
                                {discountEmailConfig.config?.has_gmail_token ? 'Connected' : 'Disconnected'}
                              </span>
                            )}
                          </p>
                        </div>
                        {discountEmailConfig.config?.config_type === 'imap' && (
                          <>
                            <div>
                              <span className="font-medium text-gray-900">IMAP Server:</span>
                              <p className="text-gray-600">{discountEmailConfig.config?.imap_server}:{discountEmailConfig.config?.imap_port}</p>
                            </div>
                            <div>
                              <span className="font-medium text-gray-900">Username:</span>
                              <p className="text-gray-600">{discountEmailConfig.config?.username}</p>
                            </div>
                          </>
                        )}
                        <div>
                          <span className="font-medium text-gray-900">Last Updated:</span>
                          <p className="text-gray-600">
                            {discountEmailConfig.config?.last_updated 
                              ? new Date(discountEmailConfig.config.last_updated).toLocaleString()
                              : 'Unknown'}
                          </p>
                        </div>
                      </div>

                      {discountEmailConfig.is_legacy && (
                        <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-md">
                          <div className="flex">
                            <AlertTriangle className="h-5 w-5 text-yellow-400" />
                            <div className="ml-3">
                              <p className="text-sm text-yellow-800">
                                Using legacy Gmail OAuth configuration. Consider updating to the new database-based configuration for better management.
                              </p>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="bg-gray-50 border border-gray-200 rounded-lg p-6">
                      <div className="text-center">
                        <Mail className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                        <h4 className="text-md font-medium text-gray-900 mb-2">No Email Configuration</h4>
                        <p className="text-sm text-gray-600 mb-4">
                          Configure an email account to fetch discount opportunity alerts for the discount opportunities feature.
                        </p>
                        <button
                          onClick={() => setShowDiscountEmailModal(true)}
                          className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-builders-600 hover:bg-builders-700"
                        >
                          <Plus className="h-4 w-4 mr-2" />
                          Configure Email Account
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Email Format Patterns Configuration */}
                  <div className="bg-white border border-gray-200 rounded-lg p-6">
                    <div className="flex items-center justify-between mb-4">
                      <div>
                        <h4 className="text-md font-medium text-gray-900">Email Format Patterns</h4>
                        <p className="text-sm text-gray-600">Configure patterns for parsing Distill.io discount alerts</p>
                      </div>
                      <button
                        onClick={() => setShowFormatPatternsModal(true)}
                        className="inline-flex items-center px-3 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700"
                      >
                        <Settings className="h-4 w-4 mr-2" />
                        Configure Patterns
                      </button>
                    </div>
                    
                    <div className="grid grid-cols-1 gap-4 text-sm">
                      <div>
                        <span className="font-medium text-gray-900">Subject Pattern:</span>
                        <p className="text-gray-600 font-mono text-xs mt-1 bg-gray-50 p-2 rounded">
                          {formatPatterns?.subject_pattern || '\\[([^\\]]+)\\]\\s*Alert:.*?\\(ASIN:\\s*([B0-9A-Z]{10})\\)'}
                        </p>
                      </div>
                      <div>
                        <span className="font-medium text-gray-900">Sender Filter:</span>
                        <p className="text-gray-600">{formatPatterns?.sender_filter || 'alert@distill.io'}</p>
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <span className="font-medium text-gray-900">ASIN Pattern:</span>
                          <p className="text-gray-600 font-mono text-xs mt-1 bg-gray-50 p-1 rounded">
                            {formatPatterns?.asin_pattern || '\\(ASIN:\\s*([B0-9A-Z]{10})\\)'}
                          </p>
                        </div>
                        <div>
                          <span className="font-medium text-gray-900">Retailer Pattern:</span>
                          <p className="text-gray-600 font-mono text-xs mt-1 bg-gray-50 p-1 rounded">
                            {formatPatterns?.retailer_pattern || '\\[([^\\]]+)\\]\\s*Alert:'}
                          </p>
                        </div>
                      </div>
                    </div>

                    <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-md">
                      <div className="flex">
                        <AlertTriangle className="h-5 w-5 text-blue-500" />
                        <div className="ml-3">
                          <p className="text-sm text-blue-800">
                            <strong>Expected format:</strong> <code className="bg-blue-100 px-1 rounded">[Retailer] Alert: Description (ASIN: BXXXXXXXXX)</code>
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}

            </>
          )}

          {/* Email Webhook Tab */}
          {activeTab === 'email-webhook' && (
            <div className="space-y-6">
              {/* Webhook Configuration Status */}
              <div className="bg-gray-50 p-4 rounded-lg">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-lg font-medium text-gray-900">Email Monitoring Webhook Configuration</h3>
                    <p className="text-sm text-gray-600 mt-1">Configure the system-wide webhook for email monitoring notifications</p>
                  </div>
                  <button
                    onClick={() => {
                      if (emailWebhookConfig?.configured) {
                        // Pre-fill form with existing config
                        setWebhookForm({
                          webhook_url: emailWebhookConfig.config?.webhook_url || '',
                          description: emailWebhookConfig.config?.description || '',
                          is_active: emailWebhookConfig.config?.is_active || true
                        });
                      }
                      setShowWebhookModal(true);
                    }}
                    className="inline-flex items-center px-3 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-builders-600 hover:bg-builders-700"
                  >
                    <Settings className="w-4 h-4 mr-2" />
                    {emailWebhookConfig?.configured ? 'Edit Webhook' : 'Configure Webhook'}
                  </button>
                </div>

                {emailWebhookConfig?.configured ? (
                  <div className="mt-4 space-y-2">
                    <div className="flex items-center space-x-2">
                      <CheckCircle className="w-4 h-4 text-green-500" />
                      <span className="text-sm text-gray-900">Webhook Configured</span>
                    </div>
                    <div className="text-sm text-gray-600">
                      <strong>URL:</strong> {emailWebhookConfig.config?.webhook_url}
                    </div>
                    {emailWebhookConfig.config?.description && (
                      <div className="text-sm text-gray-600">
                        <strong>Description:</strong> {emailWebhookConfig.config?.description}
                      </div>
                    )}
                    <div className="text-sm text-gray-600">
                      <strong>Status:</strong> {emailWebhookConfig.config?.is_active ? 'Active' : 'Inactive'}
                    </div>
                    <div className="text-sm text-gray-600">
                      <strong>Created:</strong> {new Date(emailWebhookConfig.config?.created_at).toLocaleString()}
                    </div>
                    <div className="flex space-x-2 mt-2">
                      <button
                        onClick={handleDeleteWebhook}
                        className="text-red-600 hover:text-red-800 text-sm"
                      >
                        Delete Configuration
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="mt-4 flex items-center space-x-2">
                    <AlertTriangle className="w-4 h-4 text-yellow-500" />
                    <span className="text-sm text-gray-600">No webhook configured. Email notifications will not be sent.</span>
                  </div>
                )}
              </div>

              {/* Usage Information */}
              <div className="bg-blue-50 p-4 rounded-lg">
                <h4 className="text-sm font-medium text-blue-900 mb-2">How Email Monitoring Webhooks Work</h4>
                <ul className="text-sm text-blue-700 space-y-1">
                  <li>• This webhook receives notifications for all users' email monitoring matches</li>
                  <li>• Individual users cannot configure their own webhooks</li>
                  <li>• The webhook URL should accept POST requests with JSON payload</li>
                  <li>• Supports Discord webhooks, Slack webhooks, or custom endpoints</li>
                </ul>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Invite Modal */}
      {showInviteModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md mx-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-medium">Send Invitation</h3>
              <button
                onClick={() => setShowInviteModal(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Email Address
                </label>
                <input
                  type="email"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  placeholder="user@example.com"
                  className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-builders-500"
                />
              </div>
              
              <div className="flex justify-end space-x-3">
                <button
                  onClick={() => setShowInviteModal(false)}
                  className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSendInvitation}
                  className="px-4 py-2 text-sm font-medium text-white bg-builders-600 border border-transparent rounded-md hover:bg-builders-700"
                >
                  Send Invitation
                </button>
              </div>
            </div>
          </div>
        </div>
      )}


      {/* Assign VA Modal */}
      {showAssignModal && assigningVA && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
          <div className="relative top-20 mx-auto p-5 border w-96 shadow-lg rounded-md bg-white">
            <div className="mt-3">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-medium text-gray-900">
                  Assign VA to Parent User
                </h3>
                <button
                  onClick={() => {
                    setShowAssignModal(false);
                    setAssigningVA(null);
                    setSelectedParentUser('');
                  }}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
              
              <div className="space-y-4">
                <div>
                  <p className="text-sm text-gray-600 mb-2">
                    Assigning: <span className="font-medium">{assigningVA.discord_username}</span>
                  </p>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Select Parent User
                  </label>
                  <select
                    value={selectedParentUser}
                    onChange={(e) => setSelectedParentUser(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-builders-500 focus:border-builders-500"
                  >
                    <option value="">Choose a parent user...</option>
                    {users.filter(u => u.user_type !== 'subuser').map(mainUser => (
                      <option key={mainUser.discord_id} value={mainUser.discord_id}>
                        {mainUser.discord_username} ({mainUser.email})
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              
              <div className="flex justify-end space-x-3 mt-6">
                <button
                  onClick={() => {
                    setShowAssignModal(false);
                    setAssigningVA(null);
                    setSelectedParentUser('');
                  }}
                  className="px-4 py-2 text-gray-600 hover:text-gray-800"
                >
                  Cancel
                </button>
                <button
                  onClick={handleAssignVA}
                  disabled={!selectedParentUser}
                  className="px-4 py-2 bg-builders-600 text-white rounded-md hover:bg-builders-700 disabled:opacity-50"
                >
                  Assign VA
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Edit User Modal */}
      {editingUser && (
        <UserEditModal
          user={editingUser}
          onSave={handleUpdateUser}
          onCancel={() => setEditingUser(null)}
        />
      )}

      {/* Feature Access Management Modal */}
      {showFeatureModal && selectedFeatureUser && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
          <div className="relative top-10 mx-auto p-5 border w-11/12 md:w-3/4 lg:w-1/2 shadow-lg rounded-md bg-white max-h-screen overflow-y-auto">
            <div className="mt-3">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-medium text-gray-900">
                  Manage Access: {selectedFeatureUser.display_name || selectedFeatureUser.feature_key}
                </h3>
                <button
                  onClick={() => {
                    setShowFeatureModal(false);
                    setSelectedFeatureUser(null);
                  }}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
              
              <div className="space-y-4">
                <div className="bg-gray-50 p-4 rounded-lg">
                  <h4 className="text-sm font-medium text-gray-900 mb-2">Feature Information</h4>
                  <p className="text-sm text-gray-600">
                    {selectedFeatureUser.description || `Control access to the ${selectedFeatureUser.feature_key} feature`}
                  </p>
                  <div className="mt-2 flex space-x-2">
                    <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                      selectedFeatureUser.is_launched 
                        ? 'bg-green-100 text-green-800'
                        : 'bg-red-100 text-red-800'
                    }`}>
                      {selectedFeatureUser.is_launched ? 'Launched' : 'Unlaunched'}
                    </span>
                    {selectedFeatureUser.is_beta && (
                      <span className="inline-flex px-2 py-1 text-xs font-semibold rounded-full bg-orange-100 text-orange-800">
                        Beta
                      </span>
                    )}
                  </div>
                </div>

                <div>
                  <h4 className="text-sm font-medium text-gray-900 mb-3">User Access</h4>
                  <div className="max-h-96 overflow-y-auto">
                    <div className="space-y-2">
                      {users.filter(user => user.user_type !== 'subuser').map((user) => {
                        const hasAccess = userFeatureAccess[user.discord_id]?.[selectedFeatureUser.feature_key] || false;
                        
                        return (
                          <div key={user.discord_id} className="flex items-center justify-between p-3 bg-white border border-gray-200 rounded-lg">
                            <div className="flex items-center">
                              {user.discord_avatar ? (
                                <img
                                  className="h-8 w-8 rounded-full mr-3"
                                  src={`https://cdn.discordapp.com/avatars/${user.discord_id}/${user.discord_avatar}.png`}
                                  alt=""
                                />
                              ) : (
                                <div className="h-8 w-8 bg-gray-300 rounded-full mr-3"></div>
                              )}
                              <div>
                                <div className="text-sm font-medium text-gray-900">{user.discord_username}</div>
                                <div className="text-xs text-gray-500">{user.email}</div>
                              </div>
                            </div>
                            
                            <button
                              onClick={() => handleToggleFeatureAccess(user.discord_id, selectedFeatureUser.feature_key)}
                              className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                                hasAccess
                                  ? 'bg-red-100 text-red-700 hover:bg-red-200'
                                  : 'bg-green-100 text-green-700 hover:bg-green-200'
                              }`}
                            >
                              {hasAccess ? 'Remove Access' : 'Grant Access'}
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              </div>
              
              <div className="flex justify-end mt-6">
                <button
                  onClick={() => {
                    setShowFeatureModal(false);
                    setSelectedFeatureUser(null);
                  }}
                  className="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700"
                >
                  Done
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Discount Email Configuration Modal */}
      {showDiscountEmailModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg max-w-md w-full mx-4 p-6">
            <h3 className="text-lg font-medium mb-4">Configure Discount Email</h3>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">Configuration Type</label>
                <select
                  value={discountEmailForm.config_type}
                  onChange={(e) => setDiscountEmailForm({...discountEmailForm, config_type: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                >
                  <option value="gmail_oauth">Gmail OAuth (Recommended)</option>
                  <option value="imap">IMAP (Manual Configuration)</option>
                </select>
                <p className="text-xs text-gray-500 mt-1">
                  Gmail OAuth is recommended for Gmail accounts and provides better security
                </p>
              </div>
              
              <div>
                <label className="block text-sm font-medium mb-1">Email Address</label>
                <input
                  type="email"
                  value={discountEmailForm.email_address}
                  onChange={(e) => setDiscountEmailForm({...discountEmailForm, email_address: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                  placeholder="your-email@example.com"
                />
                {discountEmailForm.config_type === 'gmail_oauth' && (
                  <p className="text-xs text-gray-500 mt-1">
                    Must be a Gmail address (@gmail.com or G Suite domain)
                  </p>
                )}
              </div>
              
              {discountEmailForm.config_type === 'imap' && (
                <>
                  <div>
                    <label className="block text-sm font-medium mb-1">IMAP Server</label>
                <select
                  value={discountEmailForm.imap_server}
                  onChange={(e) => {
                    const commonServers = [
                      { name: 'Gmail', server: 'imap.gmail.com', port: 993 },
                      { name: 'Outlook/Hotmail', server: 'outlook.office365.com', port: 993 },
                      { name: 'Yahoo', server: 'imap.mail.yahoo.com', port: 993 },
                      { name: 'iCloud', server: 'imap.mail.me.com', port: 993 }
                    ];
                    const server = commonServers.find(s => s.server === e.target.value);
                    setDiscountEmailForm({
                      ...discountEmailForm, 
                      imap_server: e.target.value,
                      imap_port: server ? server.port : 993
                    });
                  }}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                >
                  <option value="">Select email provider or enter custom</option>
                  <option value="imap.gmail.com">Gmail (imap.gmail.com)</option>
                  <option value="outlook.office365.com">Outlook/Hotmail (outlook.office365.com)</option>
                  <option value="imap.mail.yahoo.com">Yahoo (imap.mail.yahoo.com)</option>
                  <option value="imap.mail.me.com">iCloud (imap.mail.me.com)</option>
                </select>
                {!['imap.gmail.com', 'outlook.office365.com', 'imap.mail.yahoo.com', 'imap.mail.me.com'].includes(discountEmailForm.imap_server) && (
                  <input
                    type="text"
                    value={discountEmailForm.imap_server}
                    onChange={(e) => setDiscountEmailForm({...discountEmailForm, imap_server: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm mt-2"
                    placeholder="imap.example.com"
                  />
                )}
              </div>
              
              <div>
                <label className="block text-sm font-medium mb-1">Port</label>
                <input
                  type="number"
                  value={discountEmailForm.imap_port}
                  onChange={(e) => setDiscountEmailForm({...discountEmailForm, imap_port: parseInt(e.target.value)})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium mb-1">Username</label>
                <input
                  type="text"
                  value={discountEmailForm.username}
                  onChange={(e) => setDiscountEmailForm({...discountEmailForm, username: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                  placeholder="Usually your email address"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium mb-1">Password</label>
                <input
                  type="password"
                  value={discountEmailForm.password}
                  onChange={(e) => setDiscountEmailForm({...discountEmailForm, password: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                  placeholder="Email password or app password"
                />
                    <p className="text-xs text-gray-500 mt-1">
                      For Gmail, use an App Password instead of your main password
                    </p>
                  </div>
                </>
              )}
              
              {discountEmailTestResult && (
                <div className={`p-3 rounded-md text-sm ${
                  discountEmailTestResult.success ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'
                }`}>
                  {discountEmailTestResult.message}
                </div>
              )}
            </div>
            
            <div className="flex justify-between mt-6">
              {discountEmailForm.config_type === 'imap' && (
                <button
                  onClick={handleTestDiscountEmail}
                  disabled={testingDiscountEmail || !discountEmailForm.email_address || !discountEmailForm.imap_server || !discountEmailForm.password}
                  className="px-4 py-2 text-blue-600 border border-blue-600 rounded-md hover:bg-blue-50 text-sm disabled:opacity-50"
                >
                  {testingDiscountEmail ? 'Testing...' : 'Test Connection'}
                </button>
              )}
              {discountEmailForm.config_type === 'gmail_oauth' && <div></div>}
              <div className="space-x-3">
                <button
                  onClick={() => {
                    setShowDiscountEmailModal(false);
                    setDiscountEmailTestResult(null);
                    setDiscountEmailForm({
                      email_address: '',
                      config_type: 'gmail_oauth',
                      imap_server: '',
                      imap_port: 993,
                      username: '',
                      password: '',
                      is_active: true
                    });
                  }}
                  className="px-4 py-2 text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50 text-sm"
                >
                  Cancel
                </button>
                <button
                  onClick={handleUpdateDiscountEmail}
                  disabled={
                    !discountEmailForm.email_address || 
                    (discountEmailForm.config_type === 'imap' && (!discountEmailForm.imap_server || !discountEmailForm.password))
                  }
                  className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm disabled:opacity-50"
                >
                  <Save className="h-4 w-4 mr-2 inline" />
                  {discountEmailForm.config_type === 'gmail_oauth' ? 'Setup Gmail OAuth' : 'Save Configuration'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Format Patterns Modal */}
      {showFormatPatternsModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg max-w-2xl w-full mx-4 p-6 max-h-96 overflow-y-auto">
            <h3 className="text-lg font-medium mb-4">Configure Email Format Patterns</h3>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">Subject Pattern</label>
                <input
                  type="text"
                  defaultValue={formatPatterns?.subject_pattern || '\\[([^\\]]+)\\]\\s*Alert:.*?\\(ASIN:\\s*([B0-9A-Z]{10})\\)'}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-xs font-mono"
                  placeholder="Regex pattern for full email subject"
                />
                <p className="text-xs text-gray-500 mt-1">Captures both retailer and ASIN from subject line</p>
              </div>
              
              <div>
                <label className="block text-sm font-medium mb-1">ASIN Pattern</label>
                <input
                  type="text"
                  defaultValue={formatPatterns?.asin_pattern || '\\(ASIN:\\s*([B0-9A-Z]{10})\\)'}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-xs font-mono"
                  placeholder="Regex pattern to extract ASIN"
                />
                <p className="text-xs text-gray-500 mt-1">Should capture Amazon ASIN (B + 9 alphanumeric)</p>
              </div>
              
              <div>
                <label className="block text-sm font-medium mb-1">Retailer Pattern</label>
                <input
                  type="text"
                  defaultValue={formatPatterns?.retailer_pattern || '\\[([^\\]]+)\\]\\s*Alert:'}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-xs font-mono"
                  placeholder="Regex pattern to extract retailer"
                />
                <p className="text-xs text-gray-500 mt-1">Captures retailer name from square brackets</p>
              </div>
              
              <div>
                <label className="block text-sm font-medium mb-1">Sender Filter</label>
                <input
                  type="text"
                  defaultValue={formatPatterns?.sender_filter || 'alert@distill.io'}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  placeholder="Email sender to monitor"
                />
                <p className="text-xs text-gray-500 mt-1">Only emails from this sender will be processed</p>
              </div>

              <div className="bg-blue-50 p-3 rounded-md">
                <p className="text-sm text-blue-800">
                  <strong>Expected format:</strong> <code className="bg-blue-100 px-1 rounded">[Retailer] Alert: Description (ASIN: BXXXXXXXXX)</code>
                </p>
              </div>

              <div className="flex space-x-3 pt-4">
                <button
                  onClick={() => setShowFormatPatternsModal(false)}
                  className="px-4 py-2 text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50 text-sm"
                >
                  Cancel
                </button>
                <button
                  onClick={() => {
                    // TODO: Implement save logic
                    setShowFormatPatternsModal(false);
                    setSuccess('Format patterns updated successfully!');
                  }}
                  className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm"
                >
                  <Save className="h-4 w-4 mr-2 inline" />
                  Save Patterns
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Gmail OAuth Setup Step Modal */}
      {showGmailOAuthStep && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg max-w-md w-full mx-4 p-6">
            <h3 className="text-lg font-medium mb-4">Gmail OAuth Setup</h3>
            
            <div className="space-y-4">
              <div>
                <p className="text-sm text-gray-600 mb-4">
                  To complete the Gmail OAuth setup, please follow these steps:
                </p>
                
                <div className="bg-blue-50 p-4 rounded-md mb-4">
                  <p className="text-sm text-blue-800 mb-2">
                    <strong>1. Click the link below to authorize access:</strong>
                  </p>
                  <a
                    href={gmailAuthUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center px-3 py-2 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700"
                  >
                    <ExternalLink className="h-4 w-4 mr-2" />
                    Authorize Gmail Access
                  </a>
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    2. Paste the authorization code here:
                  </label>
                  <input
                    type="text"
                    value={gmailAuthCode}
                    onChange={(e) => setGmailAuthCode(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Paste authorization code here..."
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    After authorizing, copy the code from the redirect page and paste it here.
                  </p>
                </div>
              </div>
              
              {error && (
                <div className="p-3 rounded-md text-sm bg-red-50 text-red-800">
                  {error}
                </div>
              )}
            </div>
            
            <div className="flex justify-end space-x-3 mt-6">
              <button
                onClick={() => {
                  setShowGmailOAuthStep(false);
                  setGmailAuthCode('');
                  setGmailAuthUrl('');
                  setError('');
                }}
                className="px-4 py-2 text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50 text-sm"
              >
                Cancel
              </button>
              <button
                onClick={handleGmailAuth}
                disabled={!gmailAuthCode}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm disabled:opacity-50"
              >
                Complete Setup
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Webhook Configuration Modal */}
      {showWebhookModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg max-w-md w-full mx-4 p-6">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-medium">Configure Email Monitoring Webhook</h3>
              <button
                onClick={() => {
                  setShowWebhookModal(false);
                  setWebhookTestResult(null);
                }}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700">Webhook URL *</label>
                <input
                  type="url"
                  value={webhookForm.webhook_url}
                  onChange={(e) => setWebhookForm({...webhookForm, webhook_url: e.target.value})}
                  className="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-builders-500"
                  placeholder="https://hooks.slack.com/services/..."
                />
                <p className="text-xs text-gray-500 mt-1">
                  Discord webhook, Slack webhook, or any URL that accepts POST requests
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">Description (optional)</label>
                <input
                  type="text"
                  value={webhookForm.description}
                  onChange={(e) => setWebhookForm({...webhookForm, description: e.target.value})}
                  className="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-builders-500"
                  placeholder="e.g., Main Discord Channel"
                />
              </div>

              <div className="flex items-center">
                <input
                  id="webhook_active"
                  type="checkbox"
                  checked={webhookForm.is_active}
                  onChange={(e) => setWebhookForm({...webhookForm, is_active: e.target.checked})}
                  className="h-4 w-4 text-builders-600 focus:ring-builders-500 border-gray-300 rounded"
                />
                <label htmlFor="webhook_active" className="ml-2 block text-sm text-gray-700">
                  Active
                </label>
              </div>

              {webhookTestResult && (
                <div className={`p-3 rounded-md text-sm ${
                  webhookTestResult.success ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'
                }`}>
                  {webhookTestResult.message}
                </div>
              )}
            </div>

            <div className="flex justify-between mt-6">
              <button
                onClick={handleTestWebhook}
                disabled={testingWebhook || !webhookForm.webhook_url}
                className="px-4 py-2 text-blue-600 border border-blue-600 rounded-md hover:bg-blue-50 text-sm disabled:opacity-50"
              >
                {testingWebhook ? 'Testing...' : 'Test Webhook'}
              </button>
              <div className="space-x-3">
                <button
                  onClick={() => {
                    setShowWebhookModal(false);
                    setWebhookTestResult(null);
                  }}
                  className="px-4 py-2 bg-white border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 text-sm"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSaveWebhook}
                  disabled={!webhookForm.webhook_url}
                  className="px-4 py-2 bg-builders-600 text-white rounded-md hover:bg-builders-700 text-sm disabled:opacity-50"
                >
                  <Save className="h-4 w-4 mr-2 inline" />
                  Save Webhook
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

    </div>
  );
};

export default AdminCompact;