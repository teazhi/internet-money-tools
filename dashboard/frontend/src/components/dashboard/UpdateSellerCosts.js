import React, { useState } from 'react';
import axios from 'axios';
import { Upload, FileText, Download, AlertCircle, CheckCircle, RefreshCw } from 'lucide-react';
import { API_ENDPOINTS } from '../../config/api';

const UpdateSellerCosts = () => {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [dragActive, setDragActive] = useState(false);

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  };

  const handleFile = (selectedFile) => {
    // Validate file type
    const validTypes = ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'application/vnd.ms-excel'];
    const validExtensions = ['.xlsx', '.xls'];
    const fileExtension = selectedFile.name.substring(selectedFile.name.lastIndexOf('.')).toLowerCase();
    
    if (!validTypes.includes(selectedFile.type) && !validExtensions.includes(fileExtension)) {
      setError('Please upload an Excel file (.xlsx or .xls)');
      return;
    }

    setFile(selectedFile);
    setError(null);
    setSuccess(null);
  };

  const handleUpload = async () => {
    if (!file) {
      setError('Please select a file to upload');
      return;
    }

    setLoading(true);
    setError(null);
    setSuccess(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post(
        API_ENDPOINTS.UPDATE_SELLER_COSTS,
        formData,
        {
          withCredentials: true,
          responseType: 'blob',
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        }
      );

      // Extract summary from headers
      const updatedCount = response.headers['x-updated-count'] || '0';
      const skippedCount = response.headers['x-skipped-count'] || '0';
      const notFoundCount = response.headers['x-not-found-count'] || '0';

      // Create a download link for the updated file
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `updated_seller_costs_${new Date().toISOString().slice(0, 10)}.xlsx`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);

      // Create detailed success message
      let successMessage = `File updated successfully! Updated ${updatedCount} products.`;
      if (skippedCount > 0) {
        successMessage += ` Skipped ${skippedCount} products (Latest Approved Cost was higher).`;
      }
      if (notFoundCount > 0) {
        successMessage += ` ${notFoundCount} ASINs not found in Google Sheets.`;
      }

      setSuccess(successMessage);
      setFile(null);
    } catch (err) {
      console.error('Upload error:', err);
      if (err.response && err.response.data) {
        // Try to read the error from blob response
        if (err.response.data instanceof Blob) {
          const text = await err.response.data.text();
          try {
            const errorData = JSON.parse(text);
            setError(errorData.error || 'Failed to update seller costs');
          } catch {
            setError('Failed to update seller costs');
          }
        } else {
          setError(err.response.data.error || 'Failed to update seller costs');
        }
      } else {
        setError('Failed to upload file. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="mb-6">
        <h2 className="text-xl font-bold text-gray-900 mb-2">Update Seller Costs</h2>
        <p className="text-gray-600">
          Upload your Excel file to automatically update the "Seller New Cost" column with the latest sourcing costs from your connected Google Sheets.
        </p>
      </div>

      {/* Upload Area */}
      <div
        className={`relative border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
          dragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-gray-400'
        }`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
      >
        <input
          type="file"
          id="file-upload"
          className="sr-only"
          onChange={handleFileChange}
          accept=".xlsx,.xls"
          disabled={loading}
        />
        
        <label
          htmlFor="file-upload"
          className="cursor-pointer"
        >
          <Upload className="mx-auto h-12 w-12 text-gray-400 mb-4" />
          
          {file ? (
            <div className="space-y-2">
              <div className="flex items-center justify-center space-x-2">
                <FileText className="h-5 w-5 text-blue-600" />
                <span className="text-sm font-medium text-gray-900">{file.name}</span>
              </div>
              <p className="text-xs text-gray-500">
                Click to change file or drag a new one
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              <p className="text-sm text-gray-600">
                <span className="font-semibold text-gray-900">Click to upload</span> or drag and drop
              </p>
              <p className="text-xs text-gray-500">Excel files only (.xlsx, .xls)</p>
            </div>
          )}
        </label>
      </div>

      {/* Requirements */}
      <div className="mt-4 bg-blue-50 border border-blue-200 rounded-md p-4">
        <h4 className="text-sm font-medium text-blue-900 mb-2">File Requirements:</h4>
        <ul className="text-sm text-blue-800 space-y-1">
          <li>• Excel file must contain an "ASIN" column (case-insensitive)</li>
          <li>• The "Seller New Cost" column will be created/updated automatically</li>
          <li>• Only updates if fetched cost is higher than "Latest Approved Cost"</li>
          <li>• Make sure your Google Sheets leads are connected in Settings</li>
          <li>• COGS data will be pulled from all worksheets in your leads sheet</li>
        </ul>
      </div>

      {/* Error Message */}
      {error && (
        <div className="mt-4 bg-red-50 border border-red-200 rounded-md p-4 flex items-start">
          <AlertCircle className="h-5 w-5 text-red-600 mr-2 flex-shrink-0 mt-0.5" />
          <div className="text-sm text-red-800">{error}</div>
        </div>
      )}

      {/* Success Message */}
      {success && (
        <div className="mt-4 bg-green-50 border border-green-200 rounded-md p-4 flex items-start">
          <CheckCircle className="h-5 w-5 text-green-600 mr-2 flex-shrink-0 mt-0.5" />
          <div className="text-sm text-green-800">{success}</div>
        </div>
      )}

      {/* Actions */}
      <div className="mt-6 flex items-center justify-end space-x-3">
        {file && !loading && (
          <button
            onClick={() => {
              setFile(null);
              setError(null);
              setSuccess(null);
            }}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
          >
            Clear
          </button>
        )}
        
        <button
          onClick={handleUpload}
          disabled={!file || loading}
          className={`flex items-center px-4 py-2 text-sm font-medium text-white rounded-md transition-colors ${
            !file || loading
              ? 'bg-gray-400 cursor-not-allowed'
              : 'bg-blue-600 hover:bg-blue-700'
          }`}
        >
          {loading ? (
            <>
              <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
              Processing...
            </>
          ) : (
            <>
              <Download className="h-4 w-4 mr-2" />
              Update Costs
            </>
          )}
        </button>
      </div>

      {/* Example Template */}
      <div className="mt-8 border-t pt-6">
        <h3 className="text-sm font-medium text-gray-900 mb-2">Need a template?</h3>
        <p className="text-sm text-gray-600">
          Your Excel file should have at minimum an ASIN column (case-insensitive: "ASIN" or "Asin"). 
          The "Seller New Cost" column will be added/updated automatically with the latest COGS from your Google Sheets.
        </p>
      </div>
    </div>
  );
};

export default UpdateSellerCosts;