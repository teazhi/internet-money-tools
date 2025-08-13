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
  Download
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

  useEffect(() => {
    fetchDiagnostics();
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

      await axios.post('/api/admin/deploy-lambda', formData, {
        withCredentials: true,
        headers: {
          'Content-Type': 'multipart/form-data',
        }
      });

      setMessage({ 
        type: 'success', 
        text: `${deploymentType === 'costUpdater' ? 'Cost Updater' : 'Prep Uploader'} deployed successfully! Function updated with ${deployment.files.length} files.` 
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
                <p className="text-xs text-gray-500 mt-1">
                  {deployments.costUpdater.files.length} file(s) selected
                </p>
              )}
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
            </div>
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
                <p className="text-xs text-gray-500 mt-1">
                  {deployments.prepUploader.files.length} file(s) selected
                </p>
              )}
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
            </div>
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

      {/* Instructions */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
        <div className="flex items-start space-x-3">
          <Code className="h-5 w-5 text-blue-500 mt-0.5" />
          <div>
            <h4 className="text-sm font-medium text-blue-900">Deployment Instructions</h4>
            <div className="text-sm text-blue-700 mt-2 space-y-2">
              <p>• <strong>Select Multiple Files:</strong> Choose all Python files, dependencies, and config files for your Lambda function</p>
              <p>• <strong>Auto-Zip & Deploy:</strong> Files are automatically zipped and deployed to the Lambda function</p>
              <p>• <strong>Download Current:</strong> Use the download button to get the current deployed code</p>
              <p>• <strong>No Manual Zipping:</strong> The system handles packaging and deployment automatically</p>
              <p>• <strong>Instant Updates:</strong> Changes are live immediately after successful deployment</p>
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
    </div>
  );
};

export default LambdaDeployment;