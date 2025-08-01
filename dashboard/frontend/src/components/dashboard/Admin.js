import React, { useState, useEffect, useCallback, useMemo } from 'react';
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
  Cog,
  FileText,
  ChevronDown,
  ChevronUp
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

const ScriptConfigModal = ({ configs, onSave, onCancel, onTrigger, loading, lambdaLogs, logsLoading, showLogs, onToggleLogs, onFetchLogs, formatLogTimestamp, getLogLevel, getLogLevelColor }) => {
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
    // For date-only inputs, just return YYYY-MM-DD format
    if (dateString.includes('T')) {
      // If it's an ISO datetime, extract just the date part
      return dateString.split('T')[0];
    }
    return dateString; // Assume it's already in YYYY-MM-DD format
  };

  const formatDateForAPI = (dateString) => {
    if (!dateString) return '';
    // For date-only inputs, just return the date string as-is
    return dateString;
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
                  {loading ? 'Processing...' : 'Run Lambda'}
                </button>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Last Processed Date
                </label>
                <input
                  type="date"
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
                  Current: {configs?.amznUploadConfig?.last_processed_date || 'Not set'}
                </p>
              </div>
              
              {/* View Logs Button */}
              <div className="mt-3">
                <button
                  onClick={() => onToggleLogs('cost_updater')}
                  className="flex items-center px-3 py-2 text-sm font-medium text-gray-700 bg-gray-100 border border-gray-300 rounded-md hover:bg-gray-200"
                >
                  <FileText className="h-4 w-4 mr-2" />
                  {showLogs.cost_updater ? 'Hide Logs' : 'View Logs'}
                  {showLogs.cost_updater ? <ChevronUp className="h-4 w-4 ml-2" /> : <ChevronDown className="h-4 w-4 ml-2" />}
                </button>
              </div>
              
              {/* Logs Display */}
              {showLogs.cost_updater && (
                <div className="mt-3 border border-gray-200 rounded-lg p-3 bg-gray-50">
                  <div className="flex items-center justify-between mb-2">
                    <h5 className="text-sm font-medium text-gray-900">Recent Logs</h5>
                    <button
                      onClick={() => onFetchLogs('cost_updater')}
                      disabled={logsLoading}
                      className="text-xs text-blue-600 hover:text-blue-800 disabled:opacity-50"
                    >
                      {logsLoading ? 'Loading...' : 'Refresh'}
                    </button>
                  </div>
                  
                  <div className="max-h-64 overflow-y-auto space-y-1">
                    {lambdaLogs.cost_updater?.logs?.length > 0 ? (
                      lambdaLogs.cost_updater.logs.map((log, index) => {
                        const level = getLogLevel(log.message);
                        return (
                          <div key={index} className={`text-xs p-2 rounded border ${getLogLevelColor(level)}`}>
                            <div className="flex justify-between items-start mb-1">
                              <span className="font-mono text-xs text-gray-500">
                                {formatLogTimestamp(log.timestamp)}
                              </span>
                              <span className={`px-1 py-0.5 rounded text-xs font-medium ${getLogLevelColor(level)}`}>
                                {level.toUpperCase()}
                              </span>
                            </div>
                            <div className="font-mono text-xs whitespace-pre-wrap break-all">
                              {log.message}
                            </div>
                          </div>
                        );
                      })
                    ) : (
                      <p className="text-xs text-gray-500 text-center py-4">
                        {logsLoading ? 'Loading logs...' : 'No logs available'}
                      </p>
                    )}
                  </div>
                </div>
              )}
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
                  {loading ? 'Processing...' : 'Run Lambda'}
                </button>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Last Processed Date
                </label>
                <input
                  type="date"
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
                  Current: {configs?.config?.last_processed_date || 'Not set'}
                </p>
              </div>
              
              {/* View Logs Button */}
              <div className="mt-3">
                <button
                  onClick={() => onToggleLogs('prep_uploader')}
                  className="flex items-center px-3 py-2 text-sm font-medium text-gray-700 bg-gray-100 border border-gray-300 rounded-md hover:bg-gray-200"
                >
                  <FileText className="h-4 w-4 mr-2" />
                  {showLogs.prep_uploader ? 'Hide Logs' : 'View Logs'}
                  {showLogs.prep_uploader ? <ChevronUp className="h-4 w-4 ml-2" /> : <ChevronDown className="h-4 w-4 ml-2" />}
                </button>
              </div>
              
              {/* Logs Display */}
              {showLogs.prep_uploader && (
                <div className="mt-3 border border-gray-200 rounded-lg p-3 bg-gray-50">
                  <div className="flex items-center justify-between mb-2">
                    <h5 className="text-sm font-medium text-gray-900">Recent Logs</h5>
                    <button
                      onClick={() => onFetchLogs('prep_uploader')}
                      disabled={logsLoading}
                      className="text-xs text-blue-600 hover:text-blue-800 disabled:opacity-50"
                    >
                      {logsLoading ? 'Loading...' : 'Refresh'}
                    </button>
                  </div>
                  
                  <div className="max-h-64 overflow-y-auto space-y-1">
                    {lambdaLogs.prep_uploader?.logs?.length > 0 ? (
                      lambdaLogs.prep_uploader.logs.map((log, index) => {
                        const level = getLogLevel(log.message);
                        return (
                          <div key={index} className={`text-xs p-2 rounded border ${getLogLevelColor(level)}`}>
                            <div className="flex justify-between items-start mb-1">
                              <span className="font-mono text-xs text-gray-500">
                                {formatLogTimestamp(log.timestamp)}
                              </span>
                              <span className={`px-1 py-0.5 rounded text-xs font-medium ${getLogLevelColor(level)}`}>
                                {level.toUpperCase()}
                              </span>
                            </div>
                            <div className="font-mono text-xs whitespace-pre-wrap break-all">
                              {log.message}
                            </div>
                          </div>
                        );
                      })
                    ) : (
                      <p className="text-xs text-gray-500 text-center py-4">
                        {logsLoading ? 'Loading logs...' : 'No logs available'}
                      </p>
                    )}
                  </div>
                </div>
              )}
            </div>

            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <div className="flex">
                <div className="flex-shrink-0">
                  <svg className="h-5 w-5 text-blue-400" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                  </svg>
                </div>
                <div className="ml-3">
                  <p className="text-sm text-blue-700">
                    <strong>How it works:</strong>
                  </p>
                  <ul className="text-sm text-blue-600 mt-2 space-y-1">
                    <li>• <strong>Save Dates Only:</strong> Updates S3 config files without running anything</li>
                    <li>• <strong>Run Lambda:</strong> Invokes the Lambda function which reads its own config from S3</li>
                    <li>• Lambda functions handle their own date processing logic</li>
                  </ul>
                </div>
              </div>
            </div>

            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
              <div className="flex">
                <AlertTriangle className="h-5 w-5 text-yellow-400 flex-shrink-0" />
                <div className="ml-3">
                  <p className="text-sm text-yellow-700">
                    <strong>Note:</strong> Setting dates to the past will cause Lambda functions to reprocess old data when invoked.
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
              {loading ? 'Saving...' : 'Save Dates Only'}
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
  const [lambdaLogs, setLambdaLogs] = useState({});
  const [logsLoading, setLogsLoading] = useState(false);
  const [showLogs, setShowLogs] = useState({});

  // Hook definitions must come before any early returns
  const fetchUsers = useCallback(async () => {
    try {
      setError('');
      setLoading(true);
      const response = await axios.get('/api/admin/users', { withCredentials: true });
      setUsers(response.data.users);
      setRawUserData(JSON.stringify(response.data.users, null, 2));
    } catch (error) {
      console.error('Failed to fetch users:', error);
      setError(error.response?.data?.error || 'Failed to fetch users');
    } finally {
      setLoading(false);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchSystemStats = useCallback(async () => {
    try {
      const response = await axios.get('/api/admin/stats', { withCredentials: true });
      setSystemStats(response.data);
    } catch (error) {
      console.error('Failed to fetch system stats:', error);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchInvitations = useCallback(async () => {
    try {
      const response = await axios.get('/api/admin/invitations', { withCredentials: true });
      // Filter to only show pending invitations
      const pendingInvitations = response.data.invitations.filter(inv => inv.status === 'pending');
      setInvitations(pendingInvitations);
    } catch (error) {
      console.error('Failed to fetch invitations:', error);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const filteredUsers = useMemo(() => {
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
  }, [users, searchTerm, filterStatus]);

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
    
    // Use user's timezone for longer time periods
    const userTimezone = user?.user_record?.timezone;
    const options = {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      ...(userTimezone && { timeZone: userTimezone })
    };
    return date.toLocaleDateString('en-US', options);
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
    
    // Use user's timezone for longer time periods
    const userTimezone = user?.user_record?.timezone;
    const options = {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      ...(userTimezone && { timeZone: userTimezone })
    };
    return date.toLocaleDateString('en-US', options);
  };
  
  // Check if current user is admin
  const isAdmin = user?.discord_id === '712147636463075389';

  useEffect(() => {
    if (isAdmin) {
      fetchUsers();
      fetchSystemStats();
      fetchInvitations();
      fetchScriptConfigs();
    }
  }, [isAdmin, fetchUsers, fetchSystemStats, fetchInvitations]);

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

  const handleUpdateScriptConfigs = async (configData) => {
    try {
      setError('');
      setSuccess('');
      setScriptLoading(true);
      
      console.log('[SCRIPT CONFIG] Updating configs:', configData);
      
      const response = await axios.post('/api/admin/script-configs', configData, { withCredentials: true });
      
      setSuccess('Script configurations updated successfully');
      
      // Small delay to ensure backend has processed the update
      await new Promise(resolve => setTimeout(resolve, 500));
      
      // Refresh the configs to show the updated values
      await fetchScriptConfigs();
      
      // Close the modal
      setShowScriptModal(false);
      
    } catch (error) {
      console.error('Script config update error:', error);
      setError(error.response?.data?.error || 'Failed to update script configurations');
    } finally {
      setScriptLoading(false);
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

  const handleTriggerScript = async (scriptType) => {
    if (!window.confirm(`Are you sure you want to run the ${scriptType} Lambda function? It will read the current saved date from S3.`)) {
      return;
    }

    try {
      setError('');
      setSuccess('');
      setScriptLoading(true);
      
      const response = await axios.post('/api/admin/trigger-script', 
        { script_type: scriptType }, 
        { withCredentials: true }
      );
      
      setSuccess(`${scriptType} script triggered successfully`);
      
      // Refresh script configs to show updated dates
      await fetchScriptConfigs();
      
      // Also refresh logs to see any new activity
      if (scriptType === 'listing_loader') {
        fetchLambdaLogs('cost_updater');
      } else if (scriptType === 'prep_uploader') {
        fetchLambdaLogs('prep_uploader');
      }
      
    } catch (error) {
      console.error('Script trigger error:', error);
      setError(error.response?.data?.error || `Failed to trigger ${scriptType} script`);
    } finally {
      setScriptLoading(false);
    }
  };

  const fetchLambdaLogs = async (functionName, hours = 24) => {
    try {
      setLogsLoading(true);
      const response = await axios.get('/api/admin/lambda-logs', {
        params: { function: functionName, hours },
        withCredentials: true
      });
      setLambdaLogs(prev => ({
        ...prev,
        [functionName]: response.data
      }));
    } catch (error) {
      console.error(`Failed to fetch ${functionName} logs:`, error);
      setError(`Failed to fetch ${functionName} logs`);
    } finally {
      setLogsLoading(false);
    }
  };

  const toggleLogs = (functionName) => {
    setShowLogs(prev => ({
      ...prev,
      [functionName]: !prev[functionName]
    }));
    
    // Fetch logs if showing and not already loaded
    if (!showLogs[functionName] && !lambdaLogs[functionName]) {
      fetchLambdaLogs(functionName);
    }
  };

  const formatLogTimestamp = (timestamp) => {
    return new Date(timestamp).toLocaleString();
  };

  const getLogLevel = (message) => {
    if (message.includes('[ERROR]') || message.includes('ERROR') || message.includes('Exception')) {
      return 'error';
    }
    if (message.includes('[WARN]') || message.includes('WARNING')) {
      return 'warning';
    }
    if (message.includes('[DEBUG]') || message.includes('DEBUG')) {
      return 'debug';
    }
    return 'info';
  };

  const getLogLevelColor = (level) => {
    switch (level) {
      case 'error': return 'text-red-600 bg-red-50';
      case 'warning': return 'text-yellow-600 bg-yellow-50';
      case 'debug': return 'text-gray-600 bg-gray-50';
      default: return 'text-blue-600 bg-blue-50';
    }
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
      <div className="space-y-6">
        {/* Header Skeleton */}
        <div className="bg-gradient-to-r from-builders-500 to-builders-600 rounded-lg shadow-sm p-6">
          <div className="flex items-center justify-between">
            <div>
              <div className="h-8 bg-white/20 rounded w-32 mb-2 animate-pulse"></div>
              <div className="h-4 bg-white/20 rounded w-48 animate-pulse"></div>
            </div>
            <div className="flex items-center space-x-4">
              <div className="h-10 bg-white/20 rounded w-20 animate-pulse"></div>
              <div className="h-10 bg-white/20 rounded w-20 animate-pulse"></div>
            </div>
          </div>
        </div>

        {/* Stats Grid Skeleton */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="bg-white rounded-lg shadow p-4 animate-pulse">
              <div className="flex items-center">
                <div className="h-8 w-8 bg-gray-300 rounded"></div>
                <div className="ml-3 flex-1">
                  <div className="h-4 bg-gray-300 rounded w-16 mb-1"></div>
                  <div className="h-6 bg-gray-300 rounded w-8"></div>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Search/Filter Skeleton */}
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between space-y-4 sm:space-y-0">
            <div className="h-10 bg-gray-300 rounded w-64 animate-pulse"></div>
            <div className="flex items-center space-x-4">
              <div className="h-10 bg-gray-300 rounded w-32 animate-pulse"></div>
              <div className="h-10 bg-gray-300 rounded w-24 animate-pulse"></div>
            </div>
          </div>
        </div>

        {/* User Table Skeleton */}
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200">
            <div className="h-6 bg-gray-300 rounded w-24 animate-pulse"></div>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  {['User', 'Status', 'Activity', 'Scripts', 'Actions'].map((header, i) => (
                    <th key={i} className="px-6 py-3">
                      <div className="h-4 bg-gray-300 rounded w-16 animate-pulse"></div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {[1, 2, 3, 4, 5].map(i => (
                  <tr key={i} className="animate-pulse">
                    <td className="px-6 py-4">
                      <div className="flex items-center">
                        <div className="h-10 w-10 bg-gray-300 rounded-full"></div>
                        <div className="ml-4">
                          <div className="h-4 bg-gray-300 rounded w-32 mb-1"></div>
                          <div className="h-3 bg-gray-300 rounded w-48"></div>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="h-6 bg-gray-300 rounded-full w-16"></div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="h-4 bg-gray-300 rounded w-20"></div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="h-6 bg-gray-300 rounded w-12"></div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center space-x-2">
                        <div className="h-8 bg-gray-300 rounded w-16"></div>
                        <div className="h-8 bg-gray-300 rounded w-16"></div>
                        <div className="h-8 bg-gray-300 rounded w-16"></div>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Loading indicator */}
        <div className="text-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-builders-500 mx-auto mb-2"></div>
          <p className="text-gray-600 text-sm">Loading admin panel data...</p>
          <p className="text-gray-500 text-xs mt-1">Fetching users, system stats, and invitations</p>
        </div>
      </div>
    );
  }


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
              onClick={() => {
                fetchScriptConfigs();
                setShowScriptModal(true);
              }}
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
              onClick={() => {
                fetchScriptConfigs();
                setShowScriptModal(true);
              }}
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
                        new Date(scriptConfigs.amznUploadConfig.last_processed_date).toLocaleDateString('en-US', {
                          year: 'numeric',
                          month: 'short',
                          day: 'numeric',
                          ...(user?.user_record?.timezone && { timeZone: user.user_record.timezone })
                        }) : 
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
                        new Date(scriptConfigs.config.last_processed_date).toLocaleDateString('en-US', {
                          year: 'numeric',
                          month: 'short',
                          day: 'numeric',
                          ...(user?.user_record?.timezone && { timeZone: user.user_record.timezone })
                        }) : 
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
                      {invitation.status === 'pending' && new Date(invitation.expires_at) > new Date() ? (
                        <span className="px-2 py-1 text-xs font-medium bg-yellow-100 text-yellow-800 rounded-full">
                          Pending
                        </span>
                      ) : invitation.status === 'accepted' ? (
                        <span className="px-2 py-1 text-xs font-medium bg-green-100 text-green-800 rounded-full">
                          Accepted
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
                          {new Date(user.last_activity).toLocaleDateString('en-US', {
                            year: 'numeric',
                            month: 'short',
                            day: 'numeric',
                            ...(user?.user_record?.timezone && { timeZone: user.user_record.timezone })
                          })} {new Date(user.last_activity).toLocaleTimeString('en-US', {
                            hour: '2-digit',
                            minute: '2-digit',
                            ...(user?.user_record?.timezone && { timeZone: user.user_record.timezone })
                          })}
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
          lambdaLogs={lambdaLogs}
          logsLoading={logsLoading}
          showLogs={showLogs}
          onToggleLogs={toggleLogs}
          onFetchLogs={fetchLambdaLogs}
          formatLogTimestamp={formatLogTimestamp}
          getLogLevel={getLogLevel}
          getLogLevelColor={getLogLevelColor}
        />
      )}
    </div>
  );
};

export default Admin;