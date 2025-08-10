import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { 
  CheckCircle, 
  Circle, 
  ArrowRight, 
  ArrowLeft,
  User,
  Link as LinkIcon,
  Database,
  ExternalLink,
  AlertTriangle,
  Check,
  Settings,
  Upload,
  File,
  FileSpreadsheet
} from 'lucide-react';
import axios from 'axios';

const OnboardingStep = ({ number, title, description, completed, active, children }) => (
  <div className={`relative ${active ? 'z-10' : 'z-0'}`}>
    <div className={`flex items-start ${active ? 'bg-white rounded-lg border-2 border-builders-500 p-6 shadow-lg' : 'p-4'}`}>
      <div className="flex-shrink-0">
        <div className={`flex items-center justify-center w-8 h-8 rounded-full ${
          completed 
            ? 'bg-green-500 text-white' 
            : active 
              ? 'bg-builders-500 text-white' 
              : 'bg-gray-200 text-gray-600'
        }`}>
          {completed ? <Check className="w-4 h-4" /> : number}
        </div>
      </div>
      <div className="ml-4 flex-1">
        <h3 className={`text-lg font-medium ${active ? 'text-gray-900' : 'text-gray-700'}`}>
          {title}
        </h3>
        <p className={`text-sm ${active ? 'text-gray-600' : 'text-gray-500'}`}>
          {description}
        </p>
        {active && children}
      </div>
    </div>
  </div>
);

const Onboarding = () => {
  const { user, refreshUser } = useAuth();
  const [currentStep, setCurrentStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Step 1: Profile Data
  const [profileData, setProfileData] = useState({
    email: '',
    sellerboard_orders_url: '',
    sellerboard_stock_url: '',
    run_scripts: false
  });

  // Step 2: File Upload Status
  const [fileStatus, setFileStatus] = useState({
    has_sellerboard: false,
    has_listing_loader: false,
    files_complete: false
  });
  const [uploadingFiles, setUploadingFiles] = useState(false);

  // Step 3: Google Auth
  const [googleAuthUrl, setGoogleAuthUrl] = useState('');
  const [authCode, setAuthCode] = useState('');

  // Step 4: Sheet Configuration
  const [spreadsheets, setSpreadsheets] = useState([]);
  const [selectedSpreadsheet, setSelectedSpreadsheet] = useState('');
  const [worksheets, setWorksheets] = useState([]);
  const [selectedWorksheet, setSelectedWorksheet] = useState('');
  const [sheetHeaders, setSheetHeaders] = useState([]);
  const [columnMapping, setColumnMapping] = useState({
    'Date': '',
    'Sale Price': '',
    'Name': '',
    'Size/Color': '',
    '# Units in Bundle': '',
    'Amount Purchased': '',
    'ASIN': '',
    'COGS': '',
    'Order #': '',
    'Prep Notes': ''
  });

  // Progress tracking
  const getStepStatus = () => {
    const steps = [
      {
        number: 1,
        title: "Profile Setup",
        description: "Configure your basic profile and Sellerboard URLs",
        completed: user?.profile_configured || false,
        isValid: profileData.email && profileData.sellerboard_orders_url && profileData.sellerboard_stock_url
      },
      {
        number: 2,
        title: "Upload Required Files",
        description: "Upload your Sellerboard file and Listing Loader template",
        completed: fileStatus.files_complete,
        isValid: fileStatus.files_complete
      },
      {
        number: 3,
        title: "Connect Google Account",
        description: "Link your Google account for spreadsheet access",
        completed: user?.google_linked || false,
        isValid: user?.google_linked || false
      },
      {
        number: 4,
        title: "Configure Spreadsheet",
        description: "Set up your inventory tracking spreadsheet",
        completed: user?.sheet_configured || false,
        isValid: selectedSpreadsheet && selectedWorksheet && Object.values(columnMapping).every(v => v)
      }
    ];

    return steps;
  };

  const steps = getStepStatus();
  const currentStepData = steps[currentStep - 1];

  useEffect(() => {
    // Auto-advance to first incomplete step
    const firstIncompleteStep = steps.findIndex(step => !step.completed);
    if (firstIncompleteStep !== -1) {
      setCurrentStep(firstIncompleteStep + 1);
    }
  }, [user]);

  // Step 1: Handle Profile Submission
  const handleProfileSubmit = async () => {
    if (!profileData.email || !profileData.sellerboard_orders_url || !profileData.sellerboard_stock_url) {
      setError('Please fill in all required fields');
      return;
    }

    setLoading(true);
    setError('');
    try {
      await axios.post('/api/user/profile', profileData, { withCredentials: true });
      setSuccess('Profile updated successfully!');
      await refreshUser();
      setTimeout(() => {
        setCurrentStep(2);
        setSuccess('');
        fetchFileStatus(); // Load file status for step 2
      }, 1000);
    } catch (error) {
      setError(error.response?.data?.error || 'Failed to update profile');
    } finally {
      setLoading(false);
    }
  };

  // Step 2: File Upload Functions
  const fetchFileStatus = async () => {
    try {
      const response = await axios.get('/api/files/status', { withCredentials: true });
      setFileStatus(response.data);
    } catch (error) {
      setError('Failed to check file upload status');
    }
  };

  const handleFileUpload = async (file, fileType) => {
    if (!file) return;

    setUploadingFiles(true);
    setError('');

    const formData = new FormData();
    formData.append('file', file);

    try {
      await axios.post('/api/upload/sellerboard', formData, {
        withCredentials: true,
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      
      setSuccess(`${fileType} uploaded successfully!`);
      fetchFileStatus(); // Refresh status
      
      setTimeout(() => setSuccess(''), 3000);
    } catch (error) {
      setError(error.response?.data?.error || `Failed to upload ${fileType}`);
    } finally {
      setUploadingFiles(false);
    }
  };

  const proceedFromFileUpload = () => {
    if (fileStatus.files_complete) {
      setCurrentStep(3);
    } else {
      setError('Please upload both required files before proceeding');
    }
  };

  // Step 3: Google Authentication
  const getGoogleAuthUrl = async () => {
    try {
      const response = await axios.get('/api/google/auth-url', { withCredentials: true });
      setGoogleAuthUrl(response.data.auth_url);
    } catch (error) {
      setError('Failed to get Google auth URL');
    }
  };

  const handleGoogleAuth = async () => {
    if (!authCode) {
      setError('Please enter the authorization code');
      return;
    }

    setLoading(true);
    setError('');
    try {
      await axios.post('/api/google/complete-auth', { code: authCode }, { withCredentials: true });
      setSuccess('Google account linked successfully!');
      await refreshUser();
      setTimeout(() => {
        setCurrentStep(4);
        setSuccess('');
        fetchSpreadsheets();
      }, 1000);
    } catch (error) {
      setError(error.response?.data?.error || 'Failed to link Google account');
    } finally {
      setLoading(false);
    }
  };

  // Step 3: Sheet Configuration
  const fetchSpreadsheets = async () => {
    try {
      const response = await axios.get('/api/google/spreadsheets', { withCredentials: true });
      setSpreadsheets(response.data.spreadsheets);
    } catch (error) {
      setError('Failed to fetch spreadsheets');
    }
  };

  const fetchWorksheets = async (spreadsheetId) => {
    try {
      const response = await axios.get(`/api/google/worksheets/${spreadsheetId}`, { withCredentials: true });
      setWorksheets(response.data.worksheets);
    } catch (error) {
      setError('Failed to fetch worksheets');
    }
  };

  const fetchSheetHeaders = async (spreadsheetId, worksheetTitle) => {
    try {
      const response = await axios.get(`/api/sheet/headers/${spreadsheetId}/${encodeURIComponent(worksheetTitle)}`, { withCredentials: true });
      setSheetHeaders(response.data.headers);
    } catch (error) {
      setError('Failed to fetch sheet headers');
    }
  };

  const handleSheetSubmit = async () => {
    if (!selectedSpreadsheet || !selectedWorksheet || !Object.values(columnMapping).every(v => v)) {
      setError('Please complete all sheet configuration fields');
      return;
    }

    setLoading(true);
    setError('');
    try {
      await axios.post('/api/sheet/configure', {
        spreadsheet_id: selectedSpreadsheet,
        worksheet_title: selectedWorksheet,
        column_mapping: columnMapping
      }, { withCredentials: true });
      
      setSuccess('Sheet configuration saved successfully!');
      await refreshUser();
      
      // Setup complete! Redirect to dashboard
      setTimeout(() => {
        window.location.href = '/dashboard';
      }, 2000);
    } catch (error) {
      setError(error.response?.data?.error || 'Failed to save sheet configuration');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (currentStep === 2) {
      fetchFileStatus();
    } else if (currentStep === 3) {
      getGoogleAuthUrl();
    }
  }, [currentStep]);

  useEffect(() => {
    if (selectedSpreadsheet) {
      fetchWorksheets(selectedSpreadsheet);
    }
  }, [selectedSpreadsheet]);

  useEffect(() => {
    if (selectedSpreadsheet && selectedWorksheet) {
      fetchSheetHeaders(selectedSpreadsheet, selectedWorksheet);
    }
  }, [selectedSpreadsheet, selectedWorksheet]);

  const isStepComplete = (stepNumber) => {
    return steps[stepNumber - 1]?.completed;
  };

  const canProceedToStep = (stepNumber) => {
    if (stepNumber === 1) return true;
    return isStepComplete(stepNumber - 1);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-4xl mx-auto py-8 px-4">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-xl font-bold text-gray-900 mb-2">Welcome to DMS!</h1>
          <p className="text-sm text-gray-600">Let's get your account set up in just a few steps</p>
        </div>

        {/* Progress Bar */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-4">
            {steps.map((step, index) => (
              <div key={step.number} className="flex items-center">
                <div className={`flex items-center justify-center w-8 h-8 rounded-full border-2 ${
                  step.completed 
                    ? 'bg-green-500 border-green-500 text-white' 
                    : currentStep === step.number
                      ? 'bg-builders-500 border-builders-500 text-white'
                      : 'bg-white border-gray-300 text-gray-500'
                }`}>
                  {step.completed ? <Check className="w-4 h-4" /> : step.number}
                </div>
                {index < steps.length - 1 && (
                  <div className={`w-16 h-1 mx-4 ${
                    step.completed ? 'bg-green-500' : 'bg-gray-200'
                  }`} />
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Error/Success Messages */}
        {error && (
          <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4">
            <div className="flex">
              <AlertTriangle className="h-5 w-5 text-red-400 flex-shrink-0" />
              <p className="ml-3 text-sm text-red-700">{error}</p>
            </div>
          </div>
        )}

        {success && (
          <div className="mb-6 bg-green-50 border border-green-200 rounded-lg p-4">
            <div className="flex">
              <CheckCircle className="h-5 w-5 text-green-400 flex-shrink-0" />
              <p className="ml-3 text-sm text-green-700">{success}</p>
            </div>
          </div>
        )}

        {/* Steps */}
        <div className="space-y-6">
          {/* Step 1: Profile Setup */}
          <OnboardingStep
            number={1}
            title="Profile Setup"
            description="Configure your basic profile and Sellerboard URLs"
            completed={isStepComplete(1)}
            active={currentStep === 1}
          >
            <div className="mt-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Email Address *
                </label>
                <input
                  type="email"
                  value={profileData.email}
                  onChange={(e) => setProfileData({...profileData, email: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-builders-500"
                  placeholder="your@email.com"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Sellerboard Orders Report URL *
                </label>
                <input
                  type="url"
                  value={profileData.sellerboard_orders_url}
                  onChange={(e) => setProfileData({...profileData, sellerboard_orders_url: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-builders-500"
                  placeholder="https://app.sellerboard.com/en/automation/reports?id=..."
                />
                <p className="text-xs text-gray-500 mt-1">The automation URL for your Sellerboard orders report</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Sellerboard Stock Report URL *
                </label>
                <input
                  type="url"
                  value={profileData.sellerboard_stock_url}
                  onChange={(e) => setProfileData({...profileData, sellerboard_stock_url: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-builders-500"
                  placeholder="https://app.sellerboard.com/en/automation/reports?id=..."
                />
                <p className="text-xs text-gray-500 mt-1">The automation URL for your Sellerboard stock report</p>
              </div>

              <div className="flex items-center">
                <input
                  id="run_scripts"
                  type="checkbox"
                  checked={profileData.run_scripts}
                  onChange={(e) => setProfileData({...profileData, run_scripts: e.target.checked})}
                  className="h-4 w-4 text-builders-600 focus:ring-builders-500 border-gray-300 rounded"
                />
                <label htmlFor="run_scripts" className="ml-2 block text-sm text-gray-700">
                  Enable automated scripts
                </label>
              </div>

              <button
                onClick={handleProfileSubmit}
                disabled={loading || !profileData.email || !profileData.sellerboard_orders_url || !profileData.sellerboard_stock_url}
                className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-builders-600 hover:bg-builders-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-builders-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? 'Saving...' : 'Save Profile & Continue'}
              </button>
            </div>
          </OnboardingStep>

          {/* Step 2: File Upload */}
          <OnboardingStep
            number={2}
            title="Upload Required Files"
            description="Upload your Sellerboard file and Listing Loader template"
            completed={isStepComplete(2)}
            active={currentStep === 2}
          >
            <div className="mt-4 space-y-6">
              {/* Sellerboard File Upload */}
              <div className="border-2 border-dashed border-gray-300 rounded-lg p-6">
                <div className="text-center">
                  <FileSpreadsheet className="mx-auto h-12 w-12 text-gray-400" />
                  <h3 className="mt-2 text-sm font-medium text-gray-900">
                    Sellerboard File {fileStatus.has_sellerboard && <Check className="inline w-4 h-4 text-green-500 ml-1" />}
                  </h3>
                  <p className="mt-1 text-sm text-gray-500">
                    Upload your exported Sellerboard file (.xlsx, .csv)
                  </p>
                  <div className="mt-4">
                    <input
                      type="file"
                      accept=".xlsx,.csv,.xls"
                      onChange={(e) => handleFileUpload(e.target.files[0], 'Sellerboard file')}
                      className="hidden"
                      id="sellerboard-upload"
                      disabled={uploadingFiles}
                    />
                    <label
                      htmlFor="sellerboard-upload"
                      className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-builders-600 hover:bg-builders-700 cursor-pointer disabled:opacity-50"
                    >
                      <Upload className="w-4 h-4 mr-2" />
                      {fileStatus.has_sellerboard ? 'Replace File' : 'Upload Sellerboard File'}
                    </label>
                  </div>
                </div>
              </div>

              {/* Listing Loader Upload */}
              <div className="border-2 border-dashed border-gray-300 rounded-lg p-6">
                <div className="text-center">
                  <File className="mx-auto h-12 w-12 text-gray-400" />
                  <h3 className="mt-2 text-sm font-medium text-gray-900">
                    Listing Loader Template {fileStatus.has_listing_loader && <Check className="inline w-4 h-4 text-green-500 ml-1" />}
                  </h3>
                  <p className="mt-1 text-sm text-gray-500">
                    Upload your Amazon Listing Loader template (.xlsm)
                  </p>
                  <div className="mt-4">
                    <input
                      type="file"
                      accept=".xlsm"
                      onChange={(e) => handleFileUpload(e.target.files[0], 'Listing Loader template')}
                      className="hidden"
                      id="listing-loader-upload"
                      disabled={uploadingFiles}
                    />
                    <label
                      htmlFor="listing-loader-upload"
                      className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-builders-600 hover:bg-builders-700 cursor-pointer disabled:opacity-50"
                    >
                      <Upload className="w-4 h-4 mr-2" />
                      {fileStatus.has_listing_loader ? 'Replace Template' : 'Upload Listing Loader'}
                    </label>
                  </div>
                </div>
              </div>

              {/* Progress Status */}
              <div className="bg-gray-50 rounded-lg p-4">
                <h4 className="text-sm font-medium text-gray-900 mb-2">Upload Progress:</h4>
                <div className="space-y-2">
                  <div className="flex items-center">
                    {fileStatus.has_sellerboard ? (
                      <CheckCircle className="w-4 h-4 text-green-500 mr-2" />
                    ) : (
                      <Circle className="w-4 h-4 text-gray-300 mr-2" />
                    )}
                    <span className={`text-sm ${fileStatus.has_sellerboard ? 'text-green-700' : 'text-gray-500'}`}>
                      Sellerboard file uploaded
                    </span>
                  </div>
                  <div className="flex items-center">
                    {fileStatus.has_listing_loader ? (
                      <CheckCircle className="w-4 h-4 text-green-500 mr-2" />
                    ) : (
                      <Circle className="w-4 h-4 text-gray-300 mr-2" />
                    )}
                    <span className={`text-sm ${fileStatus.has_listing_loader ? 'text-green-700' : 'text-gray-500'}`}>
                      Listing Loader template uploaded
                    </span>
                  </div>
                </div>
              </div>

              <button
                onClick={proceedFromFileUpload}
                disabled={!fileStatus.files_complete || uploadingFiles}
                className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-builders-600 hover:bg-builders-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-builders-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {uploadingFiles ? 'Uploading...' : 'Continue to Google Authentication'}
              </button>
            </div>
          </OnboardingStep>

          {/* Step 3: Google Authentication */}
          <OnboardingStep
            number={3}
            title="Connect Google Account"
            description="Link your Google account for spreadsheet access"
            completed={isStepComplete(3)}
            active={currentStep === 3}
          >
            {!isStepComplete(3) && (
              <div className="mt-4 space-y-4">
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <div className="flex">
                    <LinkIcon className="h-5 w-5 text-blue-400 flex-shrink-0" />
                    <div className="ml-3">
                      <h4 className="text-sm font-medium text-blue-800">Connect Your Google Account</h4>
                      <p className="text-sm text-blue-700 mt-1">
                        We need access to your Google Sheets to manage your inventory data.
                      </p>
                    </div>
                  </div>
                </div>

                {googleAuthUrl && (
                  <>
                    <div>
                      <p className="text-sm text-gray-700 mb-2">
                        1. Click the button below to authorize access to your Google account:
                      </p>
                      <a
                        href={googleAuthUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700"
                      >
                        Authorize Google Access
                        <ExternalLink className="ml-2 h-4 w-4" />
                      </a>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        2. Paste the authorization code here:
                      </label>
                      <input
                        type="text"
                        value={authCode}
                        onChange={(e) => setAuthCode(e.target.value)}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-builders-500"
                        placeholder="Paste authorization code here..."
                      />
                    </div>

                    <button
                      onClick={handleGoogleAuth}
                      disabled={loading || !authCode}
                      className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-builders-600 hover:bg-builders-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-builders-500 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {loading ? 'Connecting...' : 'Complete Google Connection'}
                    </button>
                  </>
                )}
              </div>
            )}
          </OnboardingStep>

          {/* Step 4: Spreadsheet Configuration */}
          <OnboardingStep
            number={4}
            title="Configure Spreadsheet"
            description="Set up your inventory tracking spreadsheet"
            completed={isStepComplete(4)}
            active={currentStep === 4}
          >
            {!isStepComplete(4) && (
              <div className="mt-4 space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Select Spreadsheet
                  </label>
                  <select
                    value={selectedSpreadsheet}
                    onChange={(e) => setSelectedSpreadsheet(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-builders-500"
                  >
                    <option value="">Choose a spreadsheet...</option>
                    {spreadsheets.map((sheet) => (
                      <option key={sheet.id} value={sheet.id}>
                        {sheet.name}
                      </option>
                    ))}
                  </select>
                </div>

                {worksheets.length > 0 && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Select Worksheet
                    </label>
                    <select
                      value={selectedWorksheet}
                      onChange={(e) => setSelectedWorksheet(e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-builders-500"
                    >
                      <option value="">Choose a worksheet...</option>
                      {worksheets.map((worksheet) => (
                        <option key={worksheet.sheetId} value={worksheet.title}>
                          {worksheet.title}
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                {sheetHeaders.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-gray-700 mb-3">Map Your Columns</h4>
                    <p className="text-sm text-gray-600 mb-4">
                      Map the following required columns from your spreadsheet:
                    </p>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {Object.keys(columnMapping).map((columnName) => (
                        <div key={columnName}>
                          <label className="block text-sm font-medium text-gray-700 mb-1">
                            {columnName}
                          </label>
                          <select
                            value={columnMapping[columnName]}
                            onChange={(e) => setColumnMapping({...columnMapping, [columnName]: e.target.value})}
                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-builders-500"
                          >
                            <option value="">Select column...</option>
                            {sheetHeaders.map((header) => (
                              <option key={header} value={header}>
                                {header}
                              </option>
                            ))}
                          </select>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {Object.values(columnMapping).every(v => v) && (
                  <button
                    onClick={handleSheetSubmit}
                    disabled={loading}
                    className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-builders-600 hover:bg-builders-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-builders-500 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {loading ? 'Completing Setup...' : 'Complete Setup'}
                  </button>
                )}
              </div>
            )}
          </OnboardingStep>
        </div>

        {/* Navigation */}
        <div className="mt-8 flex justify-between">
          <button
            onClick={() => setCurrentStep(Math.max(1, currentStep - 1))}
            disabled={currentStep === 1}
            className="flex items-center px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Previous
          </button>

          <button
            onClick={() => setCurrentStep(Math.min(3, currentStep + 1))}
            disabled={currentStep === 3 || !canProceedToStep(currentStep + 1)}
            className="flex items-center px-4 py-2 text-sm font-medium text-white bg-builders-600 border border-transparent rounded-md hover:bg-builders-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Next
            <ArrowRight className="w-4 h-4 ml-2" />
          </button>
        </div>
      </div>
    </div>
  );
};

export default Onboarding;