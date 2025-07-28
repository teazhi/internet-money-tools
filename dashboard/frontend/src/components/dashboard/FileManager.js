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
  Download
} from 'lucide-react';
import axios from 'axios';

const FileManager = () => {
  const { user } = useAuth();
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState({ type: '', text: '' });
  const [dragOver, setDragOver] = useState(false);

  useEffect(() => {
    fetchFiles();
  }, []);

  const fetchFiles = async () => {
    try {
      const response = await axios.get('/api/files/sellerboard', { withCredentials: true });
      setFiles(response.data.files || []);
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

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-builders-500"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center space-x-3">
        <FileText className="h-8 w-8 text-builders-500" />
        <div>
          <h1 className="text-2xl font-bold text-gray-900">File Manager</h1>
          <p className="text-gray-600">Upload and manage your Sellerboard files</p>
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
            <AlertCircle className="h-5 w-5" />
          )}
          <span>{message.text}</span>
        </div>
      )}

      {/* Upload Area */}
      <div className="card">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Upload Sellerboard File</h3>
        
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
              {dragOver ? 'Drop file here' : 'Upload your Sellerboard file'}
            </p>
            <p className="text-sm text-gray-500">
              Drag and drop your file here, or click to browse
            </p>
            <p className="text-xs text-gray-400">
              Supports CSV, XLSX, XLSM, XLS files up to 16MB
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
            {files.map((file, index) => (
              <div
                key={index}
                className="flex items-center justify-between p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors duration-200"
              >
                <div className="flex items-center space-x-4">
                  <div className="flex-shrink-0">
                    <File className="h-8 w-8 text-gray-400" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-900">{file.filename}</p>
                    <div className="flex items-center space-x-4 text-xs text-gray-500">
                      <span className="flex items-center space-x-1">
                        <Calendar className="h-3 w-3" />
                        <span>{formatDate(file.upload_date)}</span>
                      </span>
                      <span>{formatFileSize(file.file_size)}</span>
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
              <p>• Only the most recent file is kept per user (previous files are auto-deleted)</p>
              <p>• Files are used for analytics and automated script processing</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default FileManager;