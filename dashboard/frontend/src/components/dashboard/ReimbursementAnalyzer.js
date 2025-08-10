import React, { useState } from 'react';
import { 
  Upload, 
  FileText, 
  AlertCircle, 
  CheckCircle, 
  Download,
  DollarSign,
  TrendingDown,
  Activity
} from 'lucide-react';
import axios from 'axios';

const ReimbursementAnalyzer = () => {
  const [file, setFile] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [results, setResults] = useState(null);
  const [message, setMessage] = useState({ type: '', text: '' });
  const [dragOver, setDragOver] = useState(false);

  const handleFileSelect = (event) => {
    const selectedFile = event.target.files[0];
    if (selectedFile) {
      setFile(selectedFile);
      setResults(null);
      setMessage({ type: '', text: '' });
    }
    // Reset input
    event.target.value = '';
  };

  const handleDrop = (event) => {
    event.preventDefault();
    setDragOver(false);
    
    const droppedFile = event.dataTransfer.files[0];
    if (droppedFile) {
      setFile(droppedFile);
      setResults(null);
      setMessage({ type: '', text: '' });
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

  const analyzeReimbursements = async () => {
    if (!file) {
      setMessage({ type: 'error', text: 'Please select a CSV file first.' });
      return;
    }

    setAnalyzing(true);
    setMessage({ type: '', text: '' });

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post('/api/reimbursements/analyze', formData, {
        withCredentials: true,
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      setResults(response.data);
      
      if (response.data.underpaid_count === 0) {
        setMessage({ 
          type: 'success', 
          text: 'Great news! No underpaid reimbursements found.' 
        });
      } else {
        setMessage({ 
          type: 'warning', 
          text: `Found ${response.data.underpaid_count} underpaid reimbursements with a total shortfall of $${response.data.total_shortfall}.` 
        });
      }
    } catch (error) {
      console.error('Analysis error:', error);
      
      if (error.response?.data?.setup_required) {
        setMessage({ 
          type: 'error', 
          text: 'Google Sheets setup required. Please complete your profile setup first.' 
        });
      } else {
        setMessage({ 
          type: 'error', 
          text: error.response?.data?.error || 'Analysis failed. Please try again.' 
        });
      }
    } finally {
      setAnalyzing(false);
    }
  };

  const downloadResults = async () => {
    if (!results || !results.underpaid_reimbursements) return;

    try {
      const response = await axios.post('/api/reimbursements/download', {
        underpaid_reimbursements: results.underpaid_reimbursements
      }, {
        withCredentials: true,
        responseType: 'blob'
      });

      // Create download link
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'underpaid_reimbursements.csv');
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);

      setMessage({ 
        type: 'success', 
        text: 'Underpaid reimbursements CSV downloaded successfully.' 
      });
    } catch (error) {
      setMessage({ 
        type: 'error', 
        text: 'Failed to download results. Please try again.' 
      });
    }
  };

  const formatCurrency = (amount) => {
    return typeof amount === 'number' ? `$${amount.toFixed(2)}` : amount;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <TrendingDown className="h-8 w-8 text-red-500" />
          <div>
            <h1 className="text-base font-bold text-gray-900">Reimbursement Analyzer</h1>
            <p className="text-gray-600">Find underpaid Amazon reimbursements by comparing against your COGS data</p>
          </div>
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
        <h3 className="text-base font-semibold text-gray-900 mb-4">Upload Reimbursement CSV</h3>
        
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
            <p className="text-base font-medium text-gray-900">
              {dragOver ? 'Drop file here' : 'Upload reimbursement CSV'}
            </p>
            <p className="text-sm text-gray-500">
              Drag and drop your Amazon reimbursement CSV file here
            </p>
            <p className="text-xs text-gray-400">
              CSV files only • The system will analyze against your Google Sheets COGS data
            </p>
          </div>
          
          <input
            type="file"
            onChange={handleFileSelect}
            accept=".csv"
            className="hidden"
            id="reimbursement-upload"
            disabled={analyzing}
          />
          
          <label
            htmlFor="reimbursement-upload"
            className={`mt-4 inline-block px-4 py-2 bg-builders-500 text-white rounded-md hover:bg-builders-600 transition-colors duration-200 cursor-pointer ${
              analyzing ? 'opacity-50 cursor-not-allowed' : ''
            }`}
          >
            Choose CSV File
          </label>
        </div>

        {file && (
          <div className="mt-4 flex items-center justify-between p-3 bg-gray-50 rounded-md">
            <div className="flex items-center space-x-2">
              <FileText className="h-5 w-5 text-gray-500" />
              <span className="text-sm font-medium">{file.name}</span>
              <span className="text-xs text-gray-500">
                ({(file.size / 1024).toFixed(1)} KB)
              </span>
            </div>
            <button
              onClick={analyzeReimbursements}
              disabled={analyzing}
              className="px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {analyzing ? 'Analyzing...' : 'Analyze Reimbursements'}
            </button>
          </div>
        )}
      </div>

      {/* Results Summary */}
      {results && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="card bg-gradient-to-r from-red-500 to-red-600 text-white">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-red-100">Underpaid Reimbursements</p>
                <p className="text-base font-bold">{results.underpaid_count}</p>
              </div>
              <TrendingDown className="h-8 w-8 text-red-200" />
            </div>
          </div>

          <div className="card bg-gradient-to-r from-orange-500 to-orange-600 text-white">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-orange-100">Total Shortfall</p>
                <p className="text-base font-bold">${results.total_shortfall}</p>
              </div>
              <DollarSign className="h-8 w-8 text-orange-200" />
            </div>
          </div>

          <div className="card bg-gradient-to-r from-blue-500 to-blue-600 text-white">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-blue-100">COGS Records Found</p>
                <p className="text-base font-bold">{results.max_cogs_count}</p>
              </div>
              <Activity className="h-8 w-8 text-blue-200" />
            </div>
          </div>
        </div>
      )}

      {/* Detailed Results */}
      {results && results.underpaid_reimbursements && results.underpaid_reimbursements.length > 0 && (
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-base font-semibold text-gray-900">Underpaid Reimbursements</h3>
            <button
              onClick={downloadResults}
              className="inline-flex items-center px-4 py-2 bg-green-500 text-white rounded-md hover:bg-green-600 transition-colors duration-200"
            >
              <Download className="w-4 h-4 mr-2" />
              Download CSV
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    ASIN
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Product Name
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Reason
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Reimbursed
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Your COGS
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Shortfall
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {results.underpaid_reimbursements.map((item, index) => (
                  <tr key={index} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                      {item.asin}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-900 max-w-xs truncate">
                      {item['product-name']}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {item.reason}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {formatCurrency(item['amount-per-unit'])}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-green-600">
                      ${item.highest_cogs?.toFixed(2)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-red-600">
                      ${item.shortfall_amount?.toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Instructions */}
      <div className="card bg-blue-50 border border-blue-200">
        <div className="flex items-start space-x-3">
          <AlertCircle className="h-5 w-5 text-blue-500 mt-0.5" />
          <div>
            <h4 className="text-sm font-medium text-blue-900">How to use the Reimbursement Analyzer</h4>
            <div className="text-sm text-blue-700 mt-1 space-y-1">
              <p>• Download your reimbursement report from Amazon Seller Central</p>
              <p>• Upload the CSV file using the area above</p>
              <p>• The system compares reimbursement amounts against your highest COGS from Google Sheets</p>
              <p>• View underpaid items and download the results for Amazon appeals</p>
              <p>• Make sure your Google Sheets contain ASIN and COGS columns</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ReimbursementAnalyzer;