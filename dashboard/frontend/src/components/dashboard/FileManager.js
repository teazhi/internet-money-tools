import React, { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { 
  Upload, 
  File, 
  Trash2, 
  Calendar, 
  FileText,
  AlertCircle,
  CheckCircle,
  Download,
  Settings
} from 'lucide-react';
import axios from 'axios';

const FileManager = () => {
  const { user } = useAuth();
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState({ type: '', text: '' });
  const [dragOver, setDragOver] = useState(false);
  const [migrating, setMigrating] = useState(false);
  const [adminMigrating, setAdminMigrating] = useState(false);
  const [cleaning, setCleaning] = useState(false);
  const [duplicates, setDuplicates] = useState({});
  const [cleaningDuplicates, setCleaningDuplicates] = useState(false);

  useEffect(() => {
    fetchFiles();
  }, []);

  const fetchFiles = async () => {
    try {
      const response = await axios.get('/api/files/sellerboard', { withCredentials: true });
      setFiles(response.data.files || []);
      setDuplicates(response.data.duplicates || {});
      
      // Show warnings if duplicates are detected
      if (response.data.warnings && response.data.warnings.length > 0) {
        setMessage({ 
          type: 'warning', 
          text: response.data.warnings.join(' ') + ' Use the "Clean Up Duplicates" button to fix this automatically.' 
        });
      } else {
        // Clear any existing warnings if no duplicates
        setMessage({ type: '', text: '' });
      }
    } catch (error) {
      console.error('Error fetching files:', error);
      setMessage({ type: 'error', text: 'Failed to load files' });
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (file) => {
    if (!file) return;

    // Validate file type
    const allowedTypes = ['text/csv', 'application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'];
    const allowedExtensions = ['.csv', '.xlsx', '.xlsm', '.xls'];
    
    const isValidType = allowedTypes.includes(file.type) || 
                       allowedExtensions.some(ext => file.name.toLowerCase().endsWith(ext));
    
    if (!isValidType) {
      setMessage({ type: 'error', text: 'Invalid file type. Please upload CSV, XLSX, XLSM, or XLS files only.' });
      return;
    }

    // Validate file size (16MB)
    if (file.size > 16 * 1024 * 1024) {
      setMessage({ type: 'error', text: 'File size too large. Maximum size is 16MB.' });
      return;
    }

    setUploading(true);
    setMessage({ type: '', text: '' });

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post('/api/upload/sellerboard', formData, {
        withCredentials: true,
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      setMessage({ type: 'success', text: 'File uploaded successfully!' });
      fetchFiles(); // Refresh file list
    } catch (error) {
      setMessage({ 
        type: 'error', 
        text: error.response?.data?.error || 'Upload failed' 
      });
    } finally {
      setUploading(false);
    }
  };

  const handleFileSelect = (event) => {
    const file = event.target.files[0];
    if (file) {
      handleFileUpload(file);
    }
    // Reset input
    event.target.value = '';
  };

  const handleDrop = (event) => {
    event.preventDefault();
    setDragOver(false);
    
    const file = event.dataTransfer.files[0];
    if (file) {
      handleFileUpload(file);
    }
  };

  const handleDragOver = (event) => {
    event.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = (event) => {
    event.preventDefault();
    setDragOver(false);
  };

  const deleteFile = async (fileKey) => {
    if (!window.confirm('Are you sure you want to delete this file?')) {
      return;
    }

    try {
      console.log('Deleting file with key:', fileKey);
      const response = await axios.delete(`/api/files/sellerboard/${encodeURIComponent(fileKey)}`, { 
        withCredentials: true 
      });
      console.log('Delete response:', response.data);
      setMessage({ type: 'success', text: 'File deleted successfully' });
      fetchFiles(); // Refresh file list
    } catch (error) {
      console.error('Delete error:', error);
      console.error('Error response:', error.response?.data);
      setMessage({ 
        type: 'error', 
        text: error.response?.data?.error || 'Failed to delete file' 
      });
    }
  };

  const migrateExistingFiles = async () => {
    setMigrating(true);
    setMessage({ type: '', text: '' });

    try {
      const response = await axios.post('/api/files/migrate', {}, { withCredentials: true });
      setMessage({ 
        type: 'success', 
        text: `${response.data.message}. Refreshing file list...` 
      });
      
      // Refresh file list after migration
      setTimeout(() => {
        fetchFiles();
        setMessage({ type: '', text: '' });
      }, 2000);
    } catch (error) {
      setMessage({ 
        type: 'error', 
        text: error.response?.data?.error || 'Failed to migrate existing files' 
      });
    } finally {
      setMigrating(false);
    }
  };

  const migrateAllUserFiles = async () => {
    if (!window.confirm('This will reorganize ALL user files in S3. Continue?')) {
      return;
    }

    setAdminMigrating(true);
    setMessage({ type: '', text: '' });

    try {
      const response = await axios.post('/api/admin/migrate-all-files', {}, { withCredentials: true });
      setMessage({ 
        type: 'success', 
        text: `${response.data.message} Check console for details.` 
      });
      console.log('Migration results:', response.data.results);
      
      // Refresh file list after migration
      setTimeout(() => {
        fetchFiles();
      }, 2000);
    } catch (error) {
      setMessage({ 
        type: 'error', 
        text: error.response?.data?.error || 'Failed to migrate all user files' 
      });
    } finally {
      setAdminMigrating(false);
    }
  };

  const cleanupUpdatedFiles = async () => {
    if (!window.confirm('This will remove _updated files from your file list. These are script-generated files, not your original uploads. Continue?')) {
      return;
    }

    setCleaning(true);
    setMessage({ type: '', text: '' });

    try {
      const response = await axios.post('/api/files/cleanup-updated', {}, { withCredentials: true });
      setMessage({ 
        type: 'success', 
        text: `${response.data.message}. Refreshing file list...` 
      });
      
      // Refresh file list after cleanup
      setTimeout(() => {
        fetchFiles();
        setMessage({ type: '', text: '' });
      }, 2000);
    } catch (error) {
      setMessage({ 
        type: 'error', 
        text: error.response?.data?.error || 'Failed to cleanup updated files' 
      });
    } finally {
      setCleaning(false);
    }
  };

  const adminCleanupAllUpdated = async () => {
    if (!window.confirm('This will remove ALL _updated files from ALL user records system-wide. These are script-generated files. Continue?')) {
      return;
    }

    setCleaning(true);
    setMessage({ type: '', text: '' });

    try {
      const response = await axios.post('/api/admin/cleanup-all-updated', {}, { withCredentials: true });
      setMessage({ 
        type: 'success', 
        text: `${response.data.message}. Refreshing file list...` 
      });
      
      // Refresh file list after cleanup
      setTimeout(() => {
        fetchFiles();
        setMessage({ type: '', text: '' });
      }, 2000);
    } catch (error) {
      setMessage({ 
        type: 'error', 
        text: error.response?.data?.error || 'Failed to cleanup all updated files' 
      });
    } finally {
      setCleaning(false);
    }
  };

  const cleanupDuplicates = async () => {
    if (!window.confirm('This will delete duplicate files, keeping only the most recent of each type. Continue?')) {
      return;
    }

    setCleaningDuplicates(true);
    setMessage({ type: '', text: '' });

    try {
      const response = await axios.post('/api/files/cleanup-duplicates', {}, { withCredentials: true });
      setMessage({ 
        type: 'success', 
        text: `${response.data.message}. Refreshing file list...` 
      });
      
      // Refresh file list after cleanup
      setTimeout(() => {
        fetchFiles();
      }, 1000);
    } catch (error) {
      setMessage({ 
        type: 'error', 
        text: error.response?.data?.error || 'Failed to cleanup duplicate files' 
      });
    } finally {
      setCleaningDuplicates(false);
    }
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    
    // Use user's timezone from their profile if available
    const userTimezone = user?.user_record?.timezone;
    
    const options = {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      ...(userTimezone && { timeZone: userTimezone })
    };
    
    return date.toLocaleDateString('en-US', options);
  };

  if (loading) {
    return (
      <div className="space-y-6">
        {/* Header Skeleton */}
        <div className="bg-gradient-to-r from-builders-500 to-builders-600 rounded-lg shadow-sm p-6">
          <div className="flex items-center justify-between">
            <div>
              <div className="h-8 bg-white/20 rounded w-32 mb-2 animate-pulse"></div>
              <div className="h-4 bg-white/20 rounded w-64 animate-pulse"></div>
            </div>
            <div className="h-10 bg-white/20 rounded w-24 animate-pulse"></div>
          </div>
        </div>

        {/* Upload Area Skeleton */}
        <div className="bg-white rounded-lg shadow">
          <div className="px-6 py-4 border-b border-gray-200">
            <div className="h-6 bg-gray-300 rounded w-32 animate-pulse"></div>
          </div>
          <div className="p-6">
            <div className="border-2 border-dashed border-gray-300 rounded-lg p-8">
              <div className="text-center">
                <div className="h-12 w-12 bg-gray-300 rounded mx-auto mb-4 animate-pulse"></div>
                <div className="h-4 bg-gray-300 rounded w-48 mx-auto mb-2 animate-pulse"></div>
                <div className="h-3 bg-gray-300 rounded w-64 mx-auto mb-4 animate-pulse"></div>
                <div className="h-10 bg-gray-300 rounded w-24 mx-auto animate-pulse"></div>
              </div>
            </div>
          </div>
        </div>

        {/* File List Skeleton */}
        <div className="bg-white rounded-lg shadow">
          <div className="px-6 py-4 border-b border-gray-200">
            <div className="h-6 bg-gray-300 rounded w-24 animate-pulse"></div>
          </div>
          <div className="divide-y divide-gray-200">
            {[1, 2, 3, 4, 5].map(i => (
              <div key={i} className="px-6 py-4 flex items-center justify-between animate-pulse">
                <div className="flex items-center space-x-3">
                  <div className="h-8 w-8 bg-gray-300 rounded"></div>
                  <div>
                    <div className="h-4 bg-gray-300 rounded w-48 mb-1"></div>
                    <div className="flex items-center space-x-4 text-sm">
                      <div className="h-3 bg-gray-300 rounded w-20"></div>
                      <div className="h-3 bg-gray-300 rounded w-16"></div>
                    </div>
                  </div>
                </div>
                <div className="flex items-center space-x-2">
                  <div className="h-8 bg-gray-300 rounded w-16"></div>
                  <div className="h-8 bg-gray-300 rounded w-16"></div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Loading indicator */}
        <div className="text-center py-4">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-builders-500 mx-auto mb-2"></div>
          <p className="text-gray-600 text-sm">Loading file manager...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <FileText className="h-8 w-8 text-builders-500" />
          <div>
            <h1 className="text-2xl font-bold text-gray-900">File Manager</h1>
            <p className="text-gray-600">Upload and manage your Sellerboard files</p>
          </div>
        </div>
        
        {/* Migration Buttons */}
        <div className="flex space-x-2">
          <button
            onClick={migrateExistingFiles}
            disabled={migrating || adminMigrating || cleaning}
            className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-builders-500 disabled:opacity-50"
          >
            <Download className="w-4 h-4 mr-2" />
            {migrating ? 'Finding Files...' : 'Refresh File List'}
          </button>
          
          {/* Cleanup Button - show if user has _updated files */}
          {files.some(f => f.filename?.includes('_updated') || f.s3_key?.includes('_updated')) && (
            <button
              onClick={cleanupUpdatedFiles}
              disabled={migrating || adminMigrating || cleaning || cleaningDuplicates}
              className="inline-flex items-center px-4 py-2 border border-yellow-300 rounded-md shadow-sm text-sm font-medium text-yellow-700 bg-yellow-50 hover:bg-yellow-100 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-yellow-500 disabled:opacity-50"
            >
              <Trash2 className="w-4 h-4 mr-2" />
              {cleaning ? 'Cleaning...' : 'Remove _updated Files'}
            </button>
          )}
          
          {/* Duplicate Cleanup Button - show if user has duplicate files */}
          {Object.keys(duplicates).length > 0 && (
            <button
              onClick={cleanupDuplicates}
              disabled={migrating || adminMigrating || cleaning || cleaningDuplicates}
              className="inline-flex items-center px-4 py-2 border border-red-300 rounded-md shadow-sm text-sm font-medium text-red-700 bg-red-50 hover:bg-red-100 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50"
            >
              <Trash2 className="w-4 h-4 mr-2" />
              {cleaningDuplicates ? 'Cleaning...' : 'Clean Up Duplicates'}
            </button>
          )}
          
          {/* Admin Buttons - only show for admin users */}
          {user?.discord_id === '1278565917206249503' && (
            <>
              <button
                onClick={migrateAllUserFiles}
                disabled={migrating || adminMigrating || cleaning}
                className="inline-flex items-center px-4 py-2 border border-red-300 rounded-md shadow-sm text-sm font-medium text-red-700 bg-red-50 hover:bg-red-100 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50"
              >
                <Settings className="w-4 h-4 mr-2" />
                {adminMigrating ? 'Migrating All...' : 'Admin: Migrate All Users'}
              </button>
              <button
                onClick={adminCleanupAllUpdated}
                disabled={migrating || adminMigrating || cleaning}
                className="inline-flex items-center px-4 py-2 border border-orange-300 rounded-md shadow-sm text-sm font-medium text-orange-700 bg-orange-50 hover:bg-orange-100 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-orange-500 disabled:opacity-50"
              >
                <Trash2 className="w-4 h-4 mr-2" />
                {cleaning ? 'Cleaning...' : 'Admin: Clean All _updated'}
              </button>
            </>
          )}
        </div>
      </div>

      {/* Message Display */}
      {message.text && (
        <div className={`flex items-center space-x-2 p-4 rounded-md ${
          message.type === 'success' 
            ? 'bg-green-50 text-green-800 border border-green-200' 
            : message.type === 'warning'
            ? 'bg-yellow-50 text-yellow-800 border border-yellow-200'
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

      {/* Upload Area */}
      <div className="card">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Upload Files</h3>
        
        <div
          className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors duration-200 ${
            dragOver 
              ? 'border-builders-500 bg-builders-50' 
              : 'border-gray-300 hover:border-gray-400'
          }`}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
        >
          <Upload className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <div className="space-y-2">
            <p className="text-lg font-medium text-gray-900">
              {dragOver ? 'Drop file here' : 'Upload your files'}
            </p>
            <p className="text-sm text-gray-500">
              Drag and drop your Sellerboard file (.xlsx/.csv) or Listing Loader template (.xlsm) here
            </p>
            <p className="text-xs text-gray-400">
              Files are automatically categorized by type • Max 16MB each
            </p>
          </div>
          
          <input
            type="file"
            onChange={handleFileSelect}
            accept=".csv,.xlsx,.xlsm,.xls"
            className="hidden"
            id="file-upload"
            disabled={uploading}
          />
          
          <label
            htmlFor="file-upload"
            className={`mt-4 inline-block px-4 py-2 bg-builders-500 text-white rounded-md hover:bg-builders-600 transition-colors duration-200 cursor-pointer ${
              uploading ? 'opacity-50 cursor-not-allowed' : ''
            }`}
          >
            {uploading ? 'Uploading...' : 'Choose File'}
          </label>
        </div>
      </div>

      {/* File List */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">Your Files</h3>
          <span className="text-sm text-gray-500">{files.length} files</span>
        </div>

        {files.length === 0 ? (
          <div className="text-center py-8">
            <File className="h-12 w-12 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-500">No files uploaded yet</p>
            <p className="text-sm text-gray-400 mt-1">
              Upload your first Sellerboard file to get started
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {files
              .sort((a, b) => {
                // Prioritize non-_updated files over _updated files
                const aIsUpdated = a.filename?.includes('_updated') || a.s3_key?.includes('_updated');
                const bIsUpdated = b.filename?.includes('_updated') || b.s3_key?.includes('_updated');
                
                if (aIsUpdated && !bIsUpdated) return 1;  // b comes first
                if (!aIsUpdated && bIsUpdated) return -1; // a comes first
                
                // If both are same type, sort by upload date (most recent first)
                return new Date(b.upload_date) - new Date(a.upload_date);
              })
              .map((file, index) => (
              <div
                key={index}
                className={`flex items-center justify-between p-4 border rounded-lg transition-colors duration-200 ${
                  (file.filename?.includes('_updated') || file.s3_key?.includes('_updated'))
                    ? 'border-yellow-200 bg-yellow-50 hover:bg-yellow-100'
                    : 'border-gray-200 hover:bg-gray-50'
                }`}
              >
                <div className="flex items-center space-x-4">
                  <div className="flex-shrink-0">
                    <File className="h-8 w-8 text-gray-400" />
                  </div>
                  <div>
                    <div className="flex items-center space-x-2">
                      <p className="text-sm font-medium text-gray-900">{file.filename}</p>
                      {file.file_type_category && (
                        <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                          file.file_type_category === 'listing_loader' 
                            ? 'bg-blue-100 text-blue-800' 
                            : 'bg-green-100 text-green-800'
                        }`}>
                          {file.file_type_category === 'listing_loader' ? 'Listing Loader' : 'Sellerboard'}
                        </span>
                      )}
                      {(file.filename?.includes('_updated') || file.s3_key?.includes('_updated')) && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-orange-100 text-orange-800">
                          Script Output
                        </span>
                      )}
                    </div>
                    <div className="flex items-center space-x-4 text-xs text-gray-500">
                      <span className="flex items-center space-x-1">
                        <Calendar className="h-3 w-3" />
                        <span>{formatDate(file.upload_date)}</span>
                      </span>
                      <span>{formatFileSize(file.file_size)}</span>
                      {file.uploaded_by && file.uploaded_by !== user?.discord_id && (
                        <span className="text-blue-600 font-medium">
                          Uploaded by VA
                        </span>
                      )}
                    </div>
                    {file.s3_key && (
                      <div className="text-xs text-gray-400 mt-1">
                        <span title={file.s3_key}>User-specific storage: {file.s3_key.split('/')[1]?.substring(0, 20)}...</span>
                      </div>
                    )}
                  </div>
                </div>
                
                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => deleteFile(file.s3_key)}
                    className="p-2 text-red-600 hover:bg-red-50 rounded-md transition-colors duration-200"
                    title="Delete file"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Usage Instructions */}
      <div className="card bg-blue-50 border border-blue-200">
        <div className="flex items-start space-x-3">
          <AlertCircle className="h-5 w-5 text-blue-500 mt-0.5" />
          <div>
            <h4 className="text-sm font-medium text-blue-900">How to use uploaded files</h4>
            <div className="text-sm text-blue-700 mt-1 space-y-1">
              <p>• Files are automatically processed and stored securely with user-specific naming</p>
              <p>• Each uploaded file gets a unique identifier tied to your Discord account</p>
              <p>• You can upload CSV files exported from Sellerboard reports</p>
              <p>• Excel files (.xlsx, .xlsm, .xls) are also supported for compatibility</p>
              <p>• Only one file of each type is kept (Sellerboard + Listing Loader)</p>
              <p>• When you upload a new file of the same type, the old one is automatically replaced</p>
              <p>• Files are used for analytics and automated script processing</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default FileManager;