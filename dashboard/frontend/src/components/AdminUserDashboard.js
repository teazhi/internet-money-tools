import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { AlertTriangle, ArrowLeft, Eye, User } from 'lucide-react';
import axios from 'axios';
import Dashboard from './Dashboard';
import { useAuth } from '../contexts/AuthContext';

const AdminUserDashboard = () => {
  const { userId } = useParams();
  const navigate = useNavigate();
  const { updateUser, refreshUser } = useAuth();
  const [impersonating, setImpersonating] = useState(false);
  const [targetUser, setTargetUser] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    startImpersonation();
    
    // Cleanup function to stop impersonation when component unmounts
    return () => {
      if (impersonating) {
        stopImpersonation();
      }
    };
  }, [userId]);

  const startImpersonation = async () => {
    try {
      setLoading(true);
      setError('');
      
      const response = await axios.post(`/api/admin/impersonate/${userId}`, {}, { 
        withCredentials: true 
      });
      
      setImpersonating(true);
      setTargetUser(response.data.target_user);
      
      // Force refresh of user data in AuthContext after impersonation starts
      // This ensures the Dashboard component gets the impersonated user's data
      try {
        await refreshUser();
        console.log('Successfully refreshed user data after impersonation');
      } catch (refreshError) {
        console.error('Failed to refresh user data after impersonation:', refreshError);
        // Continue anyway - the impersonation session should still work
      }
      
    } catch (error) {
      console.error('Impersonation failed:', error);
      setError(error.response?.data?.error || 'Failed to start impersonation');
      // Redirect back to admin panel on error
      setTimeout(() => navigate('/dashboard/admin'), 2000);
    } finally {
      setLoading(false);
    }
  };

  const stopImpersonation = async () => {
    try {
      await axios.post('/api/admin/stop-impersonate', {}, { 
        withCredentials: true 
      });
      
      setImpersonating(false);
      setTargetUser(null);
      
      // Navigate back to admin panel
      navigate('/dashboard/admin');
      
    } catch (error) {
      console.error('Failed to stop impersonation:', error);
      // Force navigate back even if API call fails
      navigate('/dashboard/admin');
    }
  };

  const handleReturnToAdmin = () => {
    stopImpersonation();
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-builders-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Starting user impersonation...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="bg-white rounded-lg shadow p-6 max-w-md w-full mx-4">
          <div className="flex items-center space-x-3 mb-4">
            <AlertTriangle className="h-8 w-8 text-red-500" />
            <h3 className="text-lg font-medium text-gray-900">Impersonation Failed</h3>
          </div>
          <p className="text-gray-600 mb-4">{error}</p>
          <button
            onClick={() => navigate('/dashboard/admin')}
            className="w-full bg-builders-600 text-white px-4 py-2 rounded-md hover:bg-builders-700 transition-colors"
          >
            Return to Admin Panel
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Admin Impersonation Banner */}
      <div className="bg-yellow-100 border-b border-yellow-200 px-4 py-3">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <Eye className="h-5 w-5 text-yellow-600" />
            <div>
              <p className="text-sm font-medium text-yellow-800">
                Admin View: Viewing as {targetUser?.discord_username || 'Unknown User'}
              </p>
              <p className="text-xs text-yellow-700">
                You are seeing this user's dashboard exactly as they would see it
              </p>
            </div>
          </div>
          <button
            onClick={handleReturnToAdmin}
            className="inline-flex items-center px-3 py-1 border border-yellow-300 rounded-md text-sm font-medium text-yellow-800 bg-yellow-50 hover:bg-yellow-100 transition-colors"
          >
            <ArrowLeft className="h-4 w-4 mr-1" />
            Return to Admin
          </button>
        </div>
      </div>

      {/* User's Dashboard */}
      <Dashboard />
    </div>
  );
};

export default AdminUserDashboard;