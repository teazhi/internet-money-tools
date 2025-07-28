import React, { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { 
  Users, 
  Edit3, 
  Trash2, 
  Plus, 
  Search, 
  Filter, 
  Download, 
  Upload,
  AlertTriangle,
  CheckCircle,
  Clock,
  Database,
  Activity,
  Shield,
  Eye,
  EyeOff,
  Save,
  X,
  RefreshCw,
  UserPlus,
  Settings,
  BarChart3,
  ExternalLink,
  Play,
  Calendar,
  Cog
} from 'lucide-react';
import axios from 'axios';

const InviteModal = ({ inviteEmail, setInviteEmail, onSave, onCancel }) => {
  return (
    <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
      <div className="relative top-20 mx-auto p-5 border w-11/12 md:w-1/2 lg:w-1/3 shadow-lg rounded-md bg-white">
        <div className="mt-3">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-medium text-gray-900">
              Send Invitation
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
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Email Address
              </label>
              <input
                type="email"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                placeholder="user@example.com"
                className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-builders-500"
                autoFocus
              />
            </div>
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
              <p className="text-sm text-blue-700">
                The user will receive an email with a link to join the platform. 
                The invitation link will expire in 7 days.
              </p>
            </div>
          </div>

          <div className="flex justify-end space-x-3 mt-6">
            <button
              onClick={onCancel}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              onClick={onSave}
              className="px-4 py-2 text-sm font-medium text-white bg-builders-600 border border-transparent rounded-md hover:bg-builders-700"
            >
              Send Invitation
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

const ScriptConfigModal = ({ configs, onSave, onCancel, onTrigger, loading }) => {
  const [editData, setEditData] = useState({
    amznUploadConfig: {
      last_processed_date: configs?.amznUploadConfig?.last_processed_date || ''
    },
    config: {
      last_processed_date: configs?.config?.last_processed_date || ''
    }
  });

  const formatDateForInput = (dateString) => {
    if (!dateString) return '';
    // Convert ISO string to local datetime input format
    const date = new Date(dateString);
    return date.toISOString().slice(0, 16);
  };

  const formatDateForAPI = (dateString) => {
    if (!dateString) return '';
    // Convert local datetime input to ISO string
    return new Date(dateString).toISOString();
  };

  useEffect(() => {
    if (configs) {
      setEditData({
        amznUploadConfig: {
          last_processed_date: formatDateForInput(configs.amznUploadConfig?.last_processed_date)
        },
        config: {
          last_processed_date: formatDateForInput(configs.config?.last_processed_date)
        }
      });
    }
  }, [configs]);

  const handleSave = () => {
    const saveData = {
      amznUploadConfig: {
        last_processed_date: formatDateForAPI(editData.amznUploadConfig.last_processed_date)
      },
      config: {
        last_processed_date: formatDateForAPI(editData.config.last_processed_date)
      }
    };
    onSave(saveData);
  };

  return (
    <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
      <div className="relative top-10 mx-auto p-5 border w-11/12 md:w-3/4 lg:w-1/2 shadow-lg rounded-md bg-white">
        <div className="mt-3">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-medium text-gray-900">
              Manual Script Control
            </h3>
            <button
              onClick={onCancel}
              className="text-gray-400 hover:text-gray-600"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          <div className="space-y-6">
            {/* Listing Loader & Sellerboard Script */}
            <div className="border border-gray-200 rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h4 className="text-md font-medium text-gray-900">Listing Loader & Sellerboard Script</h4>
                  <p className="text-sm text-gray-500">Controls amznUploadConfig file</p>
                </div>
                <button
                  onClick={() => onTrigger('listing_loader')}
                  disabled={loading}
                  className="flex items-center px-3 py-2 text-sm font-medium text-white bg-green-600 border border-transparent rounded-md hover:bg-green-700 disabled:opacity-50"
                >
                  <Play className="h-4 w-4 mr-2" />
                  {loading ? 'Processing...' : 'Trigger Now'}
                </button>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Last Processed Date
                </label>
                <input
                  type="datetime-local"
                  value={editData.amznUploadConfig.last_processed_date}
                  onChange={(e) => setEditData({
                    ...editData,
                    amznUploadConfig: {
                      ...editData.amznUploadConfig,
                      last_processed_date: e.target.value
                    }
                  })}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-builders-500"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Current: {configs?.amznUploadConfig?.last_processed_date ? 
                    new Date(configs.amznUploadConfig.last_processed_date).toLocaleString() : 
                    'Not set'}
                </p>
              </div>
            </div>

            {/* Prep Uploader Script */}
            <div className="border border-gray-200 rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h4 className="text-md font-medium text-gray-900">Prep Uploader Script</h4>
                  <p className="text-sm text-gray-500">Controls config.json file</p>
                </div>
                <button
                  onClick={() => onTrigger('prep_uploader')}
                  disabled={loading}
                  className="flex items-center px-3 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700 disabled:opacity-50"
                >
                  <Play className="h-4 w-4 mr-2" />
                  {loading ? 'Processing...' : 'Trigger Now'}
                </button>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Last Processed Date
                </label>
                <input
                  type="datetime-local"
                  value={editData.config.last_processed_date}
                  onChange={(e) => setEditData({
                    ...editData,
                    config: {
                      ...editData.config,
                      last_processed_date: e.target.value
                    }
                  })}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-builders-500"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Current: {configs?.config?.last_processed_date ? 
                    new Date(configs.config.last_processed_date).toLocaleString() : 
                    'Not set'}
                </p>
              </div>
            </div>

            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
              <div className="flex">
                <AlertTriangle className="h-5 w-5 text-yellow-400 flex-shrink-0" />
                <div className="ml-3">
                  <p className="text-sm text-yellow-700">
                    <strong>Warning:</strong> Manually triggering scripts or changing dates will affect automated processing. 
                    Setting dates to the past will cause scripts to reprocess old data.
                  </p>
                </div>
              </div>
            </div>
          </div>

          <div className="flex justify-end space-x-3 mt-6">
            <button
              onClick={onCancel}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={loading}
              className="px-4 py-2 text-sm font-medium text-white bg-builders-600 border border-transparent rounded-md hover:bg-builders-700 disabled:opacity-50"
            >
              {loading ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

const Admin = () => {
  const { user } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState('all');
  const [editingUser, setEditingUser] = useState(null);
  const [showRawData, setShowRawData] = useState(false);
  const [rawUserData, setRawUserData] = useState('');
  const [systemStats, setSystemStats] = useState(null);
  const [invitations, setInvitations] = useState([]);
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [scriptConfigs, setScriptConfigs] = useState({
    amznUploadConfig: null,
    config: null
  });
  const [scriptLoading, setScriptLoading] = useState(false);
  const [showScriptModal, setShowScriptModal] = useState(false);

  const getRelativeTime = (dateString) => {
    if (!dateString) return 'Never';
    
    const now = new Date();
    // Ensure we're parsing UTC time correctly
    const date = new Date(dateString.endsWith('Z') ? dateString : dateString + 'Z');
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / (1000 * 60));
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    
    return date.toLocaleDateString();
  };

  const getExpirationTime = (dateString) => {
    if (!dateString) return 'Never';
    
    const now = new Date();
    // Ensure we're parsing UTC time correctly
    const date = new Date(dateString.endsWith('Z') ? dateString : dateString + 'Z');
    const diffMs = date - now;
    const diffMins = Math.floor(diffMs / (1000 * 60));
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    
    if (diffMs < 0) return 'Expired';
    if (diffMins < 1) return 'Soon';
    if (diffMins < 60) return `${diffMins}m`;
    if (diffHours < 24) return `${diffHours}h`;
    if (diffDays < 7) return `${diffDays}d`;
    
    return date.toLocaleDateString();
  };
  
  // Check if current user is admin
  const isAdmin = user?.discord_id === '1278565917206249503';

  useEffect(() => {
    if (isAdmin) {
      fetchUsers();
      fetchSystemStats();
      fetchInvitations();
      fetchScriptConfigs();
    }
  }, [isAdmin]);

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

  const fetchUsers = async () => {
    try {
      setError('');
      // Add cache-busting timestamp to ensure fresh data
      const timestamp = Date.now();
      const response = await axios.get(`/api/admin/users?_t=${timestamp}`, { 
        withCredentials: true,
        headers: {
          'Cache-Control': 'no-cache',
          'Pragma': 'no-cache'
        }
      });
      console.log('[FETCH USERS] Received fresh user data:', response.data.users);
      setUsers(response.data.users);
      setRawUserData(JSON.stringify(response.data.users, null, 2));
    } catch (error) {
      console.error('[FETCH USERS] Error:', error);
      setError(error.response?.data?.error || 'Failed to fetch users');
    } finally {
      setLoading(false);
    }
  };

  const fetchSystemStats = async () => {
    try {
      const response = await axios.get('/api/admin/stats', { withCredentials: true });
      setSystemStats(response.data);
    } catch (error) {
      console.error('Failed to fetch system stats:', error);
    }
  };

  const fetchInvitations = async () => {
    try {
      const response = await axios.get('/api/admin/invitations', { withCredentials: true });
      setInvitations(response.data.invitations);
    } catch (error) {
      console.error('Failed to fetch invitations:', error);
    }
  };

  const fetchScriptConfigs = async () => {
    try {
      setScriptLoading(true);
      const response = await axios.get('/api/admin/script-configs', { withCredentials: true });
      setScriptConfigs(response.data);
    } catch (error) {
      console.error('Failed to fetch script configs:', error);
      setError('Failed to fetch script configurations');
    } finally {
      setScriptLoading(false);
    }
  };

  const handleSendInvitation = async () => {
    if (!inviteEmail) {
      setError('Please enter an email address');
      return;
    }

    try {
      setError('');
      setSuccess('');
      await axios.post('/api/admin/invitations', { email: inviteEmail }, { withCredentials: true });
      setSuccess('Invitation sent successfully!');
      setInviteEmail('');
      setShowInviteModal(false);
      fetchInvitations();
    } catch (error) {
      setError(error.response?.data?.error || 'Failed to send invitation');
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
      fetchInvitations();
    } catch (error) {
      setError(error.response?.data?.error || 'Failed to delete invitation');
    }
  };

  const handleUpdateScriptConfigs = async (configData) => {
    try {
      setError('');
      setSuccess('');
      setScriptLoading(true);
      
      await axios.post('/api/admin/script-configs', configData, { withCredentials: true });
      setSuccess('Script configurations updated successfully');
      await fetchScriptConfigs();
    } catch (error) {
      setError(error.response?.data?.error || 'Failed to update script configurations');
    } finally {
      setScriptLoading(false);
    }
  };

  const handleTriggerScript = async (scriptType) => {
    if (!window.confirm(`Are you sure you want to manually trigger the ${scriptType} script?`)) {
      return;
    }

    try {
      setError('');
      setSuccess('');
      setScriptLoading(true);
      
      await axios.post('/api/admin/trigger-script', { script_type: scriptType }, { withCredentials: true });
      setSuccess(`${scriptType} script triggered successfully`);
      await fetchScriptConfigs();
    } catch (error) {
      setError(error.response?.data?.error || `Failed to trigger ${scriptType} script`);
    } finally {
      setScriptLoading(false);
    }
  };

  const handleUpdateUser = async (userId, userData) => {
    try {
      setError('');
      setSuccess('');
      
      console.log('[ADMIN UPDATE] Updating user:', userId);
      console.log('[ADMIN UPDATE] User data:', userData);
      console.log('[ADMIN UPDATE] Source Links:', userData.enable_source_links);
      console.log('[ADMIN UPDATE] Search All Worksheets:', userData.search_all_worksheets);
      
      const response = await axios.put(`/api/admin/users/${userId}`, userData, { withCredentials: true });
      console.log('[ADMIN UPDATE] Response:', response.data);
      
      setSuccess('User updated successfully');
      setEditingUser(null);
      
      // Small delay to ensure backend has persisted the changes
      console.log('[ADMIN UPDATE] Waiting for backend to persist changes...');
      await new Promise(resolve => setTimeout(resolve, 200));
      
      console.log('[ADMIN UPDATE] Refreshing user list...');
      try {
        await fetchUsers();
        console.log('[ADMIN UPDATE] User list refreshed successfully');
      } catch (fetchError) {
        console.error('[ADMIN UPDATE] fetchUsers failed:', fetchError);
        // Manual state update as fallback
        setUsers(prevUsers => 
          prevUsers.map(u => 
            u.discord_id === userId 
              ? { ...u, ...userData }
              : u
          )
        );
        console.log('[ADMIN UPDATE] Used manual state update as fallback');
      }
    } catch (error) {
      console.error('[ADMIN UPDATE] Error:', error);
      console.error('[ADMIN UPDATE] Error response:', error.response?.data);
      setError(error.response?.data?.error || 'Failed to update user');
    }
  };

  const handleDeleteUser = async (userId) => {
    if (!window.confirm('Are you sure you want to delete this user? This action cannot be undone.')) {
      return;
    }

    try {
      setError('');
      setSuccess('');
      await axios.delete(`/api/admin/users/${userId}`, { withCredentials: true });
      setSuccess('User deleted successfully');
      fetchUsers();
    } catch (error) {
      setError(error.response?.data?.error || 'Failed to delete user');
    }
  };

  const handleViewUserDashboard = async (userId) => {
    try {
      setError('');
      
      // Start impersonation and then navigate to Overview
      const response = await axios.post(`/api/admin/impersonate/${userId}`, {}, { 
        withCredentials: true 
      });
      
      // Navigate to dashboard overview - impersonation will show in banner
      window.location.href = '/dashboard/overview';
      
    } catch (error) {
      console.error('Failed to start impersonation:', error);
      setError(`Failed to start impersonation: ${error.response?.data?.error || error.message}`);
    }
  };

  const handleBulkUpdate = async () => {
    try {
      setError('');
      setSuccess('');
      const parsedData = JSON.parse(rawUserData);
      await axios.put('/api/admin/users/bulk', { users: parsedData }, { withCredentials: true });
      setSuccess('Bulk update completed successfully');
      fetchUsers();
    } catch (error) {
      if (error instanceof SyntaxError) {
        setError('Invalid JSON format');
      } else {
        setError(error.response?.data?.error || 'Failed to bulk update users');
      }
    }
  };

  const exportUserData = () => {
    const dataStr = JSON.stringify(users, null, 2);
    const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);
    const exportFileDefaultName = `users-export-${new Date().toISOString().split('T')[0]}.json`;
    
    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', dataUri);
    linkElement.setAttribute('download', exportFileDefaultName);
    linkElement.click();
  };

  const getStatusBadge = (user) => {
    if (!user.profile_configured) {
      return <span className="px-2 py-1 text-xs font-medium bg-red-100 text-red-800 rounded-full">Setup Required</span>;
    }
    if (!user.google_linked) {
      return <span className="px-2 py-1 text-xs font-medium bg-yellow-100 text-yellow-800 rounded-full">Google Pending</span>;
    }
    if (!user.sheet_configured) {
      return <span className="px-2 py-1 text-xs font-medium bg-blue-100 text-blue-800 rounded-full">Sheet Pending</span>;
    }
    return <span className="px-2 py-1 text-xs font-medium bg-green-100 text-green-800 rounded-full">Active</span>;
  };

  const getFilteredUsers = () => {
    let filtered = users.filter(user => {
      const matchesSearch = 
        user.discord_username?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        user.email?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        user.discord_id?.toString().includes(searchTerm);

      if (filterStatus === 'all') return matchesSearch;
      
      const isActive = user.profile_configured && user.google_linked && user.sheet_configured;
      const isPending = !user.profile_configured || !user.google_linked || !user.sheet_configured;
      
      if (filterStatus === 'active') return matchesSearch && isActive;
      if (filterStatus === 'pending') return matchesSearch && isPending;
      
      return matchesSearch;
    });

    return filtered;
  };


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
      sellerboard_stock_url: user.sellerboard_stock_url || ''
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
                <label className="block text-sm font-medium text-gray-700">Listing Loader Key</label>
                <input
                  type="text"
                  value={editData.listing_loader_key}
                  onChange={(e) => setEditData({...editData, listing_loader_key: e.target.value})}
                  className="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-builders-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">Sellerboard File Key</label>
                <input
                  type="text"
                  value={editData.sb_file_key}
                  onChange={(e) => setEditData({...editData, sb_file_key: e.target.value})}
                  className="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-builders-500"
                />
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
                  id="run_prep_center"
                  type="checkbox"
                  checked={editData.run_prep_center}
                  onChange={(e) => setEditData({...editData, run_prep_center: e.target.checked})}
                  className="h-4 w-4 text-builders-600 focus:ring-builders-500 border-gray-300 rounded"
                />
                <label htmlFor="run_prep_center" className="ml-2 block text-sm text-gray-700">
                  Prep center sheet automation
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
                <div>
                  <label htmlFor="enable_source_links" className="ml-2 block text-sm text-gray-700">
                    Source Links from Google Sheet
                  </label>
                  <p className="ml-6 text-xs text-gray-500">Enable COGS and restock buttons from user's Google Sheet data</p>
                </div>
              </div>

              <div className="flex items-center">
                <input
                  id="search_all_worksheets"
                  type="checkbox"
                  checked={editData.search_all_worksheets}
                  onChange={(e) => setEditData({...editData, search_all_worksheets: e.target.checked})}
                  className="h-4 w-4 text-builders-600 focus:ring-builders-500 border-gray-300 rounded"
                />
                <div>
                  <label htmlFor="search_all_worksheets" className="ml-2 block text-sm text-gray-700">
                    Search All Worksheets
                  </label>
                  <p className="ml-6 text-xs text-gray-500">Search all worksheets instead of just the mapped one</p>
                </div>
              </div>
            </div>

            <div className="flex justify-end space-x-3 mt-6">
              <button
                onClick={onCancel}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={async () => {
                  console.log('[MODAL] Save button clicked');
                  console.log('[MODAL] User ID:', user.discord_id);
                  console.log('[MODAL] Edit data:', editData);
                  try {
                    await onSave(user.discord_id, editData);
                    console.log('[MODAL] Save completed successfully');
                  } catch (error) {
                    console.error('[MODAL] Save failed:', error);
                  }
                }}
                className="px-4 py-2 text-sm font-medium text-white bg-builders-600 border border-transparent rounded-md hover:bg-builders-700"
              >
                Save Changes
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-builders-500"></div>
      </div>
    );
  }

  const filteredUsers = getFilteredUsers();

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-builders-500 to-builders-600 rounded-lg shadow-sm p-6 text-white">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold mb-2">Admin Panel</h1>
            <p className="text-builders-100">Manage users and system settings</p>
          </div>
          <div className="flex items-center space-x-4">
            <button
              onClick={fetchUsers}
              className="flex items-center px-3 py-2 bg-builders-700 hover:bg-builders-800 rounded-md transition-colors"
            >
              <RefreshCw className="h-4 w-4 mr-2" />
              Refresh
            </button>
            <button
              onClick={exportUserData}
              className="flex items-center px-3 py-2 bg-builders-700 hover:bg-builders-800 rounded-md transition-colors"
            >
              <Download className="h-4 w-4 mr-2" />
              Export
            </button>
            <button
              onClick={() => setShowInviteModal(true)}
              className="flex items-center px-3 py-2 bg-green-600 hover:bg-green-700 rounded-md transition-colors"
            >
              <UserPlus className="h-4 w-4 mr-2" />
              Invite User
            </button>
            <button
              onClick={() => setShowScriptModal(true)}
              className="flex items-center px-3 py-2 bg-purple-600 hover:bg-purple-700 rounded-md transition-colors"
            >
              <Cog className="h-4 w-4 mr-2" />
              Script Control
            </button>
          </div>
        </div>
      </div>

      {/* System Stats */}
      {systemStats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center">
              <Users className="h-8 w-8 text-blue-500" />
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-600">Total Users</p>
                <p className="text-2xl font-bold text-gray-900">{systemStats.total_users}</p>
              </div>
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center">
              <CheckCircle className="h-8 w-8 text-green-500" />
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-600">Active Users</p>
                <p className="text-2xl font-bold text-gray-900">{systemStats.active_users}</p>
              </div>
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center">
              <Clock className="h-8 w-8 text-yellow-500" />
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-600">Pending Setup</p>
                <p className="text-2xl font-bold text-gray-900">{systemStats.pending_users}</p>
              </div>
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center">
              <Activity className="h-8 w-8 text-purple-500" />
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-600">System Status</p>
                <p className="text-sm font-bold text-green-600">Operational</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Script Management Section */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-medium text-gray-900">
              Script Management
            </h3>
            <button
              onClick={() => setShowScriptModal(true)}
              className="flex items-center px-3 py-2 text-sm font-medium text-white bg-purple-600 border border-transparent rounded-md hover:bg-purple-700"
            >
              <Cog className="h-4 w-4 mr-2" />
              Manage Scripts
            </button>
          </div>
        </div>
        
        <div className="p-6">
          {scriptLoading ? (
            <div className="text-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-500 mx-auto mb-2"></div>
              <p className="text-gray-600 text-sm">Loading script configurations...</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Listing Loader & Sellerboard */}
              <div className="border border-gray-200 rounded-lg p-4">
                <div className="flex items-center mb-3">
                  <div className="h-8 w-8 bg-green-100 rounded-full flex items-center justify-center mr-3">
                    <Database className="h-4 w-4 text-green-600" />
                  </div>
                  <div>
                    <h4 className="text-sm font-medium text-gray-900">Listing Loader & Sellerboard</h4>
                    <p className="text-xs text-gray-500">amznUploadConfig</p>
                  </div>
                </div>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-600">Last Processed:</span>
                    <span className="font-medium">
                      {scriptConfigs?.amznUploadConfig?.last_processed_date ? 
                        new Date(scriptConfigs.amznUploadConfig.last_processed_date).toLocaleDateString() : 
                        'Not set'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Status:</span>
                    <span className="text-green-600 font-medium">Ready</span>
                  </div>
                </div>
              </div>

              {/* Prep Uploader */}
              <div className="border border-gray-200 rounded-lg p-4">
                <div className="flex items-center mb-3">
                  <div className="h-8 w-8 bg-blue-100 rounded-full flex items-center justify-center mr-3">
                    <Upload className="h-4 w-4 text-blue-600" />
                  </div>
                  <div>
                    <h4 className="text-sm font-medium text-gray-900">Prep Uploader</h4>
                    <p className="text-xs text-gray-500">config.json</p>
                  </div>
                </div>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-600">Last Processed:</span>
                    <span className="font-medium">
                      {scriptConfigs?.config?.last_processed_date ? 
                        new Date(scriptConfigs.config.last_processed_date).toLocaleDateString() : 
                        'Not set'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Status:</span>
                    <span className="text-blue-600 font-medium">Ready</span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Invitations Section */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-medium text-gray-900">
            Pending Invitations ({invitations.length})
          </h3>
        </div>
        
        {invitations.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Email
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Sent
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Expires
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {invitations.map((invitation) => (
                  <tr key={invitation.token} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                      {invitation.email}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {getRelativeTime(invitation.created_at)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {getExpirationTime(invitation.expires_at)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {new Date(invitation.expires_at) > new Date() ? (
                        <span className="px-2 py-1 text-xs font-medium bg-yellow-100 text-yellow-800 rounded-full">
                          Pending
                        </span>
                      ) : (
                        <span className="px-2 py-1 text-xs font-medium bg-red-100 text-red-800 rounded-full">
                          Expired
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <button
                        onClick={() => handleDeleteInvitation(invitation.token)}
                        className="text-red-600 hover:text-red-900"
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
          <div className="text-center py-12">
            <UserPlus className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-sm font-medium text-gray-900 mb-1">No pending invitations</h3>
            <p className="text-sm text-gray-500">
              Send your first invitation to get started.
            </p>
          </div>
        )}
      </div>

      {/* Error/Success Messages */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex">
            <AlertTriangle className="h-5 w-5 text-red-400 flex-shrink-0" />
            <p className="ml-3 text-sm text-red-700">{error}</p>
          </div>
        </div>
      )}

      {success && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <div className="flex">
            <CheckCircle className="h-5 w-5 text-green-400 flex-shrink-0" />
            <p className="ml-3 text-sm text-green-700">{success}</p>
          </div>
        </div>
      )}

      {/* Controls */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between space-y-4 sm:space-y-0 sm:space-x-4">
          <div className="flex items-center space-x-4 flex-1">
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
              <input
                type="text"
                placeholder="Search users..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10 pr-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-builders-500 w-full"
              />
            </div>
            
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-builders-500"
            >
              <option value="all">All Users</option>
              <option value="active">Active</option>
              <option value="pending">Pending Setup</option>
            </select>
          </div>

          <button
            onClick={() => setShowRawData(!showRawData)}
            className="flex items-center px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 border border-gray-300 rounded-md hover:bg-gray-200"
          >
            {showRawData ? <EyeOff className="h-4 w-4 mr-2" /> : <Eye className="h-4 w-4 mr-2" />}
            {showRawData ? 'Hide Raw Data' : 'Show Raw Data'}
          </button>
        </div>
      </div>

      {/* Raw Data Editor */}
      {showRawData && (
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-medium text-gray-900">Raw User Data (users.json)</h3>
            <button
              onClick={handleBulkUpdate}
              className="flex items-center px-4 py-2 text-sm font-medium text-white bg-red-600 border border-transparent rounded-md hover:bg-red-700"
            >
              <Save className="h-4 w-4 mr-2" />
              Apply Bulk Changes
            </button>
          </div>
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
            <div className="flex">
              <AlertTriangle className="h-5 w-5 text-red-400 flex-shrink-0" />
              <p className="ml-3 text-sm text-red-700">
                <strong>Warning:</strong> Editing raw data can break user accounts. Only modify if you know what you're doing.
              </p>
            </div>
          </div>
          <textarea
            value={rawUserData}
            onChange={(e) => setRawUserData(e.target.value)}
            className="w-full h-64 p-4 border border-gray-300 rounded-md font-mono text-sm focus:outline-none focus:ring-2 focus:ring-builders-500"
            placeholder="Raw JSON data..."
          />
        </div>
      )}

      {/* User Table */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-medium text-gray-900">
            Users ({filteredUsers.length})
          </h3>
        </div>
        
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  User
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Configuration
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Last Activity
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {filteredUsers.map((user) => (
                <tr key={user.discord_id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center">
                      <div className="h-10 w-10 rounded-full bg-builders-100 flex items-center justify-center">
                        <span className="text-sm font-medium text-builders-700">
                          {user.discord_username?.charAt(0)?.toUpperCase() || 'U'}
                        </span>
                      </div>
                      <div className="ml-4">
                        <div className="text-sm font-medium text-gray-900">
                          {user.discord_username || 'Unknown'}
                        </div>
                        <div className="text-sm text-gray-500">
                          {user.email || 'No email'}
                        </div>
                        <div className="text-xs text-gray-400">
                          ID: {user.discord_id}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    {getStatusBadge(user)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    <div className="space-y-1">
                      <div className="flex items-center">
                        {user.profile_configured ? 
                          <CheckCircle className="h-4 w-4 text-green-500 mr-1" /> : 
                          <X className="h-4 w-4 text-red-500 mr-1" />
                        }
                        Profile
                      </div>
                      <div className="flex items-center">
                        {user.google_linked ? 
                          <CheckCircle className="h-4 w-4 text-green-500 mr-1" /> : 
                          <X className="h-4 w-4 text-red-500 mr-1" />
                        }
                        Google
                      </div>
                      <div className="flex items-center">
                        {user.sheet_configured ? 
                          <CheckCircle className="h-4 w-4 text-green-500 mr-1" /> : 
                          <X className="h-4 w-4 text-red-500 mr-1" />
                        }
                        Sheets
                      </div>
                      <div className="flex items-center">
                        {user.enable_source_links ? 
                          <CheckCircle className="h-4 w-4 text-green-500 mr-1" /> : 
                          <X className="h-4 w-4 text-red-500 mr-1" />
                        }
                        COGS
                      </div>
                      <div className="flex items-center">
                        {user.search_all_worksheets ? 
                          <CheckCircle className="h-4 w-4 text-green-500 mr-1" /> : 
                          <X className="h-4 w-4 text-red-500 mr-1" />
                        }
                        All Sheets
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {user.last_activity ? (
                      <div>
                        <div className="font-medium">{getRelativeTime(user.last_activity)}</div>
                        <div className="text-xs text-gray-400">
                          {new Date(user.last_activity).toLocaleDateString()} {new Date(user.last_activity).toLocaleTimeString()}
                        </div>
                      </div>
                    ) : (
                      <span className="text-gray-400">Never</span>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                    <div className="flex items-center justify-end space-x-2">
                      <button
                        onClick={() => handleViewUserDashboard(user.discord_id)}
                        className="text-blue-600 hover:text-blue-900"
                        title="View User's Dashboard"
                      >
                        <ExternalLink className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => setEditingUser(user)}
                        className="text-builders-600 hover:text-builders-900"
                        title="Edit User"
                      >
                        <Edit3 className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => handleDeleteUser(user.discord_id)}
                        className="text-red-600 hover:text-red-900"
                        title="Delete User"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {filteredUsers.length === 0 && (
          <div className="text-center py-12">
            <Users className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-sm font-medium text-gray-900 mb-1">No users found</h3>
            <p className="text-sm text-gray-500">
              {searchTerm || filterStatus !== 'all' 
                ? 'Try adjusting your search or filter criteria.' 
                : 'No users have been registered yet.'}
            </p>
          </div>
        )}
      </div>

      {/* Edit User Modal */}
      {editingUser && (
        <UserEditModal
          user={editingUser}
          onSave={handleUpdateUser}
          onCancel={() => setEditingUser(null)}
        />
      )}

      {/* Invite User Modal */}
      {showInviteModal && (
        <InviteModal
          inviteEmail={inviteEmail}
          setInviteEmail={setInviteEmail}
          onSave={handleSendInvitation}
          onCancel={() => setShowInviteModal(false)}
        />
      )}

      {/* Script Config Modal */}
      {showScriptModal && (
        <ScriptConfigModal
          configs={scriptConfigs}
          onSave={handleUpdateScriptConfigs}
          onTrigger={handleTriggerScript}
          onCancel={() => setShowScriptModal(false)}
          loading={scriptLoading}
        />
      )}
    </div>
  );
};

export default Admin;