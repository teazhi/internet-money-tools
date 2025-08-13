import React, { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { 
  Upload, 
  RefreshCw, 
  CheckCircle,
  AlertTriangle,
  Zap,
  FileText,
  Package,
  Code,
  Activity,
  Download,
  Database,
  Play,
  Settings,
  X,
  Eye,
  EyeOff
} from 'lucide-react';
import axios from 'axios';

const LambdaDeployment = () => {
  const { user } = useAuth();
  const [loading, setLoading] = useState({
    costUpdater: false,
    prepUploader: false,
    diagnostics: true
  });
  const [message, setMessage] = useState({ type: '', text: '' });
  const [deployments, setDeployments] = useState({
    costUpdater: { files: null, uploading: false },
    prepUploader: { files: null, uploading: false }
  });
  const [lambdaDiagnostics, setLambdaDiagnostics] = useState(null);
  const [analysis, setAnalysis] = useState({
    costUpdater: null,
    prepUploader: null
  });
  const [analyzingFunction, setAnalyzingFunction] = useState(null);
  const [extractingRequirements, setExtractingRequirements] = useState(null);
  const [extractedRequirements, setExtractedRequirements] = useState({
    costUpdater: null,
    prepUploader: null
  });
  const [deploymentMode, setDeploymentMode] = useState({
    costUpdater: 'auto', // 'auto', 'manual', 'smart'
    prepUploader: 'auto'
  });
  const [scriptConfigs, setScriptConfigs] = useState({});
  const [scriptModalOpen, setScriptModalOpen] = useState(false);
  const [editingConfigs, setEditingConfigs] = useState({});
  const [savingConfigs, setSavingConfigs] = useState(false);
  const [runningScript, setRunningScript] = useState(null);
  const [logs, setLogs] = useState({
    costUpdater: [],
    prepUploader: []
  });
  const [loadingLogs, setLoadingLogs] = useState({
    costUpdater: false,
    prepUploader: false
  });
  const [showLogs, setShowLogs] = useState({
    costUpdater: false,
    prepUploader: false
  });

  useEffect(() => {
    fetchDiagnostics();
    fetchScriptConfigs();
  }, []);

  const fetchDiagnostics = async () => {
    try {
      setLoading(prev => ({ ...prev, diagnostics: true }));
      const response = await axios.get('/api/admin/lambda-diagnostics', { withCredentials: true });
      setLambdaDiagnostics(response.data);
    } catch (error) {
      console.error('Failed to fetch diagnostics:', error);
      setMessage({ 
        type: 'error', 
        text: 'Failed to load Lambda diagnostics' 
      });
    } finally {
      setLoading(prev => ({ ...prev, diagnostics: false }));
    }
  };

  const fetchScriptConfigs = async () => {
    try {
      const response = await axios.get('/api/admin/script-configs', { withCredentials: true });
      setScriptConfigs(response.data);
      setEditingConfigs(response.data);
    } catch (error) {
      console.error('Failed to fetch script configs:', error);
    }
  };

  const fetchLogs = async (deploymentType) => {
    const functionName = deploymentType === 'costUpdater' ? 'cost_updater' : 'prep_uploader';
    
    setLoadingLogs(prev => ({ ...prev, [deploymentType]: true }));
    try {
      const response = await axios.get(`/api/admin/lambda-logs?function=${functionName}&hours=24`, {
        withCredentials: true
      });
      
      setLogs(prev => ({
        ...prev,
        [deploymentType]: response.data.logs || []
      }));
    } catch (error) {
      console.error(`Failed to fetch logs for ${deploymentType}:`, error);
      setMessage({
        type: 'error',
        text: `Failed to fetch logs: ${error.response?.data?.error || error.message}`
      });
    } finally {
      setLoadingLogs(prev => ({ ...prev, [deploymentType]: false }));
    }
  };

  const toggleLogs = (deploymentType) => {
    const currentlyShown = showLogs[deploymentType];
    setShowLogs(prev => ({
      ...prev,
      [deploymentType]: !currentlyShown
    }));

    // If showing logs for the first time, fetch them
    if (!currentlyShown && logs[deploymentType].length === 0) {
      fetchLogs(deploymentType);
    }
  };

  const downloadLogs = (deploymentType) => {
    const functionLogs = logs[deploymentType];
    if (!functionLogs || functionLogs.length === 0) {
      setMessage({
        type: 'error',
        text: 'No logs available to download'
      });
      return;
    }

    const functionName = deploymentType === 'costUpdater' ? 'Cost Updater' : 'Prep Uploader';
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    
    // Format logs for download
    const logContent = functionLogs.map(log => 
      `[${new Date(log.timestamp).toISOString()}] ${log.message}`
    ).join('\n');
    
    const blob = new Blob([logContent], { type: 'text/plain' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `${deploymentType}-logs-${timestamp}.txt`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);

    setMessage({
      type: 'success',
      text: `${functionName} logs downloaded successfully`
    });
  };

  const handleFileSelection = (deploymentType, event) => {
    const files = Array.from(event.target.files);
    setDeployments(prev => ({
      ...prev,
      [deploymentType]: { ...prev[deploymentType], files }
    }));
    setMessage({ type: '', text: '' });
  };

  const deployToLambda = async (deploymentType) => {
    const deployment = deployments[deploymentType];
    if (!deployment.files || deployment.files.length === 0) {
      setMessage({ 
        type: 'error', 
        text: 'Please select files to deploy first' 
      });
      return;
    }

    try {
      setLoading(prev => ({ ...prev, [deploymentType]: true }));
      setMessage({ type: '', text: '' });

      // Check if requirements.txt is included
      const hasRequirements = Array.from(deployment.files).some(file => file.name === 'requirements.txt');
      const mode = deploymentMode[deploymentType];

      // Create FormData for file upload
      const formData = new FormData();
      
      // Add all selected files
      deployment.files.forEach((file, index) => {
        formData.append(`files`, file);
      });
      
      formData.append('deployment_type', deploymentType);
      formData.append('lambda_name', deploymentType === 'costUpdater' 
        ? lambdaDiagnostics?.cost_updater_lambda_name || 'amznAndSBUpload'
        : lambdaDiagnostics?.prep_uploader_lambda_name || 'prepUploader'
      );

      // Use smart deployment if requirements.txt detected or mode is set to smart
      const useSmartDeployment = hasRequirements || mode === 'smart';
      const endpoint = useSmartDeployment ? '/api/admin/deploy-lambda-smart' : '/api/admin/deploy-lambda';

      const response = await axios.post(endpoint, formData, {
        withCredentials: true,
        headers: {
          'Content-Type': 'multipart/form-data',
        }
      });

      let successMessage = `${deploymentType === 'costUpdater' ? 'Cost Updater' : 'Prep Uploader'} deployed successfully!`;
      
      if (response.data.deployment_info) {
        const info = response.data.deployment_info;
        if (info.deployment_method === 'requirements.txt') {
          successMessage += ` Dependencies installed automatically. Package size: ${info.package_size_mb}MB`;
        } else {
          successMessage += ` ${deployment.files.length} files uploaded.`;
        }
      }

      setMessage({ 
        type: 'success', 
        text: successMessage
      });

      // Clear the file selection
      setDeployments(prev => ({
        ...prev,
        [deploymentType]: { files: null, uploading: false }
      }));

      // Reset file input
      const fileInput = document.getElementById(`${deploymentType}-files`);
      if (fileInput) fileInput.value = '';

    } catch (error) {
      setMessage({ 
        type: 'error', 
        text: error.response?.data?.error || `Failed to deploy ${deploymentType === 'costUpdater' ? 'Cost Updater' : 'Prep Uploader'}` 
      });
    } finally {
      setLoading(prev => ({ ...prev, [deploymentType]: false }));
    }
  };

  const downloadCurrentCode = async (deploymentType) => {
    try {
      const lambdaName = deploymentType === 'costUpdater' 
        ? lambdaDiagnostics?.cost_updater_lambda_name || 'amznAndSBUpload'
        : lambdaDiagnostics?.prep_uploader_lambda_name || 'prepUploader';

      const response = await axios.get(`/api/admin/download-lambda-code/${lambdaName}`, {
        withCredentials: true,
        responseType: 'blob'
      });

      // Create download link
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `${lambdaName}-current-code.zip`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);

    } catch (error) {
      setMessage({ 
        type: 'error', 
        text: `Failed to download current code: ${error.response?.data?.error || error.message}` 
      });
    }
  };

  const analyzeFunction = async (deploymentType) => {
    try {
      setAnalyzingFunction(deploymentType);
      const lambdaName = deploymentType === 'costUpdater' 
        ? lambdaDiagnostics?.cost_updater_lambda_name || 'amznAndSBUpload'
        : lambdaDiagnostics?.prep_uploader_lambda_name || 'prepUploader';

      const response = await axios.get(`/api/admin/analyze-lambda/${lambdaName}`, {
        withCredentials: true
      });

      setAnalysis(prev => ({
        ...prev,
        [deploymentType]: response.data
      }));

    } catch (error) {
      setMessage({ 
        type: 'error', 
        text: `Failed to analyze function: ${error.response?.data?.error || error.message}` 
      });
    } finally {
      setAnalyzingFunction(null);
    }
  };

  const extractRequirements = async (deploymentType) => {
    try {
      setExtractingRequirements(deploymentType);
      const lambdaName = deploymentType === 'costUpdater' 
        ? lambdaDiagnostics?.cost_updater_lambda_name || 'amznAndSBUpload'
        : lambdaDiagnostics?.prep_uploader_lambda_name || 'prepUploader';

      const response = await axios.get(`/api/admin/extract-requirements/${lambdaName}`, {
        withCredentials: true
      });

      setExtractedRequirements(prev => ({
        ...prev,
        [deploymentType]: response.data
      }));

      setMessage({ 
        type: 'success', 
        text: `Extracted ${response.data.package_count} dependencies from ${deploymentType === 'costUpdater' ? 'Cost Updater' : 'Prep Uploader'}` 
      });

    } catch (error) {
      setMessage({ 
        type: 'error', 
        text: `Failed to extract requirements: ${error.response?.data?.error || error.message}` 
      });
    } finally {
      setExtractingRequirements(null);
    }
  };

  const downloadRequirementsTxt = (deploymentType) => {
    const extracted = extractedRequirements[deploymentType];
    if (!extracted) return;

    const blob = new Blob([extracted.requirements_txt], { type: 'text/plain' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `${deploymentType}-requirements.txt`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  };

  const handleSaveScriptConfigs = async () => {
    setSavingConfigs(true);
    try {
      await axios.post('/api/admin/script-configs', editingConfigs, { withCredentials: true });
      setScriptConfigs(editingConfigs);
      setMessage({ 
        type: 'success', 
        text: 'Script configurations updated successfully!' 
      });
      setScriptModalOpen(false);
    } catch (error) {
      setMessage({ 
        type: 'error', 
        text: 'Failed to save script configurations' 
      });
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

  const handleRunScript = async (scriptType) => {
    setRunningScript(scriptType);
    try {
      const scriptName = scriptType === 'costUpdater' ? 'listing_loader' : 'prep_uploader';
      
      const response = await axios.post('/api/admin/trigger-script', {
        script_type: scriptName
      }, { withCredentials: true });
      
      setMessage({ 
        type: 'success', 
        text: `${scriptType === 'costUpdater' ? 'Listing Loader' : 'Prep Uploader'} script started successfully!` 
      });
      
      // Refresh configs after running and show logs
      setTimeout(() => {
        fetchScriptConfigs();
        fetchLogs(scriptType);
        setShowLogs(prev => ({ ...prev, [scriptType]: true }));
      }, 2000);
    } catch (error) {
      setMessage({ 
        type: 'error', 
        text: `Failed to run script: ${error.response?.data?.error || error.message}` 
      });
    } finally {
      setRunningScript(null);
    }
  };

  // If not admin, show access denied
  if (!user?.is_admin) {
    return (
      <div className="space-y-6">
        <div className="bg-red-50 border border-red-200 rounded-lg p-6">
          <div className="flex items-center space-x-3">
            <AlertTriangle className="h-8 w-8 text-red-500" />
            <div>
              <h3 className="text-lg font-medium text-red-900">Admin Access Required</h3>
              <p className="text-red-700 mt-1">
                This Lambda deployment interface is restricted to admin users only.
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center space-x-3">
        <Zap className="h-8 w-8 text-builders-500" />
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Lambda Deployment</h1>
          <p className="text-gray-600">Deploy code updates to Cost Updater and Prep Uploader Lambda functions</p>
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

      {/* Lambda Diagnostics */}
      {loading.diagnostics ? (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <div className="animate-pulse space-y-4">
            <div className="h-4 bg-gray-300 rounded w-1/4"></div>
            <div className="space-y-2">
              <div className="h-3 bg-gray-300 rounded w-3/4"></div>
              <div className="h-3 bg-gray-300 rounded w-1/2"></div>
            </div>
          </div>
        </div>
      ) : lambdaDiagnostics && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
            <Activity className="h-5 w-5 mr-2" />
            Lambda Status
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">AWS Connection:</span>
                <span className={`text-sm font-medium ${
                  lambdaDiagnostics.aws_connection === 'success' ? 'text-green-600' : 'text-red-600'
                }`}>
                  {lambdaDiagnostics.aws_connection === 'success' ? 'Connected' : 'Failed'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Cost Updater:</span>
                <span className={`text-sm font-medium ${
                  lambdaDiagnostics.cost_updater_exists ? 'text-green-600' : 'text-red-600'
                }`}>
                  {lambdaDiagnostics.cost_updater_exists ? 'Found' : 'Not Found'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Prep Uploader:</span>
                <span className={`text-sm font-medium ${
                  lambdaDiagnostics.prep_uploader_exists ? 'text-green-600' : 'text-red-600'
                }`}>
                  {lambdaDiagnostics.prep_uploader_exists ? 'Found' : 'Not Found'}
                </span>
              </div>
            </div>
            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Region:</span>
                <span className="text-sm font-medium">{lambdaDiagnostics.aws_region}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Functions Found:</span>
                <span className="text-sm font-medium">{lambdaDiagnostics.lambda_functions_found || 0}</span>
              </div>
            </div>
            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Cost Updater Name:</span>
                <span className="text-sm font-medium font-mono text-gray-800">
                  {lambdaDiagnostics.cost_updater_lambda_name}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Prep Uploader Name:</span>
                <span className="text-sm font-medium font-mono text-gray-800">
                  {lambdaDiagnostics.prep_uploader_lambda_name}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Deployment Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Cost Updater Deployment */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <div className="flex items-center space-x-3 mb-4">
            <div className="h-10 w-10 bg-blue-100 rounded-lg flex items-center justify-center">
              <FileText className="h-5 w-5 text-blue-600" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-gray-900">Cost Updater</h3>
              <p className="text-sm text-gray-500">Deploy code to {lambdaDiagnostics?.cost_updater_lambda_name}</p>
            </div>
          </div>

          <div className="space-y-4">
            {/* Requirements.txt Extraction */}
            <div className="bg-blue-50 border border-blue-200 rounded-md p-3 mb-4">
              <div className="flex items-center justify-between">
                <div>
                  <h5 className="text-sm font-medium text-blue-900">Switch to requirements.txt</h5>
                  <p className="text-xs text-blue-700">Extract dependencies from current deployment</p>
                </div>
                <button
                  onClick={() => extractRequirements('costUpdater')}
                  disabled={extractingRequirements === 'costUpdater'}
                  className="px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                >
                  {extractingRequirements === 'costUpdater' ? 'Extracting...' : 'Extract'}
                </button>
              </div>
              {extractedRequirements.costUpdater && (
                <div className="mt-3 p-2 bg-white rounded border">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-medium text-gray-700">
                      {extractedRequirements.costUpdater.package_count} packages detected
                    </span>
                    <button
                      onClick={() => downloadRequirementsTxt('costUpdater')}
                      className="text-xs text-blue-600 hover:text-blue-800"
                    >
                      Download requirements.txt
                    </button>
                  </div>
                  <div className="text-xs text-gray-600 max-h-20 overflow-y-auto font-mono">
                    {extractedRequirements.costUpdater.detected_packages.slice(0, 5).join('\n')}
                    {extractedRequirements.costUpdater.detected_packages.length > 5 && '\n...'}
                  </div>
                </div>
              )}
            </div>

            {/* File Selection */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Select Files to Deploy
              </label>
              <input
                id="costUpdater-files"
                type="file"
                multiple
                onChange={(e) => handleFileSelection('costUpdater', e)}
                className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-medium file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
              />
              {deployments.costUpdater.files && (
                <div className="mt-2">
                  <p className="text-xs text-gray-500">
                    {deployments.costUpdater.files.length} file(s) selected
                  </p>
                  {Array.from(deployments.costUpdater.files).some(file => file.name === 'requirements.txt') && (
                    <div className="text-xs text-green-600 mt-1 flex items-center">
                      <CheckCircle className="h-3 w-3 mr-1" />
                      requirements.txt detected - Smart deployment will be used
                    </div>
                  )}
                </div>
              )}
              <p className="text-xs text-gray-500 mt-1">
                <strong>Smart deployment:</strong> Include requirements.txt + Python files for automatic dependency installation
              </p>
            </div>

            {/* Actions */}
            <div className="flex space-x-2">
              <button
                onClick={() => deployToLambda('costUpdater')}
                disabled={loading.costUpdater || !deployments.costUpdater.files}
                className="flex-1 flex items-center justify-center space-x-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading.costUpdater ? (
                  <>
                    <RefreshCw className="h-4 w-4 animate-spin" />
                    <span>Deploying...</span>
                  </>
                ) : (
                  <>
                    <Upload className="h-4 w-4" />
                    <span>Deploy</span>
                  </>
                )}
              </button>
              <button
                onClick={() => downloadCurrentCode('costUpdater')}
                className="px-3 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
                title="Download current code"
              >
                <Download className="h-4 w-4" />
              </button>
              <button
                onClick={() => analyzeFunction('costUpdater')}
                disabled={analyzingFunction === 'costUpdater'}
                className="px-3 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
                title="Analyze current structure"
              >
                {analyzingFunction === 'costUpdater' ? (
                  <RefreshCw className="h-4 w-4 animate-spin" />
                ) : (
                  <Activity className="h-4 w-4" />
                )}
              </button>
              <button
                onClick={() => toggleLogs('costUpdater')}
                className="px-3 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
                title="View logs"
              >
                {showLogs.costUpdater ? (
                  <EyeOff className="h-4 w-4" />
                ) : (
                  <Eye className="h-4 w-4" />
                )}
              </button>
            </div>

            {/* Logs Section */}
            {showLogs.costUpdater && (
              <div className="mt-4 border-t pt-4">
                <div className="flex items-center justify-between mb-2">
                  <h5 className="text-sm font-medium text-gray-900">Recent Logs (24h)</h5>
                  <div className="flex space-x-2">
                    <button
                      onClick={() => downloadLogs('costUpdater')}
                      disabled={logs.costUpdater.length === 0}
                      className="text-xs text-blue-600 hover:text-blue-800 disabled:opacity-50 disabled:text-gray-400"
                    >
                      Download
                    </button>
                    <button
                      onClick={() => fetchLogs('costUpdater')}
                      disabled={loadingLogs.costUpdater}
                      className="text-xs text-gray-600 hover:text-gray-800 disabled:opacity-50"
                    >
                      {loadingLogs.costUpdater ? 'Refreshing...' : 'Refresh'}
                    </button>
                  </div>
                </div>
                <div className="bg-black text-green-400 p-3 rounded-md text-xs font-mono max-h-60 overflow-y-auto">
                  {loadingLogs.costUpdater ? (
                    <div>Loading logs...</div>
                  ) : logs.costUpdater.length > 0 ? (
                    logs.costUpdater.map((log, index) => (
                      <div key={index} className="mb-1">
                        <span className="text-gray-500">[{new Date(log.timestamp).toLocaleString()}]</span> {log.message}
                      </div>
                    ))
                  ) : (
                    <div className="text-gray-500">No logs found in the last 24 hours</div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Prep Uploader Deployment */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <div className="flex items-center space-x-3 mb-4">
            <div className="h-10 w-10 bg-purple-100 rounded-lg flex items-center justify-center">
              <Package className="h-5 w-5 text-purple-600" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-gray-900">Prep Uploader</h3>
              <p className="text-sm text-gray-500">Deploy code to {lambdaDiagnostics?.prep_uploader_lambda_name}</p>
            </div>
          </div>

          <div className="space-y-4">
            {/* Requirements.txt Extraction */}
            <div className="bg-purple-50 border border-purple-200 rounded-md p-3 mb-4">
              <div className="flex items-center justify-between">
                <div>
                  <h5 className="text-sm font-medium text-purple-900">Switch to requirements.txt</h5>
                  <p className="text-xs text-purple-700">Extract dependencies from current deployment</p>
                </div>
                <button
                  onClick={() => extractRequirements('prepUploader')}
                  disabled={extractingRequirements === 'prepUploader'}
                  className="px-3 py-1 text-xs bg-purple-600 text-white rounded hover:bg-purple-700 disabled:opacity-50"
                >
                  {extractingRequirements === 'prepUploader' ? 'Extracting...' : 'Extract'}
                </button>
              </div>
              {extractedRequirements.prepUploader && (
                <div className="mt-3 p-2 bg-white rounded border">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-medium text-gray-700">
                      {extractedRequirements.prepUploader.package_count} packages detected
                    </span>
                    <button
                      onClick={() => downloadRequirementsTxt('prepUploader')}
                      className="text-xs text-purple-600 hover:text-purple-800"
                    >
                      Download requirements.txt
                    </button>
                  </div>
                  <div className="text-xs text-gray-600 max-h-20 overflow-y-auto font-mono">
                    {extractedRequirements.prepUploader.detected_packages.slice(0, 5).join('\n')}
                    {extractedRequirements.prepUploader.detected_packages.length > 5 && '\n...'}
                  </div>
                </div>
              )}
            </div>

            {/* File Selection */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Select Files to Deploy
              </label>
              <input
                id="prepUploader-files"
                type="file"
                multiple
                onChange={(e) => handleFileSelection('prepUploader', e)}
                className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-medium file:bg-purple-50 file:text-purple-700 hover:file:bg-purple-100"
              />
              {deployments.prepUploader.files && (
                <div className="mt-2">
                  <p className="text-xs text-gray-500">
                    {deployments.prepUploader.files.length} file(s) selected
                  </p>
                  {Array.from(deployments.prepUploader.files).some(file => file.name === 'requirements.txt') && (
                    <div className="text-xs text-green-600 mt-1 flex items-center">
                      <CheckCircle className="h-3 w-3 mr-1" />
                      requirements.txt detected - Smart deployment will be used
                    </div>
                  )}
                </div>
              )}
              <p className="text-xs text-gray-500 mt-1">
                <strong>Smart deployment:</strong> Include requirements.txt + Python files for automatic dependency installation
              </p>
            </div>

            {/* Actions */}
            <div className="flex space-x-2">
              <button
                onClick={() => deployToLambda('prepUploader')}
                disabled={loading.prepUploader || !deployments.prepUploader.files}
                className="flex-1 flex items-center justify-center space-x-2 px-4 py-2 text-sm font-medium text-white bg-purple-600 border border-transparent rounded-md hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading.prepUploader ? (
                  <>
                    <RefreshCw className="h-4 w-4 animate-spin" />
                    <span>Deploying...</span>
                  </>
                ) : (
                  <>
                    <Upload className="h-4 w-4" />
                    <span>Deploy</span>
                  </>
                )}
              </button>
              <button
                onClick={() => downloadCurrentCode('prepUploader')}
                className="px-3 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
                title="Download current code"
              >
                <Download className="h-4 w-4" />
              </button>
              <button
                onClick={() => analyzeFunction('prepUploader')}
                disabled={analyzingFunction === 'prepUploader'}
                className="px-3 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
                title="Analyze current structure"
              >
                {analyzingFunction === 'prepUploader' ? (
                  <RefreshCw className="h-4 w-4 animate-spin" />
                ) : (
                  <Activity className="h-4 w-4" />
                )}
              </button>
              <button
                onClick={() => toggleLogs('prepUploader')}
                className="px-3 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
                title="View logs"
              >
                {showLogs.prepUploader ? (
                  <EyeOff className="h-4 w-4" />
                ) : (
                  <Eye className="h-4 w-4" />
                )}
              </button>
            </div>

            {/* Logs Section */}
            {showLogs.prepUploader && (
              <div className="mt-4 border-t pt-4">
                <div className="flex items-center justify-between mb-2">
                  <h5 className="text-sm font-medium text-gray-900">Recent Logs (24h)</h5>
                  <div className="flex space-x-2">
                    <button
                      onClick={() => downloadLogs('prepUploader')}
                      disabled={logs.prepUploader.length === 0}
                      className="text-xs text-blue-600 hover:text-blue-800 disabled:opacity-50 disabled:text-gray-400"
                    >
                      Download
                    </button>
                    <button
                      onClick={() => fetchLogs('prepUploader')}
                      disabled={loadingLogs.prepUploader}
                      className="text-xs text-gray-600 hover:text-gray-800 disabled:opacity-50"
                    >
                      {loadingLogs.prepUploader ? 'Refreshing...' : 'Refresh'}
                    </button>
                  </div>
                </div>
                <div className="bg-black text-green-400 p-3 rounded-md text-xs font-mono max-h-60 overflow-y-auto">
                  {loadingLogs.prepUploader ? (
                    <div>Loading logs...</div>
                  ) : logs.prepUploader.length > 0 ? (
                    logs.prepUploader.map((log, index) => (
                      <div key={index} className="mb-1">
                        <span className="text-gray-500">[{new Date(log.timestamp).toLocaleString()}]</span> {log.message}
                      </div>
                    ))
                  ) : (
                    <div className="text-gray-500">No logs found in the last 24 hours</div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Analysis Results */}
      {(analysis.costUpdater || analysis.prepUploader) && (
        <div className="space-y-6">
          <h3 className="text-lg font-semibold text-gray-900">Current Lambda Structure Analysis</h3>
          
          {analysis.costUpdater && (
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
              <div className="flex items-center space-x-3 mb-4">
                <div className="h-8 w-8 bg-blue-100 rounded-lg flex items-center justify-center">
                  <FileText className="h-4 w-4 text-blue-600" />
                </div>
                <div>
                  <h4 className="font-semibold text-gray-900">Cost Updater Analysis</h4>
                  <p className="text-sm text-gray-500">
                    {analysis.costUpdater.runtime} • {(analysis.costUpdater.code_size / 1024 / 1024).toFixed(2)} MB
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                <div className="bg-gray-50 p-3 rounded-md">
                  <div className="text-sm font-medium text-gray-900">Python Files</div>
                  <div className="text-2xl font-bold text-blue-600">{analysis.costUpdater.python_files?.length || 0}</div>
                  {analysis.costUpdater.python_files?.length > 0 && (
                    <div className="text-xs text-gray-500 mt-1">
                      {analysis.costUpdater.python_files.slice(0, 3).join(', ')}
                      {analysis.costUpdater.python_files.length > 3 && '...'}
                    </div>
                  )}
                </div>
                <div className="bg-gray-50 p-3 rounded-md">
                  <div className="text-sm font-medium text-gray-900">Dependencies</div>
                  <div className="text-2xl font-bold text-purple-600">{analysis.costUpdater.package_directories?.length || 0}</div>
                  {analysis.costUpdater.package_directories?.length > 0 && (
                    <div className="text-xs text-gray-500 mt-1">
                      {analysis.costUpdater.package_directories.slice(0, 3).join(', ')}
                      {analysis.costUpdater.package_directories.length > 3 && '...'}
                    </div>
                  )}
                </div>
                <div className="bg-gray-50 p-3 rounded-md">
                  <div className="text-sm font-medium text-gray-900">Total Files</div>
                  <div className="text-2xl font-bold text-gray-600">{analysis.costUpdater.files?.length || 0}</div>
                  <div className={`text-xs mt-1 ${analysis.costUpdater.has_requirements_txt ? 'text-green-600' : 'text-red-600'}`}>
                    {analysis.costUpdater.has_requirements_txt ? '✓ Has requirements.txt' : '✗ No requirements.txt'}
                  </div>
                </div>
              </div>

              {analysis.costUpdater.has_requirements_txt && analysis.costUpdater.requirements_content && (
                <div className="bg-blue-50 border border-blue-200 rounded-md p-3">
                  <div className="text-sm font-medium text-blue-900 mb-2">Requirements.txt Contents:</div>
                  <div className="text-xs font-mono text-blue-800 space-y-1">
                    {analysis.costUpdater.requirements_content.map((req, idx) => (
                      <div key={idx}>{req}</div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {analysis.prepUploader && (
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
              <div className="flex items-center space-x-3 mb-4">
                <div className="h-8 w-8 bg-purple-100 rounded-lg flex items-center justify-center">
                  <Package className="h-4 w-4 text-purple-600" />
                </div>
                <div>
                  <h4 className="font-semibold text-gray-900">Prep Uploader Analysis</h4>
                  <p className="text-sm text-gray-500">
                    {analysis.prepUploader.runtime} • {(analysis.prepUploader.code_size / 1024 / 1024).toFixed(2)} MB
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                <div className="bg-gray-50 p-3 rounded-md">
                  <div className="text-sm font-medium text-gray-900">Python Files</div>
                  <div className="text-2xl font-bold text-blue-600">{analysis.prepUploader.python_files?.length || 0}</div>
                  {analysis.prepUploader.python_files?.length > 0 && (
                    <div className="text-xs text-gray-500 mt-1">
                      {analysis.prepUploader.python_files.slice(0, 3).join(', ')}
                      {analysis.prepUploader.python_files.length > 3 && '...'}
                    </div>
                  )}
                </div>
                <div className="bg-gray-50 p-3 rounded-md">
                  <div className="text-sm font-medium text-gray-900">Dependencies</div>
                  <div className="text-2xl font-bold text-purple-600">{analysis.prepUploader.package_directories?.length || 0}</div>
                  {analysis.prepUploader.package_directories?.length > 0 && (
                    <div className="text-xs text-gray-500 mt-1">
                      {analysis.prepUploader.package_directories.slice(0, 3).join(', ')}
                      {analysis.prepUploader.package_directories.length > 3 && '...'}
                    </div>
                  )}
                </div>
                <div className="bg-gray-50 p-3 rounded-md">
                  <div className="text-sm font-medium text-gray-900">Total Files</div>
                  <div className="text-2xl font-bold text-gray-600">{analysis.prepUploader.files?.length || 0}</div>
                  <div className={`text-xs mt-1 ${analysis.prepUploader.has_requirements_txt ? 'text-green-600' : 'text-red-600'}`}>
                    {analysis.prepUploader.has_requirements_txt ? '✓ Has requirements.txt' : '✗ No requirements.txt'}
                  </div>
                </div>
              </div>

              {analysis.prepUploader.has_requirements_txt && analysis.prepUploader.requirements_content && (
                <div className="bg-purple-50 border border-purple-200 rounded-md p-3">
                  <div className="text-sm font-medium text-purple-900 mb-2">Requirements.txt Contents:</div>
                  <div className="text-xs font-mono text-purple-800 space-y-1">
                    {analysis.prepUploader.requirements_content.map((req, idx) => (
                      <div key={idx}>{req}</div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Script Configuration Section */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900 flex items-center">
            <Settings className="h-5 w-5 mr-2" />
            Script Configuration
          </h3>
          <button
            onClick={() => setScriptModalOpen(true)}
            className="flex items-center px-3 py-2 bg-gray-600 text-white rounded-md text-sm hover:bg-gray-700"
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
              <button 
                onClick={() => handleRunScript('costUpdater')}
                disabled={runningScript === 'costUpdater'}
                className="flex items-center px-2 py-1 bg-green-600 text-white rounded text-xs hover:bg-green-700 disabled:opacity-50"
              >
                {runningScript === 'costUpdater' ? (
                  <>
                    <RefreshCw className="h-3 w-3 mr-1 animate-spin" />
                    Running...
                  </>
                ) : (
                  <>
                    <Play className="h-3 w-3 mr-1" />
                    Run
                  </>
                )}
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
              <button 
                onClick={() => handleRunScript('prepUploader')}
                disabled={runningScript === 'prepUploader'}
                className="flex items-center px-2 py-1 bg-blue-600 text-white rounded text-xs hover:bg-blue-700 disabled:opacity-50"
              >
                {runningScript === 'prepUploader' ? (
                  <>
                    <RefreshCw className="h-3 w-3 mr-1 animate-spin" />
                    Running...
                  </>
                ) : (
                  <>
                    <Play className="h-3 w-3 mr-1" />
                    Run
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Instructions */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
        <div className="flex items-start space-x-3">
          <Code className="h-5 w-5 text-blue-500 mt-0.5" />
          <div>
            <h4 className="text-sm font-medium text-blue-900">Smart Lambda Deployment</h4>
            <div className="text-sm text-blue-700 mt-2 space-y-2">
              <p>• <strong>Extract Dependencies:</strong> Click "Extract" to create requirements.txt from your current deployment</p>
              <p>• <strong>Smart Deployment:</strong> Upload requirements.txt + Python files for automatic dependency installation</p>
              <p>• <strong>Manual Deployment:</strong> Upload all files directly (old method still supported)</p>
              <p>• <strong>Smaller Packages:</strong> requirements.txt deployments are much smaller and faster</p>
              <p>• <strong>Version Control:</strong> Easily manage and update specific package versions</p>
              <p>• <strong>Automatic Detection:</strong> System detects requirements.txt and switches to smart deployment</p>
            </div>
          </div>
        </div>
      </div>

      {/* Refresh Button */}
      <div className="flex justify-center">
        <button
          onClick={fetchDiagnostics}
          disabled={loading.diagnostics}
          className="flex items-center space-x-2 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${loading.diagnostics ? 'animate-spin' : ''}`} />
          <span>Refresh Status</span>
        </button>
      </div>

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

export default LambdaDeployment;