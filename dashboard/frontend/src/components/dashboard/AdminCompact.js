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
  const [groups, setGroups] = useState([]);
  const [showGroupModal, setShowGroupModal] = useState(false);
  const [selectedGroup, setSelectedGroup] = useState(null);
  const [newGroupData, setNewGroupData] = useState({ group_key: '', group_name: '', description: '' });
  const [groupMembers, setGroupMembers] = useState([]);
  const [groupFeatures, setGroupFeatures] = useState({});
  const [activeGroupTab, setActiveGroupTab] = useState('members');

  const isAdmin = user?.discord_id === '712147636463075389';

  const fetchData = useCallback(async () => {
    if (!isAdmin) return;
    
    try {
      setLoading(true);
      const [usersRes, statsRes, invitesRes, discountRes, featuresRes, userFeaturesRes, groupsRes] = await Promise.all([
        axios.get('/api/admin/users', { withCredentials: true }),
        axios.get('/api/admin/stats', { withCredentials: true }),
        axios.get('/api/admin/invitations', { withCredentials: true }),
        axios.get(API_ENDPOINTS.DISCOUNT_MONITORING_STATUS, { withCredentials: true }),
        axios.get('/api/admin/features', { withCredentials: true }),
        axios.get('/api/admin/user-features', { withCredentials: true }),
        axios.get('/api/admin/groups', { withCredentials: true })
      ]);
      
      const users = usersRes.data.users;
      setUsers(users);
      setSystemStats(statsRes.data);
      setInvitations(invitesRes.data.invitations || []);
      setDiscountMonitoring(discountRes.data);
      setFeatures(featuresRes.data.features || []);
      setUserFeatureAccess(userFeaturesRes.data.user_features || {});
      setGroups(groupsRes.data.groups || []);
      
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

  const fetchGroupData = async (groupKey) => {
    try {
      const [membersRes, featuresRes] = await Promise.all([
        axios.get(`/api/admin/groups/${groupKey}/members`, { withCredentials: true }),
        axios.get(`/api/admin/groups/${groupKey}/features`, { withCredentials: true })
      ]);
      
      setGroupMembers(membersRes.data.members || []);
      setGroupFeatures(featuresRes.data.features || {});
    } catch (error) {
      setError('Failed to fetch group data');
    }
  };

  const handleAddUserToGroup = async (userId, groupKey) => {
    try {
      await axios.post(`/api/admin/groups/${groupKey}/members`, {
        user_id: userId
      }, { withCredentials: true });
      
      setSuccess('User added to group successfully!');
      fetchGroupData(groupKey);
      fetchData(); // Refresh main data to update member counts
    } catch (error) {
      setError('Failed to add user to group');
    }
  };

  const handleRemoveUserFromGroup = async (userId, groupKey) => {
    try {
      await axios.delete(`/api/admin/groups/${groupKey}/members/${userId}`, { withCredentials: true });
      setSuccess('User removed from group successfully!');
      fetchGroupData(groupKey);
      fetchData(); // Refresh main data to update member counts
    } catch (error) {
      setError('Failed to remove user from group');
    }
  };

  const handleToggleGroupFeatureAccess = async (groupKey, featureKey) => {
    try {
      setError('');
      const currentAccess = groupFeatures[featureKey]?.has_access || false;
      
      if (currentAccess) {
        await axios.delete(`/api/admin/groups/${groupKey}/features/${featureKey}`, { withCredentials: true });
      } else {
        await axios.post(`/api/admin/groups/${groupKey}/features`, {
          feature_key: featureKey
        }, { withCredentials: true });
      }
      
      setSuccess(`Group feature access ${currentAccess ? 'removed' : 'granted'} successfully!`);
      fetchGroupData(groupKey);
    } catch (error) {
      setError('Failed to update group feature access');
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
    { id: 'groups', name: 'Groups', icon: UserPlus, count: groups.length }
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

              {/* Groups Tab */}
              {activeTab === 'groups' && (
                <div className="space-y-6">
                  {/* Groups Overview */}
                  <div className="flex justify-between items-center">
                    <div>
                      <h3 className="text-lg font-medium text-gray-900">User Groups</h3>
                      <p className="text-sm text-gray-600">
                        Organize users into groups for easier feature access management.
                      </p>
                    </div>
                    <button
                      onClick={() => {
                        setNewGroupData({ group_key: '', group_name: '', description: '' });
                        setShowGroupModal(true);
                      }}
                      className="flex items-center px-3 py-2 bg-builders-600 text-white rounded-md text-sm hover:bg-builders-700"
                    >
                      <Plus className="h-4 w-4 mr-1" />
                      Create Group
                    </button>
                  </div>

                  {/* Groups List */}
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {groups.map((group) => (
                      <div key={group.group_key} className="bg-white rounded-lg shadow p-4 hover:shadow-md transition-shadow">
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <h4 className="text-lg font-medium text-gray-900">{group.group_name}</h4>
                            <p className="text-sm text-gray-600 mt-1">{group.description}</p>
                            <div className="mt-3 flex items-center text-sm text-gray-500">
                              <UserPlus className="h-4 w-4 mr-1" />
                              <span>{group.member_count} members</span>
                            </div>
                          </div>
                          <button
                            onClick={() => {
                              setSelectedGroup(group);
                              setShowGroupModal(true);
                            }}
                            className="text-gray-400 hover:text-gray-600"
                          >
                            <Settings className="h-5 w-5" />
                          </button>
                        </div>
                        
                        <div className="mt-4 flex space-x-2">
                          <button
                            onClick={async () => {
                              setSelectedGroup(group);
                              setActiveGroupTab('members');
                              setShowGroupModal(true);
                              await fetchGroupData(group.group_key);
                            }}
                            className="flex-1 px-3 py-2 bg-blue-50 text-blue-700 rounded-md text-sm hover:bg-blue-100"
                          >
                            Manage Members
                          </button>
                          <button 
                            onClick={async () => {
                              setSelectedGroup(group);
                              setActiveGroupTab('features');
                              setShowGroupModal(true);
                              await fetchGroupData(group.group_key);
                            }}
                            className="flex-1 px-3 py-2 bg-green-50 text-green-700 rounded-md text-sm hover:bg-green-100"
                          >
                            Set Permissions
                          </button>
                        </div>
                      </div>
                    ))}
                    
                    {groups.length === 0 && (
                      <div className="col-span-full text-center py-8">
                        <UserPlus className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                        <h3 className="text-lg font-medium text-gray-900 mb-2">No Groups Yet</h3>
                        <p className="text-gray-600 mb-4">
                          Create user groups to manage feature access more efficiently.
                        </p>
                        <button
                          onClick={() => {
                            setNewGroupData({ group_key: '', group_name: '', description: '' });
                            setShowGroupModal(true);
                          }}
                          className="inline-flex items-center px-4 py-2 bg-builders-600 text-white rounded-md hover:bg-builders-700"
                        >
                          <Plus className="h-4 w-4 mr-2" />
                          Create Your First Group
                        </button>
                      </div>
                    )}
                  </div>
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

      {/* Group Management Modal */}
      {showGroupModal && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
          <div className="relative top-10 mx-auto p-5 border w-11/12 md:w-3/4 lg:w-1/2 shadow-lg rounded-md bg-white max-h-screen overflow-y-auto">
            <div className="mt-3">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-medium text-gray-900">
                  {selectedGroup ? `Manage Group: ${selectedGroup.group_name}` : 'Create New Group'}
                </h3>
                <button
                  onClick={() => {
                    setShowGroupModal(false);
                    setSelectedGroup(null);
                    setNewGroupData({ group_key: '', group_name: '', description: '' });
                  }}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
              
              {!selectedGroup ? (
                // Create New Group Form
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Group Key</label>
                    <input
                      type="text"
                      value={newGroupData.group_key}
                      onChange={(e) => setNewGroupData({...newGroupData, group_key: e.target.value})}
                      placeholder="e.g., premium_users"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-builders-500"
                    />
                    <p className="text-xs text-gray-500 mt-1">Unique identifier (lowercase, underscores only)</p>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Group Name</label>
                    <input
                      type="text"
                      value={newGroupData.group_name}
                      onChange={(e) => setNewGroupData({...newGroupData, group_name: e.target.value})}
                      placeholder="e.g., Premium Users"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-builders-500"
                    />
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                    <textarea
                      value={newGroupData.description}
                      onChange={(e) => setNewGroupData({...newGroupData, description: e.target.value})}
                      placeholder="Describe this group's purpose..."
                      rows={3}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-builders-500"
                    />
                  </div>
                  
                  <div className="flex justify-end space-x-3 mt-6">
                    <button
                      onClick={() => {
                        setShowGroupModal(false);
                        setNewGroupData({ group_key: '', group_name: '', description: '' });
                      }}
                      className="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={async () => {
                        try {
                          await axios.post('/api/admin/groups', newGroupData, { withCredentials: true });
                          setSuccess('Group created successfully!');
                          setShowGroupModal(false);
                          setNewGroupData({ group_key: '', group_name: '', description: '' });
                          fetchData();
                        } catch (error) {
                          setError('Failed to create group');
                        }
                      }}
                      disabled={!newGroupData.group_key || !newGroupData.group_name}
                      className="px-4 py-2 bg-builders-600 text-white rounded-md hover:bg-builders-700 disabled:opacity-50"
                    >
                      Create Group
                    </button>
                  </div>
                </div>
              ) : (
                // Manage Existing Group
                <div className="space-y-6">
                  {/* Group Info Header */}
                  <div className="bg-gray-50 p-4 rounded-lg">
                    <h4 className="text-sm font-medium text-gray-900 mb-2">Group Information</h4>
                    <p className="text-sm text-gray-600">{selectedGroup.description}</p>
                    <div className="mt-2 flex items-center text-sm text-gray-500">
                      <UserPlus className="h-4 w-4 mr-1" />
                      <span>{selectedGroup.member_count} members</span>
                      <span className="mx-2">•</span>
                      <span>Created {new Date(selectedGroup.created_at).toLocaleDateString()}</span>
                    </div>
                  </div>

                  {/* Tab Navigation */}
                  <div className="border-b border-gray-200">
                    <nav className="flex space-x-8">
                      <button
                        onClick={() => setActiveGroupTab('members')}
                        className={`py-2 px-1 border-b-2 font-medium text-sm ${
                          activeGroupTab === 'members'
                            ? 'border-builders-500 text-builders-600'
                            : 'border-transparent text-gray-500 hover:text-gray-700'
                        }`}
                      >
                        Members ({groupMembers.length})
                      </button>
                      <button
                        onClick={() => setActiveGroupTab('features')}
                        className={`py-2 px-1 border-b-2 font-medium text-sm ${
                          activeGroupTab === 'features'
                            ? 'border-builders-500 text-builders-600'
                            : 'border-transparent text-gray-500 hover:text-gray-700'
                        }`}
                      >
                        Features ({Object.keys(groupFeatures).filter(k => groupFeatures[k].has_access).length})
                      </button>
                    </nav>
                  </div>

                  {/* Tab Content */}
                  {activeGroupTab === 'members' && (
                    <div className="space-y-4">
                      {/* Add User Section */}
                      <div className="bg-blue-50 p-4 rounded-lg">
                        <h5 className="text-sm font-medium text-blue-900 mb-2">Add Users to Group</h5>
                        <div className="space-y-2 max-h-32 overflow-y-auto">
                          {users.filter(user => 
                            user.user_type !== 'subuser' && 
                            !groupMembers.some(member => member.discord_id === user.discord_id)
                          ).map(user => (
                            <div key={user.discord_id} className="flex items-center justify-between bg-white p-2 rounded">
                              <div className="flex items-center">
                                {user.discord_avatar ? (
                                  <img
                                    className="h-6 w-6 rounded-full mr-2"
                                    src={`https://cdn.discordapp.com/avatars/${user.discord_id}/${user.discord_avatar}.png`}
                                    alt=""
                                  />
                                ) : (
                                  <div className="h-6 w-6 bg-gray-300 rounded-full mr-2"></div>
                                )}
                                <span className="text-sm font-medium">{user.discord_username}</span>
                              </div>
                              <button
                                onClick={() => handleAddUserToGroup(user.discord_id, selectedGroup.group_key)}
                                className="text-xs px-2 py-1 bg-green-100 text-green-700 rounded hover:bg-green-200"
                              >
                                Add
                              </button>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Current Members */}
                      <div>
                        <h5 className="text-sm font-medium text-gray-900 mb-2">Current Members</h5>
                        {groupMembers.length > 0 ? (
                          <div className="space-y-2">
                            {groupMembers.map(member => (
                              <div key={member.discord_id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                                <div className="flex items-center">
                                  <div className="h-8 w-8 bg-gray-300 rounded-full mr-3"></div>
                                  <div>
                                    <div className="text-sm font-medium">{member.discord_username}</div>
                                    <div className="text-xs text-gray-500">{member.email}</div>
                                  </div>
                                </div>
                                <button
                                  onClick={() => handleRemoveUserFromGroup(member.discord_id, selectedGroup.group_key)}
                                  className="text-xs px-2 py-1 bg-red-100 text-red-700 rounded hover:bg-red-200"
                                >
                                  Remove
                                </button>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <p className="text-sm text-gray-500 text-center py-4">No members in this group yet</p>
                        )}
                      </div>
                    </div>
                  )}

                  {activeGroupTab === 'features' && (
                    <div className="space-y-4">
                      <h5 className="text-sm font-medium text-gray-900">Feature Access Control</h5>
                      <div className="space-y-2">
                        {features.map(feature => {
                          const hasAccess = groupFeatures[feature.feature_key]?.has_access || false;
                          return (
                            <div key={feature.feature_key} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                              <div className="flex-1">
                                <div className="text-sm font-medium text-gray-900 flex items-center">
                                  {feature.display_name || feature.feature_key}
                                  {feature.is_beta && (
                                    <span className="ml-2 px-1 py-0.5 text-xs bg-orange-200 text-orange-800 rounded-full">
                                      β
                                    </span>
                                  )}
                                </div>
                                <div className="text-xs text-gray-500">{feature.description}</div>
                              </div>
                              <button
                                onClick={() => handleToggleGroupFeatureAccess(selectedGroup.group_key, feature.feature_key)}
                                className={`px-3 py-1 rounded-md text-xs font-medium ${
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
                  )}
                </div>
              )}
              
              {selectedGroup && (
                <div className="flex justify-end mt-6">
                  <button
                    onClick={() => {
                      setShowGroupModal(false);
                      setSelectedGroup(null);
                    }}
                    className="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700"
                  >
                    Done
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminCompact;