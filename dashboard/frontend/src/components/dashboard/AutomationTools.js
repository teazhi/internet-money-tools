import React, { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { 
  Upload, 
  RefreshCw, 
  Settings as SettingsIcon,
  CheckCircle,
  AlertTriangle,
  Zap,
  FileText,
  Play,
  Activity
} from 'lucide-react';
import axios from 'axios';

const AutomationTools = () => {
  const { user } = useAuth();
  const [loading, setLoading] = useState({
    listingLoader: false,
    prepUploader: false,
    configs: true
  });
  const [message, setMessage] = useState({ type: '', text: '' });
  const [scriptConfigs, setScriptConfigs] = useState(null);

  useEffect(() => {
    fetchScriptConfigs();
  }, []);

  const fetchScriptConfigs = async () => {
    try {
      setLoading(prev => ({ ...prev, configs: true }));
      const response = await axios.get('/api/admin/script-configs', { withCredentials: true });
      setScriptConfigs(response.data);
    } catch (error) {
      console.error('Failed to fetch script configs:', error);
      // Non-admin users might not have access to this endpoint
      if (error.response?.status !== 403) {
        setMessage({ 
          type: 'error', 
          text: 'Failed to load automation status' 
        });
      }
    } finally {
      setLoading(prev => ({ ...prev, configs: false }));
    }
  };

  const triggerScript = async (scriptType) => {
    try {
      setLoading(prev => ({ ...prev, [scriptType]: true }));
      setMessage({ type: '', text: '' });

      const response = await axios.post('/api/admin/trigger-script', 
        { script_type: scriptType }, 
        { withCredentials: true }
      );

      setMessage({ 
        type: 'success', 
        text: `${scriptType === 'listing_loader' ? 'Cost Updater' : 'Prep Uploader'} triggered successfully! Check the execution logs for details.` 
      });


      // Refresh configs after a delay
      setTimeout(() => {
        fetchScriptConfigs();
      }, 2000);

    } catch (error) {
      if (error.response?.status === 403) {
        setMessage({ 
          type: 'error', 
          text: 'You need admin privileges to manually trigger automation tools. Contact your administrator for manual execution.' 
        });
      } else {
        setMessage({ 
          type: 'error', 
          text: error.response?.data?.error || `Failed to trigger ${scriptType === 'listing_loader' ? 'Cost Updater' : 'Prep Uploader'}` 
        });
      }
    } finally {
      setLoading(prev => ({ ...prev, [scriptType]: false }));
    }
  };

  const getLastProcessedDate = (configKey) => {
    const config = scriptConfigs?.[configKey];
    if (!config?.last_processed_date) return 'Never';
    
    return new Date(config.last_processed_date).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      ...(user?.user_record?.timezone && { timeZone: user.user_record.timezone })
    });
  };

  const isAutomationEnabled = (settingKey) => {
    return user?.user_record?.[settingKey] === true;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center space-x-3">
        <Zap className="h-8 w-8 text-builders-500" />
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Automation Tools</h1>
          <p className="text-gray-600">Manage your Cost Updater and Prep Uploader automation</p>
        </div>
      </div>

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
            <AlertTriangle className="h-5 w-5" />
          )}
          <span>{message.text}</span>
        </div>
      )}

      {/* Automation Status Overview */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Cost Updater (Listing Loader) */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-3">
              <div className="h-10 w-10 bg-blue-100 rounded-lg flex items-center justify-center">
                <FileText className="h-5 w-5 text-blue-600" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-gray-900">Cost Updater</h3>
                <p className="text-sm text-gray-500">Amazon Listing Loader & Sellerboard</p>
              </div>
            </div>
            <div className={`px-2 py-1 rounded-full text-xs font-medium ${
              isAutomationEnabled('run_scripts') 
                ? 'bg-green-100 text-green-800' 
                : 'bg-gray-100 text-gray-600'
            }`}>
              {isAutomationEnabled('run_scripts') ? 'Enabled' : 'Disabled'}
            </div>
          </div>

          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">Last Processed:</span>
              <span className="text-sm font-medium">
                {getLastProcessedDate('amznUploadConfig')}
              </span>
            </div>
            
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">Automation:</span>
              <span className={`text-sm font-medium ${
                isAutomationEnabled('run_scripts') ? 'text-green-600' : 'text-gray-600'
              }`}>
                {isAutomationEnabled('run_scripts') ? 'Active' : 'Inactive'}
              </span>
            </div>

            <div className="pt-3 border-t border-gray-200">
              <button
                onClick={() => triggerScript('listing_loader')}
                disabled={loading.listingLoader}
                className="w-full flex items-center justify-center space-x-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading.listingLoader ? (
                  <>
                    <RefreshCw className="h-4 w-4 animate-spin" />
                    <span>Running...</span>
                  </>
                ) : (
                  <>
                    <Play className="h-4 w-4" />
                    <span>Run Now</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Prep Uploader */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-3">
              <div className="h-10 w-10 bg-purple-100 rounded-lg flex items-center justify-center">
                <Upload className="h-5 w-5 text-purple-600" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-gray-900">Prep Uploader</h3>
                <p className="text-sm text-gray-500">Prep Center Sheet Automation</p>
              </div>
            </div>
            <div className={`px-2 py-1 rounded-full text-xs font-medium ${
              isAutomationEnabled('run_prep_center') 
                ? 'bg-green-100 text-green-800' 
                : 'bg-gray-100 text-gray-600'
            }`}>
              {isAutomationEnabled('run_prep_center') ? 'Enabled' : 'Disabled'}
            </div>
          </div>

          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">Last Processed:</span>
              <span className="text-sm font-medium">
                {getLastProcessedDate('config')}
              </span>
            </div>
            
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">Automation:</span>
              <span className={`text-sm font-medium ${
                isAutomationEnabled('run_prep_center') ? 'text-green-600' : 'text-gray-600'
              }`}>
                {isAutomationEnabled('run_prep_center') ? 'Active' : 'Inactive'}
              </span>
            </div>

            <div className="pt-3 border-t border-gray-200">
              <button
                onClick={() => triggerScript('prep_uploader')}
                disabled={loading.prepUploader}
                className="w-full flex items-center justify-center space-x-2 px-4 py-2 text-sm font-medium text-white bg-purple-600 border border-transparent rounded-md hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading.prepUploader ? (
                  <>
                    <RefreshCw className="h-4 w-4 animate-spin" />
                    <span>Running...</span>
                  </>
                ) : (
                  <>
                    <Play className="h-4 w-4" />
                    <span>Run Now</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Information Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* How It Works */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
          <div className="flex items-start space-x-3">
            <Activity className="h-5 w-5 text-blue-500 mt-0.5" />
            <div>
              <h4 className="text-sm font-medium text-blue-900">Integrated Automation</h4>
              <div className="text-sm text-blue-700 mt-2 space-y-2">
                <p>• <strong>No More Manual Deployments:</strong> Your tools are now integrated directly into the dashboard</p>
                <p>• <strong>Cost Updater:</strong> Automatically updates Amazon listings and processes Sellerboard data</p>
                <p>• <strong>Prep Uploader:</strong> Manages and uploads prep center sheets to keep inventory synchronized</p>
                <p>• <strong>One-Click Execution:</strong> Run tools instantly from this dashboard without zipping or uploading</p>
                <p>• Tools run automatically on schedule when enabled, plus manual trigger capability</p>
              </div>
            </div>
          </div>
        </div>

        {/* Configuration */}
        <div className="bg-green-50 border border-green-200 rounded-lg p-6">
          <div className="flex items-start space-x-3">
            <SettingsIcon className="h-5 w-5 text-green-500 mt-0.5" />
            <div>
              <h4 className="text-sm font-medium text-green-900">Configuration</h4>
              <div className="text-sm text-green-700 mt-2 space-y-2">
                <p>• Enable/disable automation in <a href="/dashboard/settings" className="underline">Settings</a></p>
                <p>• Upload your files through <a href="/dashboard/files" className="underline">File Manager</a></p>
                <p>• Configure sheet connections in <a href="/dashboard/sheet-config" className="underline">Sheet Setup</a></p>
                <p>• Monitor execution status and logs in this dashboard</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Refresh Button */}
      <div className="flex justify-center">
        <button
          onClick={fetchScriptConfigs}
          disabled={loading.configs}
          className="flex items-center space-x-2 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${loading.configs ? 'animate-spin' : ''}`} />
          <span>Refresh Status</span>
        </button>
      </div>
    </div>
  );
};

export default AutomationTools;