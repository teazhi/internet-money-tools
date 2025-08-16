import React, { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { 
  Database, 
  ExternalLink, 
  CheckCircle, 
  AlertCircle, 
  Loader, 
  ArrowRight,
  FileSpreadsheet,
  Link as LinkIcon
} from 'lucide-react';
import axios from 'axios';

const SheetConfig = () => {
  const { user, updateUser } = useAuth();
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState({ type: '', text: '' });
  
  // Google linking state
  const [googleAuthUrl, setGoogleAuthUrl] = useState('');
  const [authCode, setAuthCode] = useState('');
  
  // Sheet selection state
  const [spreadsheets, setSpreadsheets] = useState([]);
  const [selectedSpreadsheet, setSelectedSpreadsheet] = useState('');
  const [worksheets, setWorksheets] = useState([]);
  const [selectedWorksheet, setSelectedWorksheet] = useState('');
  
  // Column mapping state
  const [headers, setHeaders] = useState([]);
  const [columnMapping, setColumnMapping] = useState({});
  
  // Configuration display state
  const [configuredSpreadsheetName, setConfiguredSpreadsheetName] = useState('');
  const [hasManuallyNavigated, setHasManuallyNavigated] = useState(false);

  const requiredColumns = [
    'Date', 'Sale Price', 'Name', 'Size/Color', '# Units in Bundle',
    'Amount Purchased', 'ASIN', 'COGS', 'Order #', 'Prep Notes'
  ];

  useEffect(() => {
    if (user?.sheet_configured && user?.user_record) {
      // Load existing configuration and go to step 4 (highest priority)
      loadExistingConfiguration(user.user_record);
      setStep(4);
    } else if (user?.google_linked && !hasManuallyNavigated) {
      // Only auto-advance to step 2 if user hasn't manually navigated
      setStep(2);
      fetchSpreadsheets();
    }
  }, [user, hasManuallyNavigated]);

  const loadExistingConfiguration = async (userRecord) => {
    try {
      // Set the stored configuration data
      if (userRecord.sheet_id) {
        setSelectedSpreadsheet(userRecord.sheet_id);
      }
      if (userRecord.worksheet_title) {
        setSelectedWorksheet(userRecord.worksheet_title);
      }
      if (userRecord.column_mapping) {
        setColumnMapping(userRecord.column_mapping);
      }
      
      // Fetch the spreadsheet name from Google API if we have the ID
      if (userRecord.sheet_id) {
        try {
          const response = await axios.get('/api/google/spreadsheets', { withCredentials: true });
          const spreadsheet = response.data.spreadsheets.find(s => s.id === userRecord.sheet_id);
          if (spreadsheet) {
            setConfiguredSpreadsheetName(spreadsheet.name);
          }
        } catch (error) {
          console.error('Failed to fetch spreadsheet name:', error);
          // Fallback to showing the ID if we can't get the name
          setConfiguredSpreadsheetName(userRecord.sheet_id);
        }
      }
    } catch (error) {
      console.error('Error loading existing configuration:', error);
    }
  };

  const getGoogleAuthUrl = async () => {
    try {
      const response = await axios.get('/api/google/auth-url', { withCredentials: true });
      setGoogleAuthUrl(response.data.auth_url);
    } catch (error) {
      setMessage({ type: 'error', text: 'Failed to get Google authorization URL' });
    }
  };

  const completeGoogleAuth = async () => {
    if (!authCode.trim()) {
      setMessage({ type: 'error', text: 'Please enter the authorization code' });
      return;
    }

    setLoading(true);
    try {
      await axios.post('/api/google/complete-auth', { code: authCode }, { withCredentials: true });
      setMessage({ type: 'success', text: 'Google account linked successfully!' });
      updateUser({ google_linked: true });
      setStep(2);
      fetchSpreadsheets();
    } catch (error) {
      setMessage({ type: 'error', text: error.response?.data?.error || 'Failed to link Google account' });
    } finally {
      setLoading(false);
    }
  };

  const fetchSpreadsheets = async () => {
    setLoading(true);
    try {
      const response = await axios.get('/api/google/spreadsheets', { withCredentials: true });
      setSpreadsheets(response.data.spreadsheets);
    } catch (error) {
      setMessage({ type: 'error', text: 'Failed to fetch spreadsheets' });
    } finally {
      setLoading(false);
    }
  };

  const fetchWorksheets = async (spreadsheetId) => {
    setLoading(true);
    try {
      const response = await axios.get(`/api/google/worksheets/${spreadsheetId}`, { withCredentials: true });
      setWorksheets(response.data.worksheets);
      setStep(3);
    } catch (error) {
      setMessage({ type: 'error', text: 'Failed to fetch worksheets' });
    } finally {
      setLoading(false);
    }
  };

  const autoDetectColumnMapping = (headers) => {
    const mapping = {};
    
    // Define patterns for each required column
    const patterns = {
      'Date': ['date', 'purchase date', 'order date', 'bought', 'purchased'],
      'Sale Price': ['sale price', 'selling price', 'price', 'sell price', 'sale', 'amount'],
      'Name': ['name', 'product name', 'title', 'product title', 'item name', 'description'],
      'Size/Color': ['size', 'color', 'variant', 'size/color', 'variation', 'style'],
      '# Units in Bundle': ['units', 'quantity', 'qty', 'bundle', 'pack size', 'count'],
      'Amount Purchased': ['amount purchased', 'purchase quantity', 'bought quantity', 'purchased qty'],
      'ASIN': ['asin', 'product asin', 'amazon asin'],
      'COGS': ['cogs', 'cost', 'purchase price', 'buy price', 'wholesale', 'cost price'],
      'Order #': ['order', 'order number', 'order #', 'order id', 'purchase order'],
      'Prep Notes': ['prep', 'notes', 'prep notes', 'preparation', 'comment', 'remarks']
    };
    
    // For each required column, find the best matching header
    for (const [requiredCol, searchPatterns] of Object.entries(patterns)) {
      let bestMatch = null;
      let bestScore = 0;
      
      for (const header of headers) {
        const headerLower = header.toLowerCase();
        
        // Check for exact matches first (highest score)
        for (const pattern of searchPatterns) {
          if (headerLower === pattern) {
            bestMatch = header;
            bestScore = 100;
            break;
          }
        }
        
        // If no exact match, check for partial matches
        if (bestScore < 100) {
          for (const pattern of searchPatterns) {
            if (headerLower.includes(pattern)) {
              const score = pattern.length / headerLower.length * 50; // Partial match score
              if (score > bestScore) {
                bestMatch = header;
                bestScore = score;
              }
            }
          }
        }
      }
      
      if (bestMatch && bestScore > 30) { // Only use matches with reasonable confidence
        mapping[requiredCol] = bestMatch;
      }
    }
    
    return mapping;
  };

  const fetchHeaders = async () => {
    if (!selectedSpreadsheet || !selectedWorksheet) return;
    
    setLoading(true);
    try {
      const response = await axios.get(
        `/api/sheet/headers/${selectedSpreadsheet}/${encodeURIComponent(selectedWorksheet)}`,
        { withCredentials: true }
      );
      const fetchedHeaders = response.data.headers;
      setHeaders(fetchedHeaders);
      
      // Auto-detect column mapping (only if not already configured)
      if (Object.keys(columnMapping).length === 0) {
        const detectedMapping = autoDetectColumnMapping(fetchedHeaders);
        setColumnMapping(detectedMapping);
      }
      
      setStep(3.5); // Column mapping step
    } catch (error) {
      setMessage({ type: 'error', text: 'Failed to fetch sheet headers' });
    } finally {
      setLoading(false);
    }
  };

  const saveConfiguration = async () => {
    // Validate all required columns are mapped
    const missingMappings = requiredColumns.filter(col => !columnMapping[col]);
    if (missingMappings.length > 0) {
      setMessage({ 
        type: 'error', 
        text: `Please map all required columns: ${missingMappings.join(', ')}` 
      });
      return;
    }

    setLoading(true);
    try {
      await axios.post('/api/sheet/configure', {
        spreadsheet_id: selectedSpreadsheet,
        worksheet_title: selectedWorksheet,
        column_mapping: columnMapping
      }, { withCredentials: true });
      
      setMessage({ type: 'success', text: 'Sheet configuration saved successfully!' });
      updateUser({ sheet_configured: true });
      setStep(4);
    } catch (error) {
      setMessage({ type: 'error', text: 'Failed to save configuration' });
    } finally {
      setLoading(false);
    }
  };

  const handleDisconnectGoogle = async () => {
    if (!window.confirm('Are you sure you want to disconnect your Google account? This will reset your sheet configuration and require re-authorization with write permissions.')) {
      return;
    }
    setLoading(true);
    try {
      await axios.post('/api/google/disconnect', {}, { withCredentials: true });
      setMessage({ type: 'success', text: 'Google account disconnected successfully!' });
      
      // Update user context and reset to step 1
      updateUser({
        google_linked: false,
        sheet_configured: false
      });
      
      // Reset all state
      setStep(1);
      setSelectedSpreadsheet('');
      setSelectedWorksheet('');
      setColumnMapping({});
      setConfiguredSpreadsheetName('');
      setSpreadsheets([]);
      setWorksheets([]);
      setHeaders([]);
    } catch (error) {
      setMessage({ 
        type: 'error', 
        text: error.response?.data?.error || 'Failed to disconnect Google account' 
      });
    } finally {
      setLoading(false);
    }
  };

  const renderStep1 = () => (
    <div className="card max-w-2xl">
      <div className="text-center mb-6">
        <LinkIcon className="h-12 w-12 text-builders-500 mx-auto mb-4" />
        <h3 className="text-lg font-semibold text-gray-900 mb-2">Link Google Account</h3>
        <p className="text-gray-600">
          Connect your Google account to access your spreadsheets
        </p>
      </div>

      {user?.google_linked ? (
        // Already connected - show status and next button
        <div className="space-y-4">
          <div className="bg-green-50 border border-green-200 rounded-md p-4">
            <div className="flex items-center">
              <CheckCircle className="h-5 w-5 text-green-500 mr-2" />
              <span className="text-sm text-green-800">Google account is already connected</span>
            </div>
          </div>
          <div className="flex space-x-3">
            <button
              onClick={() => {
                setStep(2);
                fetchSpreadsheets();
              }}
              className="btn-primary flex-1"
            >
              Next: Select Spreadsheet
            </button>
            <button
              onClick={handleDisconnectGoogle}
              className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors duration-200"
            >
              Disconnect & Reconnect
            </button>
          </div>
        </div>
      ) : (
        // Not connected - show auth flow
        <>
          {!googleAuthUrl ? (
            <button
              onClick={getGoogleAuthUrl}
              className="btn-primary w-full mb-4"
            >
              Generate Authorization URL
            </button>
          ) : (
            <div className="space-y-4">
              <a
                href={googleAuthUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="btn-primary w-full flex items-center justify-center space-x-2"
              >
                <ExternalLink className="h-4 w-4" />
                <span>Open Google Authorization</span>
              </a>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Authorization Code
                </label>
                <input
                  type="text"
                  value={authCode}
                  onChange={(e) => setAuthCode(e.target.value)}
                  className="input-field mb-4"
                  placeholder="Paste the authorization code here"
                />
                <button
                  onClick={completeGoogleAuth}
                  disabled={loading || !authCode.trim()}
                  className="btn-primary w-full disabled:opacity-50"
                >
                  {loading ? 'Linking...' : 'Complete Authorization'}
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );

  const renderStep2 = () => (
    <div className="card max-w-2xl">
      <div className="text-center mb-6">
        <FileSpreadsheet className="h-12 w-12 text-green-500 mx-auto mb-4" />
        <h3 className="text-lg font-semibold text-gray-900 mb-2">Select Spreadsheet</h3>
        <p className="text-gray-600">
          Choose the Google Sheet containing your purchase data
        </p>
      </div>

      {loading ? (
        <div className="text-center">
          <Loader className="h-8 w-8 animate-spin mx-auto mb-2" />
          <p>Loading spreadsheets...</p>
        </div>
      ) : (
        <div className="space-y-3">
          {spreadsheets.map((sheet) => (
            <button
              key={sheet.id}
              onClick={() => {
                setSelectedSpreadsheet(sheet.id);
                fetchWorksheets(sheet.id);
              }}
              className="w-full text-left p-4 border border-gray-200 rounded-lg hover:border-builders-500 hover:bg-builders-50 transition-colors duration-200"
            >
              <div className="flex items-center justify-between">
                <span className="font-medium text-gray-900">{sheet.name}</span>
                <ArrowRight className="h-4 w-4 text-gray-400" />
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );

  const renderStep3 = () => (
    <div className="card max-w-2xl">
      <div className="text-center mb-6">
        <Database className="h-12 w-12 text-blue-500 mx-auto mb-4" />
        <h3 className="text-lg font-semibold text-gray-900 mb-2">Select Worksheet</h3>
        <p className="text-gray-600">
          Choose the specific tab/worksheet with your data
        </p>
      </div>

      {loading ? (
        <div className="text-center">
          <Loader className="h-8 w-8 animate-spin mx-auto mb-2" />
          <p>Loading worksheets...</p>
        </div>
      ) : (
        <div className="space-y-3">
          {worksheets.map((worksheet) => (
            <button
              key={worksheet.sheetId}
              onClick={() => {
                setSelectedWorksheet(worksheet.title);
                fetchHeaders();
              }}
              className="w-full text-left p-4 border border-gray-200 rounded-lg hover:border-builders-500 hover:bg-builders-50 transition-colors duration-200"
            >
              <div className="flex items-center justify-between">
                <span className="font-medium text-gray-900">{worksheet.title}</span>
                <ArrowRight className="h-4 w-4 text-gray-400" />
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );

  const renderColumnMapping = () => {
    const autoDetectedMapping = autoDetectColumnMapping(headers);
    const detectedCount = Object.keys(autoDetectedMapping).length;
    
    return (
      <div className="card">
        <div className="text-center mb-6">
          <Database className="h-12 w-12 text-purple-500 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-gray-900 mb-2">Map Columns</h3>
          <p className="text-gray-600">
            Map your sheet columns to the required fields
          </p>
          {detectedCount > 0 && (
            <div className="mt-3 flex items-center justify-center space-x-2">
              <CheckCircle className="h-4 w-4 text-green-500" />
              <span className="text-sm text-green-600">
                Auto-detected {detectedCount} of {requiredColumns.length} columns
              </span>
              <button
                onClick={() => {
                  const detectedMapping = autoDetectColumnMapping(headers);
                  setColumnMapping(detectedMapping);
                }}
                className="text-xs text-blue-600 hover:text-blue-800 underline ml-2"
              >
                Reset to Auto-Detect
              </button>
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {requiredColumns.map((requiredCol) => {
          const isAutoDetected = autoDetectedMapping[requiredCol] === columnMapping[requiredCol];
          return (
            <div key={requiredCol}>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                <div className="flex items-center space-x-2">
                  <span>{requiredCol} <span className="text-red-500">*</span></span>
                  {isAutoDetected && (
                    <span className="inline-flex items-center px-1.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                      <CheckCircle className="h-3 w-3 mr-1" />
                      Auto-detected
                    </span>
                  )}
                </div>
              </label>
              <select
                value={columnMapping[requiredCol] || ''}
                onChange={(e) => setColumnMapping(prev => ({
                  ...prev,
                  [requiredCol]: e.target.value
                }))}
                className={`select-field ${isAutoDetected ? 'border-green-300 bg-green-50' : ''}`}
              >
                <option value="">Select column...</option>
                {headers.map((header, index) => (
                  <option key={index} value={header}>{header}</option>
                ))}
              </select>
            </div>
          );
        })}
      </div>

      <div className="mt-6 flex justify-end">
        <button
          onClick={saveConfiguration}
          disabled={loading}
          className="btn-primary disabled:opacity-50"
        >
          {loading ? 'Saving...' : 'Save Configuration'}
        </button>
      </div>
    </div>
  );

  const renderStep4 = () => (
    <div className="card max-w-2xl">
      <div className="text-center mb-6">
        <CheckCircle className="h-12 w-12 text-green-500 mx-auto mb-4" />
        <h3 className="text-lg font-semibold text-gray-900 mb-2">Configuration Complete!</h3>
        <p className="text-gray-600">
          Your Google Sheet is now connected and configured
        </p>
      </div>

      <div className="bg-green-50 border border-green-200 rounded-md p-4">
        <div className="space-y-2">
          <p className="text-sm text-green-800">
            <strong>Spreadsheet:</strong> {configuredSpreadsheetName || selectedSpreadsheet || 'Loading...'}
          </p>
          <p className="text-sm text-green-800">
            <strong>Worksheet:</strong> {selectedWorksheet || 'Loading...'}
          </p>
          <p className="text-sm text-green-800">
            <strong>Columns Mapped:</strong> {Object.keys(columnMapping).length}/{requiredColumns.length}
          </p>
        </div>
      </div>

      <div className="mt-6 flex justify-center space-x-3">
        <button
          onClick={() => {
            setStep(2);
            setSelectedSpreadsheet('');
            setSelectedWorksheet('');
            setColumnMapping({});
            setConfiguredSpreadsheetName('');
          }}
          className="btn-secondary"
        >
          Reconfigure
        </button>
        <button
          onClick={handleDisconnectGoogle}
          className="px-4 py-2 bg-red-600 text-white text-sm rounded-md hover:bg-red-700 transition-colors duration-200"
        >
          Disconnect Google Account
        </button>
      </div>
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center space-x-3">
        <Database className="h-8 w-8 text-builders-500" />
        <div>
          <h1 className="text-xl font-bold text-gray-900">Sheet Configuration</h1>
          <p className="text-gray-600">Connect and configure your Google Sheet</p>
        </div>
      </div>

      {/* Progress Steps */}
      <div className="flex items-center justify-center space-x-4 mb-8">
        {[
          { num: 1, label: 'Link Google', active: step === 1, completed: user?.google_linked },
          { num: 2, label: 'Select Sheet', active: step === 2, completed: step > 2 },
          { num: 3, label: 'Map Columns', active: step === 3 || step === 3.5, completed: step > 3.5 },
          { num: 4, label: 'Complete', active: step === 4, completed: step === 4 }
        ].map((stepItem, index) => (
          <React.Fragment key={stepItem.num}>
            <div className="flex items-center">
              <button
                onClick={() => {
                  setHasManuallyNavigated(true);
                  if (stepItem.num === 1) {
                    setStep(1);
                  } else if (stepItem.num === 2 && user?.google_linked) {
                    setStep(2);
                    fetchSpreadsheets();
                  } else if (stepItem.num === 3 && selectedSpreadsheet && selectedWorksheet) {
                    setStep(3.5);
                  } else if (stepItem.num === 4 && user?.sheet_configured) {
                    setStep(4);
                  }
                }}
                disabled={
                  (stepItem.num === 2 && !user?.google_linked) ||
                  (stepItem.num === 3 && (!selectedSpreadsheet || !selectedWorksheet)) ||
                  (stepItem.num === 4 && !user?.sheet_configured)
                }
                className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium transition-colors ${
                  stepItem.completed 
                    ? 'bg-green-500 text-white hover:bg-green-600' 
                    : stepItem.active 
                      ? 'bg-builders-500 text-white' 
                      : 'bg-gray-200 text-gray-600 hover:bg-gray-300 disabled:hover:bg-gray-200 disabled:cursor-not-allowed'
                }`}
              >
                {stepItem.completed ? <CheckCircle className="h-4 w-4" /> : stepItem.num}
              </button>
              <span className={`ml-2 text-sm ${
                stepItem.active ? 'text-builders-600 font-medium' : 'text-gray-500'
              }`}>
                {stepItem.label}
              </span>
            </div>
            {index < 3 && (
              <ArrowRight className="h-4 w-4 text-gray-400" />
            )}
          </React.Fragment>
        ))}
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
            <AlertCircle className="h-5 w-5" />
          )}
          <span>{message.text}</span>
        </div>
      )}

      {/* Step Content */}
      {step === 1 && renderStep1()}
      {step === 2 && renderStep2()}
      {step === 3 && renderStep3()}
      {step === 3.5 && renderColumnMapping()}
      {step === 4 && renderStep4()}
    </div>
  );
};

export default SheetConfig;