import React, { useState, useEffect, useCallback, useMemo } from 'react';
import axios from 'axios';
import { useAuth } from '../../contexts/AuthContext';

const SubUserManager = () => {
  const { user } = useAuth();
  const [subUsers, setSubUsers] = useState([]);
  const [invitations, setInvitations] = useState([]);
  const [availablePermissions, setAvailablePermissions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showInviteForm, setShowInviteForm] = useState(false);
  const [showEditForm, setShowEditForm] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [inviteForm, setInviteForm] = useState({
    email: '',
    va_name: '',
    permissions: []
  });
  const [editForm, setEditForm] = useState({
    va_name: '',
    permissions: []
  });

  const fetchData = useCallback(async () => {
    try {
      const [subUsersResponse, invitationsResponse, permissionsResponse] = await Promise.all([
        axios.get('/api/my-subusers', { withCredentials: true }),
        axios.get('/api/my-invitations', { withCredentials: true }),
        axios.get('/api/available-permissions', { withCredentials: true })
      ]);

      setSubUsers(subUsersResponse.data.subusers || []);
      setInvitations(invitationsResponse.data.invitations || []);
      setAvailablePermissions(permissionsResponse.data.available_permissions || []);
    } catch (error) {
      // Error fetching sub-user data - continue with empty state
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleInviteSubmit = async (e) => {
    e.preventDefault();
    try {
      await axios.post('/api/invite-subuser', inviteForm, { withCredentials: true });
      setInviteForm({ email: '', va_name: '', permissions: [] });
      setShowInviteForm(false);
      fetchData(); // Refresh data
      alert('Invitation sent successfully!');
    } catch (error) {
      alert(error.response?.data?.error || 'Failed to send invitation');
    }
  };

  const handleRevokeAccess = async (subUserId) => {
    if (window.confirm('Are you sure you want to revoke access for this VA?')) {
      try {
        await axios.delete(`/api/revoke-subuser/${subUserId}`, { withCredentials: true });
        fetchData(); // Refresh data
        alert('Access revoked successfully');
      } catch (error) {
        alert(error.response?.data?.error || 'Failed to revoke access');
      }
    }
  };

  const handleRemoveInvitation = async (invitationToken) => {
    if (window.confirm('Are you sure you want to remove this pending invitation?')) {
      try {
        await axios.delete(`/api/my-invitations/${invitationToken}`, { withCredentials: true });
        fetchData(); // Refresh data
        alert('Invitation removed successfully');
      } catch (error) {
        alert(error.response?.data?.error || 'Failed to remove invitation');
      }
    }
  };

  const handlePermissionChange = useCallback((permission) => {
    setInviteForm(prev => ({
      ...prev,
      permissions: prev.permissions.includes(permission)
        ? prev.permissions.filter(p => p !== permission)
        : [...prev.permissions, permission]
    }));
  }, []);

  const handleEditPermissionChange = useCallback((permission) => {
    setEditForm(prev => ({
      ...prev,
      permissions: prev.permissions.includes(permission)
        ? prev.permissions.filter(p => p !== permission)
        : [...prev.permissions, permission]
    }));
  }, []);

  const handleEditUser = (subUser) => {
    setEditingUser(subUser);
    setEditForm({
      va_name: subUser.va_name || '',
      permissions: [...subUser.permissions]
    });
    setShowEditForm(true);
  };

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    try {
      await axios.put(`/api/edit-subuser/${editingUser.discord_id}`, editForm, { withCredentials: true });
      setShowEditForm(false);
      setEditingUser(null);
      setEditForm({ va_name: '', permissions: [] });
      fetchData(); // Refresh data
      alert('VA updated successfully!');
    } catch (error) {
      alert(error.response?.data?.error || 'Failed to update VA');
    }
  };

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    
    // Use user's timezone from their profile if available
    const userTimezone = user?.user_record?.timezone;
    
    const options = {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      ...(userTimezone && { timeZone: userTimezone })
    };
    
    return date.toLocaleDateString('en-US', options);
  };

  if (loading) {
    return (
      <div className="space-y-6">
        {/* Header Skeleton */}
        <div className="flex justify-between items-center">
          <div className="h-8 bg-gray-300 rounded w-64 animate-pulse"></div>
          <div className="h-10 bg-gray-300 rounded w-24 animate-pulse"></div>
        </div>

        {/* Active VAs Card Skeleton */}
        <div className="bg-white rounded-lg shadow">
          <div className="px-6 py-4 border-b border-gray-200">
            <div className="h-6 bg-gray-300 rounded w-32 animate-pulse"></div>
          </div>
          <div className="divide-y divide-gray-200">
            {[1, 2, 3].map(i => (
              <div key={i} className="px-6 py-4 flex items-center justify-between animate-pulse">
                <div className="flex-1">
                  <div className="flex items-center space-x-3">
                    <div>
                      <div className="h-4 bg-gray-300 rounded w-32 mb-2"></div>
                      <div className="h-3 bg-gray-300 rounded w-48 mb-1"></div>
                      <div className="h-3 bg-gray-300 rounded w-40 mb-1"></div>
                      <div className="h-3 bg-gray-300 rounded w-36"></div>
                    </div>
                  </div>
                </div>
                <div className="h-8 bg-gray-300 rounded w-24"></div>
              </div>
            ))}
          </div>
        </div>

        {/* Pending Invitations Card Skeleton */}
        <div className="bg-white rounded-lg shadow">
          <div className="px-6 py-4 border-b border-gray-200">
            <div className="h-6 bg-gray-300 rounded w-40 animate-pulse"></div>
          </div>
          <div className="divide-y divide-gray-200">
            {[1, 2].map(i => (
              <div key={i} className="px-6 py-4 flex items-center justify-between animate-pulse">
                <div className="flex-1">
                  <div className="flex items-center space-x-3">
                    <div>
                      <div className="h-4 bg-gray-300 rounded w-40 mb-2"></div>
                      <div className="h-3 bg-gray-300 rounded w-48 mb-1"></div>
                      <div className="h-3 bg-gray-300 rounded w-32 mb-1"></div>
                      <div className="h-3 bg-gray-300 rounded w-36"></div>
                    </div>
                  </div>
                </div>
                <div className="h-6 bg-gray-300 rounded-full w-16"></div>
              </div>
            ))}
          </div>
        </div>

        {/* Loading indicator */}
        <div className="text-center py-4">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-builders-500 mx-auto mb-2"></div>
          <p className="text-gray-600 text-sm">Loading VA management data...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-bold text-gray-900">VA & Sub-User Management</h2>
        <button
          onClick={() => setShowInviteForm(true)}
          className="btn-primary"
        >
          Invite VA
        </button>
      </div>

      {/* Invite Form Modal */}
      {showInviteForm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="card max-w-md w-full mx-4">
            <h3 className="text-lg font-bold mb-4">Invite Virtual Assistant</h3>
            <form onSubmit={handleInviteSubmit}>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Email Address *
                  </label>
                  <input
                    type="email"
                    required
                    value={inviteForm.email}
                    onChange={(e) => setInviteForm(prev => ({ ...prev, email: e.target.value }))}
                    className="input-field"
                    placeholder="va@example.com"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    VA Name (Optional)
                  </label>
                  <input
                    type="text"
                    value={inviteForm.va_name}
                    onChange={(e) => setInviteForm(prev => ({ ...prev, va_name: e.target.value }))}
                    className="input-field"
                    placeholder="Assistant Name"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Permissions
                  </label>
                  <div className="space-y-2">
                    {availablePermissions.map((permission) => (
                      <label key={permission.key} className="flex items-center">
                        <input
                          type="checkbox"
                          checked={inviteForm.permissions.includes(permission.key)}
                          onChange={() => handlePermissionChange(permission.key)}
                          className="mr-2"
                        />
                        <span className="text-sm">
                          {permission.name}
                          {permission.is_beta && <span className="ml-1 text-xs bg-blue-100 text-blue-800 px-1 rounded">BETA</span>}
                        </span>
                      </label>
                    ))}
                    <label className="flex items-center">
                      <input
                        type="checkbox"
                        checked={inviteForm.permissions.includes('all')}
                        onChange={() => handlePermissionChange('all')}
                        className="mr-2"
                      />
                      <span className="text-sm">Full Dashboard Access (All Permissions)</span>
                    </label>
                  </div>
                </div>
              </div>

              <div className="flex justify-end space-x-3 mt-6">
                <button
                  type="button"
                  onClick={() => setShowInviteForm(false)}
                  className="px-4 py-2 text-gray-600 hover:text-gray-800"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn-primary"
                >
                  Send Invitation
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit VA Form Modal */}
      {showEditForm && editingUser && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="card max-w-md w-full mx-4">
            <h3 className="text-lg font-bold mb-4">Edit Virtual Assistant</h3>
            <form onSubmit={handleEditSubmit}>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Email Address
                  </label>
                  <input
                    type="email"
                    disabled
                    value={editingUser.email}
                    className="input-field bg-gray-100 cursor-not-allowed"
                  />
                  <p className="text-xs text-gray-500 mt-1">Email cannot be changed</p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    VA Name
                  </label>
                  <input
                    type="text"
                    value={editForm.va_name}
                    onChange={(e) => setEditForm(prev => ({ ...prev, va_name: e.target.value }))}
                    className="input-field"
                    placeholder="Assistant Name"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Permissions
                  </label>
                  <div className="space-y-2">
                    {availablePermissions.map((permission) => (
                      <label key={permission.key} className="flex items-center">
                        <input
                          type="checkbox"
                          checked={editForm.permissions.includes(permission.key)}
                          onChange={() => handleEditPermissionChange(permission.key)}
                          className="mr-2"
                        />
                        <span className="text-sm">
                          {permission.name}
                          {permission.is_beta && <span className="ml-1 text-xs bg-blue-100 text-blue-800 px-1 rounded">BETA</span>}
                        </span>
                      </label>
                    ))}
                    <label className="flex items-center">
                      <input
                        type="checkbox"
                        checked={editForm.permissions.includes('all')}
                        onChange={() => handleEditPermissionChange('all')}
                        className="mr-2"
                      />
                      <span className="text-sm">Full Dashboard Access (All Permissions)</span>
                    </label>
                  </div>
                </div>
              </div>

              <div className="flex justify-end space-x-3 mt-6">
                <button
                  type="button"
                  onClick={() => {
                    setShowEditForm(false);
                    setEditingUser(null);
                    setEditForm({ va_name: '', permissions: [] });
                  }}
                  className="px-4 py-2 text-gray-600 hover:text-gray-800"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn-primary"
                >
                  Save Changes
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Active Sub-Users */}
      <div className="card !p-0">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-base font-medium text-gray-900">Active VAs ({subUsers.length})</h3>
        </div>
        <div className="divide-y divide-gray-200">
          {subUsers.length === 0 ? (
            <p className="px-6 py-4 text-gray-500">No active VAs yet. Invite one to get started!</p>
          ) : (
            subUsers.map((subUser) => (
              <div key={subUser.discord_id} className="px-6 py-4 flex items-center justify-between">
                <div className="flex-1">
                  <div className="flex items-center space-x-3">
                    <div>
                      <p className="font-medium text-gray-900">
                        {subUser.va_name || subUser.discord_username || 'Unknown'}
                      </p>
                      <p className="text-sm text-gray-500">{subUser.email}</p>
                      <p className="text-xs text-gray-400">
                        Permissions: {subUser.permissions.join(', ')}
                      </p>
                      {subUser.last_activity && (
                        <p className="text-xs text-gray-400">
                          Last activity: {formatDate(subUser.last_activity)}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => handleEditUser(subUser)}
                    className="text-blue-600 hover:text-blue-800 text-sm font-medium px-3 py-1 rounded-md hover:bg-blue-50 transition-colors"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => handleRevokeAccess(subUser.discord_id)}
                    className="text-red-600 hover:text-red-800 text-sm font-medium px-3 py-1 rounded-md hover:bg-red-50 transition-colors"
                  >
                    Revoke Access
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Pending Invitations */}
      <div className="card !p-0">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-base font-medium text-gray-900">Pending Invitations ({invitations.length})</h3>
        </div>
        <div className="divide-y divide-gray-200">
          {invitations.length === 0 ? (
            <p className="px-6 py-4 text-gray-500">No pending invitations.</p>
          ) : (
            invitations.map((invitation) => (
              <div key={invitation.token} className="px-6 py-4 flex items-center justify-between">
                <div className="flex-1">
                  <div className="flex items-center space-x-3">
                    <div>
                      <p className="font-medium text-gray-900">
                        {invitation.va_name || invitation.email}
                      </p>
                      <p className="text-sm text-gray-500">{invitation.email}</p>
                      <p className="text-xs text-gray-400">
                        Sent: {formatDate(invitation.created_at)}
                      </p>
                      <p className="text-xs text-gray-400">
                        Expires: {formatDate(invitation.expires_at)}
                      </p>
                    </div>
                  </div>
                </div>
                <div className="flex items-center space-x-2">
                  <span className="inline-flex items-center px-2 py-1 text-xs font-medium bg-yellow-100 text-yellow-800 rounded-full">
                    {invitation.status}
                  </span>
                  <button
                    onClick={() => handleRemoveInvitation(invitation.token)}
                    className="text-red-600 hover:text-red-800 text-sm font-medium px-3 py-1 rounded-md hover:bg-red-50 transition-colors"
                  >
                    Remove
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};

export default SubUserManager;