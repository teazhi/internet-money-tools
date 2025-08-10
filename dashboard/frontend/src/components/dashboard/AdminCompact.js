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
  ExternalLink
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
  const [scriptConfigs, setScriptConfigs] = useState({});
  const [discountMonitoring, setDiscountMonitoring] = useState(null);
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [filteredUsers, setFilteredUsers] = useState([]);

  const isAdmin = user?.discord_id === '712147636463075389';

  const [scriptModalOpen, setScriptModalOpen] = useState(false);
  const [editingConfigs, setEditingConfigs] = useState({});
  const [savingConfigs, setSavingConfigs] = useState(false);

  const fetchData = useCallback(async () => {
    if (!isAdmin) return;
    
    try {
      setLoading(true);
      const [usersRes, statsRes, invitesRes, scriptsRes, discountRes] = await Promise.all([
        axios.get('/api/admin/users', { withCredentials: true }),
        axios.get('/api/admin/stats', { withCredentials: true }),
        axios.get('/api/admin/invitations', { withCredentials: true }),
        axios.get('/api/admin/script-configs', { withCredentials: true }),
        axios.get(API_ENDPOINTS.DISCOUNT_MONITORING_STATUS, { withCredentials: true })
      ]);
      
      const users = usersRes.data.users;
      setUsers(users);
      setSystemStats(statsRes.data);
      setInvitations(invitesRes.data.invitations || []);
      setScriptConfigs(scriptsRes.data);
      setEditingConfigs(scriptsRes.data);
      setDiscountMonitoring(discountRes.data);
      
      // Organize users hierarchically
      console.log('DEBUG: All users from API:', users.length);
      console.log('DEBUG: First user sample:', users[0]);
      
      const mainUsers = users.filter(user => user.user_type !== 'subuser');
      const subUsers = users.filter(user => user.user_type === 'subuser');
      
      console.log('DEBUG: Main users:', mainUsers.length);
      console.log('DEBUG: Sub users found:', subUsers.length);
      if (subUsers.length > 0) {
        console.log('DEBUG: Sub users:', subUsers.map(u => ({
          username: u.discord_username,
          user_type: u.user_type,
          parent_discord_id: u.parent_discord_id
        })));
      }
      
      const hierarchicalUsers = [];
      mainUsers.forEach(mainUser => {
        hierarchicalUsers.push({...mainUser, isMainUser: true});
        const userSubUsers = subUsers.filter(sub => sub.parent_discord_id === mainUser.discord_id);
        console.log(`DEBUG: Sub users for ${mainUser.discord_username}:`, userSubUsers.length);
        userSubUsers.forEach(subUser => {
          hierarchicalUsers.push({...subUser, isSubUser: true, parentUser: mainUser});
        });
      });
      
      console.log('DEBUG: Final hierarchical users:', hierarchicalUsers.length);
      setFilteredUsers(hierarchicalUsers);
    } catch (error) {
      setError('Failed to load admin data');
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

  const handleSaveScriptConfigs = async () => {
    setSavingConfigs(true);
    try {
      await axios.post('/api/admin/script-configs', editingConfigs, { withCredentials: true });
      setScriptConfigs(editingConfigs);
      setSuccess('Script configurations updated successfully!');
      setScriptModalOpen(false);
    } catch (error) {
      setError('Failed to save script configurations');
    } finally {
      setSavingConfigs(false);
    }
  };

  const handleConfigChange = (configKey, field, value) => {
    setEditingConfigs(prev => ({
      ...prev,
      [configKey]: {
        ...prev[configKey],
        [field]: value
      }
    }));
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
    { id: 'scripts', name: 'Scripts', icon: Cog, count: null },
    { id: 'discount', name: 'Discounts', icon: Percent, count: null }
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
                          
                          if (index === 0) {
                            console.log('DEBUG: First rendered user:', {
                              username: user.discord_username,
                              user_type: user.user_type,
                              isSubUser: user.isSubUser,
                              isSubuser: isSubuser
                            });
                          }
                          
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
                                  <button className="text-gray-400 hover:text-gray-600">
                                    <Edit3 className="h-4 w-4" />
                                  </button>
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


              {/* Scripts Tab */}
              {activeTab === 'scripts' && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-semibold text-gray-900">Script Configuration</h3>
                    <button
                      onClick={() => setScriptModalOpen(true)}
                      className="flex items-center px-3 py-2 bg-builders-600 text-white rounded-md text-sm hover:bg-builders-700"
                    >
                      <Settings className="h-4 w-4 mr-1" />
                      Configure
                    </button>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="border rounded-lg p-4">
                      <div className="flex items-center mb-3">
                        <Database className="h-6 w-6 text-green-500 mr-2" />
                        <div>
                          <h4 className="font-medium">Listing Loader</h4>
                          <p className="text-xs text-gray-500">Amazon orders processing</p>
                        </div>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-gray-600">
                          Last: {scriptConfigs?.amznUploadConfig?.last_processed_date || 'Not set'}
                        </span>
                        <button className="flex items-center px-2 py-1 bg-green-600 text-white rounded text-xs hover:bg-green-700">
                          <Play className="h-3 w-3 mr-1" />
                          Run
                        </button>
                      </div>
                    </div>
                    
                    <div className="border rounded-lg p-4">
                      <div className="flex items-center mb-3">
                        <Upload className="h-6 w-6 text-blue-500 mr-2" />
                        <div>
                          <h4 className="font-medium">Prep Uploader</h4>
                          <p className="text-xs text-gray-500">Prep center automation</p>
                        </div>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-gray-600">
                          Last: {scriptConfigs?.config?.last_processed_date || 'Not set'}
                        </span>
                        <button className="flex items-center px-2 py-1 bg-blue-600 text-white rounded text-xs hover:blue-700">
                          <Play className="h-3 w-3 mr-1" />
                          Run
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Discount Tab */}
              {activeTab === 'discount' && discountMonitoring && (
                <div className="space-y-4">
                  <div className="border rounded-lg p-4">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center">
                        <Mail className={`h-6 w-6 mr-2 ${
                          discountMonitoring.email_configured ? 'text-green-500' : 'text-red-500'
                        }`} />
                        <div>
                          <h4 className="font-medium">Distill.io Monitoring</h4>
                          <p className="text-xs text-gray-500">Email: {discountMonitoring.sender_email}</p>
                        </div>
                      </div>
                      <span className={`px-2 py-1 rounded text-xs font-medium ${
                        discountMonitoring.status === 'active' 
                          ? 'bg-green-100 text-green-800' 
                          : 'bg-red-100 text-red-800'
                      }`}>
                        {discountMonitoring.status === 'active' ? 'Active' : 'Inactive'}
                      </span>
                    </div>
                    
                    {discountMonitoring.email_configured && (
                      <div className="space-y-2 text-sm">
                        <div className="flex justify-between">
                          <span className="text-gray-600">Monitor Email:</span>
                          <span className="font-medium">{discountMonitoring.monitor_email}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-600">Keywords:</span>
                          <span className="font-medium">{discountMonitoring.keywords?.length || 0}</span>
                        </div>
                      </div>
                    )}
                  </div>
                  
                  {discountMonitoring.keywords && (
                    <div className="border rounded-lg p-4">
                      <h5 className="font-medium mb-2">Keywords</h5>
                      <div className="flex flex-wrap gap-2">
                        {discountMonitoring.keywords.map((keyword, index) => (
                          <span
                            key={index}
                            className="inline-flex items-center px-2 py-1 rounded text-xs bg-purple-100 text-purple-800"
                          >
                            {keyword}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

            </>
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

      {/* Script Configuration Modal */}
      {scriptModalOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-medium">Script Configuration</h3>
              <button
                onClick={() => setScriptModalOpen(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            
            <div className="space-y-6">
              {/* Amazon Upload Config */}
              <div className="border rounded-lg p-4">
                <h4 className="font-medium text-gray-900 mb-3 flex items-center">
                  <Database className="h-5 w-5 mr-2 text-green-500" />
                  Amazon Listing Loader Configuration
                </h4>
                <div className="space-y-3">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Last Processed Date
                    </label>
                    <input
                      type="date"
                      value={editingConfigs?.amznUploadConfig?.last_processed_date || ''}
                      onChange={(e) => handleConfigChange('amznUploadConfig', 'last_processed_date', e.target.value)}
                      className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-builders-500"
                    />
                  </div>
                </div>
              </div>

              {/* Prep Center Config */}
              <div className="border rounded-lg p-4">
                <h4 className="font-medium text-gray-900 mb-3 flex items-center">
                  <Upload className="h-5 w-5 mr-2 text-blue-500" />
                  Prep Center Configuration
                </h4>
                <div className="space-y-3">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Last Processed Date
                    </label>
                    <input
                      type="date"
                      value={editingConfigs?.config?.last_processed_date || ''}
                      onChange={(e) => handleConfigChange('config', 'last_processed_date', e.target.value)}
                      className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-builders-500"
                    />
                  </div>
                </div>
              </div>
            </div>
              
            <div className="flex justify-end space-x-3 mt-6">
              <button
                onClick={() => setScriptModalOpen(false)}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveScriptConfigs}
                disabled={savingConfigs}
                className="px-4 py-2 text-sm font-medium text-white bg-builders-600 border border-transparent rounded-md hover:bg-builders-700 disabled:opacity-50"
              >
                {savingConfigs ? 'Saving...' : 'Save Configuration'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminCompact;