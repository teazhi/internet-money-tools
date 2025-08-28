import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  Mail, 
  Plus, 
  Trash2, 
  CheckCircle, 
  XCircle, 
  AlertCircle,
  Webhook,
  Save,
  RefreshCw
} from 'lucide-react';

const EmailMonitoring = () => {
  const [configs, setConfigs] = useState([]);
  const [rules, setRules] = useState([]);
  const [status, setStatus] = useState({});
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');
  
  // Form states
  const [showRuleForm, setShowRuleForm] = useState(false);
  const [showOAuthForm, setShowOAuthForm] = useState(false);
  const [oauthForm, setOauthForm] = useState({
    email_address: '',
    auth_code: '',
    is_active: true
  });
  const [ruleForm, setRuleForm] = useState({
    rule_name: '',
    sender_filter: '',
    subject_filter: '',
    content_filter: '',
    is_active: true
  });
  const [oauthUrl, setOauthUrl] = useState(null);
  const [oauthLoading, setOauthLoading] = useState(false);
  
  const [checkingNow, setCheckingNow] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [configsRes, rulesRes, statusRes] = await Promise.all([
        axios.get('/api/email-monitoring/config', { withCredentials: true }),
        axios.get('/api/email-monitoring/rules', { withCredentials: true }),
        axios.get('/api/email-monitoring/status', { withCredentials: true })
      ]);
      
      setConfigs(configsRes.data.configs || []);
      setRules(rulesRes.data.rules || []);
      setStatus(statusRes.data);
    } catch (error) {
      console.error('Error fetching email monitoring data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleOAuthSetup = async () => {
    try {
      setOauthLoading(true);
      await axios.post('/api/email-monitoring/oauth-setup', oauthForm, { withCredentials: true });
      alert('OAuth setup completed successfully!');
      setShowOAuthForm(false);
      setOauthForm({
        email_address: '',
        auth_code: '',
        is_active: true
      });
      setOauthUrl(null);
      fetchData();
    } catch (error) {
      console.error('Error setting up OAuth:', error);
      alert(error.response?.data?.error || 'Failed to setup OAuth authentication');
    } finally {
      setOauthLoading(false);
    }
  };

  const handleGetOAuthUrl = async () => {
    try {
      const response = await axios.get('/api/email-monitoring/oauth-url', { withCredentials: true });
      setOauthUrl(response.data.auth_url);
    } catch (error) {
      console.error('Error getting OAuth URL:', error);
      alert('Failed to get authorization URL');
    }
  };

  const handleSaveRule = async () => {
    try {
      await axios.post('/api/email-monitoring/rules', ruleForm, { withCredentials: true });
      setShowRuleForm(false);
      setRuleForm({
        rule_name: '',
        sender_filter: '',
        subject_filter: '',
        content_filter: '',
        is_active: true
      });
      fetchData();
    } catch (error) {
      console.error('Error saving email rule:', error);
      alert('Failed to save email rule');
    }
  };

  const handleDeleteRule = async (ruleId) => {
    if (!window.confirm('Are you sure you want to delete this rule?')) return;
    
    try {
      await axios.delete(`/api/email-monitoring/rules/${ruleId}`, { withCredentials: true });
      fetchData();
    } catch (error) {
      console.error('Error deleting rule:', error);
      alert('Failed to delete rule');
    }
  };

  // OAuth configs don't need connection testing - OAuth flow validates the connection

  const handleQuickSetup = async (webhookUrl) => {
    try {
      await axios.post('/api/email-monitoring/quick-setup', { webhook_url: webhookUrl }, { withCredentials: true });
      alert('Yankee Candle refund monitoring rule created successfully!');
      fetchData();
    } catch (error) {
      console.error('Error creating quick setup:', error);
      alert('Failed to create Yankee Candle rule');
    }
  };

  const handleCheckNow = async () => {
    try {
      setCheckingNow(true);
      const response = await axios.post('/api/email-monitoring/check-now', {}, { withCredentials: true });
      alert(response.data.message);
      // Refresh status after a few seconds
      setTimeout(fetchData, 5000);
    } catch (error) {
      console.error('Error checking emails now:', error);
      alert(error.response?.data?.error || 'Failed to trigger email check');
    } finally {
      setCheckingNow(false);
    }
  };



  if (loading) {
    return (
      <div className="p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-gray-300 rounded w-64"></div>
          <div className="h-32 bg-gray-300 rounded"></div>
          <div className="h-32 bg-gray-300 rounded"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center">
            <Mail className="h-6 w-6 mr-2" />
            Email Monitoring
          </h1>
          <p className="text-gray-600 mt-1">Monitor emails for refunds and send webhook notifications</p>
        </div>
      </div>

      {/* Status Overview */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-medium">Service Status</h3>
          <button
            onClick={handleCheckNow}
            disabled={checkingNow || !status.service_running}
            className="flex items-center px-3 py-1.5 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <RefreshCw className={`h-3 w-3 mr-1.5 ${checkingNow ? 'animate-spin' : ''}`} />
            {checkingNow ? 'Checking...' : 'Check Now'}
          </button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="flex items-center space-x-3">
            <div className={`w-3 h-3 rounded-full ${status.service_running ? 'bg-green-500' : 'bg-gray-400'}`}></div>
            <span className="text-sm font-medium">
              {status.service_running ? 'Running' : 'Inactive'}
            </span>
          </div>
          <div className="text-sm">
            <span className="font-medium">{status.active_configs || 0}</span> Email Configs
          </div>
          <div className="text-sm">
            <span className="font-medium">{status.active_rules || 0}</span> Active Rules
          </div>
          <div className="text-sm">
            <span className="font-medium">{status.recent_logs?.length || 0}</span> Recent Alerts
          </div>
        </div>
        {status.service_running && (
          <div className="mt-4 pt-4 border-t border-gray-200">
            <p className="text-sm text-gray-600">
              Emails are automatically checked <span className="font-medium">once per day</span>.
              {configs.length > 0 && rules.length > 0 ? 
                ' The service is actively monitoring your configured email accounts.' :
                ' Configure email accounts and rules to start monitoring.'}
            </p>
          </div>
        )}
      </div>

      {/* Quick Setup for Yankee Candle */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
        <h3 className="text-lg font-medium text-blue-900 mb-2">Quick Setup: Yankee Candle Refunds</h3>
        <p className="text-blue-700 mb-4">
          Quickly set up monitoring for Yankee Candle refund emails from "reply@e.yankeecandle.com" 
          with subject "Here's your refund!"
        </p>
        <div className="flex space-x-3">
          <input
            type="url"
            placeholder="Enter your webhook URL"
            className="flex-1 px-3 py-2 border border-blue-300 rounded-md text-sm"
            onKeyPress={(e) => {
              if (e.key === 'Enter') {
                handleQuickSetup(e.target.value);
                e.target.value = '';
              }
            }}
          />
          <button
            onClick={(e) => {
              const input = e.target.parentElement.querySelector('input');
              if (input.value) {
                handleQuickSetup(input.value);
                input.value = '';
              }
            }}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm"
          >
            Create Rule
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="bg-white rounded-lg shadow">
        <div className="border-b border-gray-200">
          <nav className="flex space-x-8 px-6">
            {['overview', 'email-config', 'rules'].map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`py-4 px-1 border-b-2 font-medium text-sm ${
                  activeTab === tab
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                {tab === 'overview' && 'Overview'}
                {tab === 'email-config' && 'Email Configuration'}
                {tab === 'rules' && 'Monitoring Rules'}
              </button>
            ))}
          </nav>
        </div>

        <div className="p-6">
          {activeTab === 'overview' && (
            <div className="space-y-6">
              {/* Recent Activity */}
              <div>
                <h3 className="text-lg font-medium mb-4">Recent Activity</h3>
                {status.recent_logs && status.recent_logs.length > 0 ? (
                  <div className="space-y-2">
                    {status.recent_logs.map((log, index) => (
                      <div key={index} className="flex items-center justify-between p-3 bg-gray-50 rounded-md">
                        <div className="flex items-center space-x-3">
                          {log.webhook_sent ? (
                            <CheckCircle className="h-4 w-4 text-green-500" />
                          ) : (
                            <XCircle className="h-4 w-4 text-red-500" />
                          )}
                          <div>
                            <div className="font-medium text-sm">{log.subject}</div>
                            <div className="text-xs text-gray-500">{log.sender}</div>
                          </div>
                        </div>
                        <div className="text-xs text-gray-500">
                          {new Date(log.timestamp).toLocaleString()}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-gray-500 text-center py-8">No recent activity</p>
                )}
              </div>
            </div>
          )}

          {activeTab === 'email-config' && (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-medium">Email Configurations</h3>
                <button
                  onClick={() => setShowOAuthForm(true)}
                  className="flex items-center px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm"
                >
                  <Plus className="h-4 w-4 mr-2" />
                  Add Gmail Account (OAuth)
                </button>
              </div>

              {configs.length === 0 ? (
                <div className="text-center py-12">
                  <Mail className="h-12 w-12 text-gray-300 mx-auto mb-4" />
                  <p className="text-gray-500 mb-4">No email accounts configured</p>
                  <button
                    onClick={() => setShowOAuthForm(true)}
                    className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
                  >
                    Add Your First Gmail Account
                  </button>
                </div>
              ) : (
                <div className="grid gap-4">
                  {configs.map((config, index) => (
                    <div key={index} className="border rounded-lg p-4">
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="font-medium">{config.email_address}</div>
                          <div className="text-sm text-gray-500">
                            {config.auth_type === 'oauth' ? 'Gmail OAuth' : `${config.imap_server}:${config.imap_port} • ${config.username}`}
                          </div>
                          {config.last_checked && (
                            <div className="text-xs text-gray-400 mt-1">
                              Last checked: {new Date(config.last_checked).toLocaleString()}
                            </div>
                          )}
                        </div>
                        <div className="flex items-center space-x-2">
                          <div className={`w-2 h-2 rounded-full ${config.is_active ? 'bg-green-500' : 'bg-gray-400'}`}></div>
                          <span className="px-3 py-1 text-sm text-green-600 bg-green-50 rounded-md">
                            OAuth Configured
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* OAuth Configuration Form Modal */}
              {showOAuthForm && (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
                  <div className="bg-white rounded-lg max-w-md w-full mx-4 p-6">
                    <h3 className="text-lg font-medium mb-4">Add Gmail Account (OAuth)</h3>
                    
                    <div className="space-y-4">
                      <div>
                        <label className="block text-sm font-medium mb-1">Gmail Address</label>
                        <input
                          type="email"
                          value={oauthForm.email_address}
                          onChange={(e) => setOauthForm({...oauthForm, email_address: e.target.value})}
                          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                          placeholder="your-gmail@gmail.com"
                        />
                      </div>
                      
                      <div>
                        <label className="block text-sm font-medium mb-2">Step 1: Authorize Access</label>
                        <p className="text-sm text-gray-600 mb-3">
                          Click the button below to get your authorization URL, then visit it to grant access.
                        </p>
                        <button
                          onClick={handleGetOAuthUrl}
                          disabled={!oauthForm.email_address}
                          className="w-full px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm disabled:opacity-50"
                        >
                          Get Authorization URL
                        </button>
                        
                        {oauthUrl && (
                          <div className="mt-3 p-3 bg-blue-50 rounded-md">
                            <p className="text-sm text-blue-700 mb-2">Visit this URL to authorize:</p>
                            <a
                              href={oauthUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-sm text-blue-600 underline break-all hover:text-blue-800"
                            >
                              {oauthUrl}
                            </a>
                          </div>
                        )}
                      </div>
                      
                      <div>
                        <label className="block text-sm font-medium mb-1">Step 2: Authorization Code</label>
                        <input
                          type="text"
                          value={oauthForm.auth_code}
                          onChange={(e) => setOauthForm({...oauthForm, auth_code: e.target.value})}
                          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                          placeholder="Paste the authorization code here"
                        />
                        <p className="text-xs text-gray-500 mt-1">
                          After authorizing, copy and paste the code from the success page
                        </p>
                      </div>
                    </div>
                    
                    <div className="flex justify-end space-x-3 mt-6">
                      <button
                        onClick={() => {
                          setShowOAuthForm(false);
                          setOauthUrl(null);
                        }}
                        className="px-4 py-2 text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50 text-sm"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={handleOAuthSetup}
                        disabled={oauthLoading || !oauthForm.email_address || !oauthForm.auth_code}
                        className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm disabled:opacity-50"
                      >
                        <Save className="h-4 w-4 mr-2 inline" />
                        {oauthLoading ? 'Setting up...' : 'Complete Setup'}
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === 'rules' && (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-medium">Monitoring Rules</h3>
                <button
                  onClick={() => setShowRuleForm(true)}
                  className="flex items-center px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm"
                >
                  <Plus className="h-4 w-4 mr-2" />
                  Add Rule
                </button>
              </div>

              {rules.length === 0 ? (
                <div className="text-center py-12">
                  <AlertCircle className="h-12 w-12 text-gray-300 mx-auto mb-4" />
                  <p className="text-gray-500 mb-4">No monitoring rules configured</p>
                  <button
                    onClick={() => setShowRuleForm(true)}
                    className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
                  >
                    Create Your First Rule
                  </button>
                </div>
              ) : (
                <div className="grid gap-4">
                  {rules.map((rule, index) => (
                    <div key={index} className="border rounded-lg p-4">
                      <div className="flex items-center justify-between mb-2">
                        <div className="font-medium">{rule.rule_name}</div>
                        <div className="flex items-center space-x-2">
                          <div className={`w-2 h-2 rounded-full ${rule.is_active ? 'bg-green-500' : 'bg-gray-400'}`}></div>
                          <button
                            onClick={() => handleDeleteRule(rule.id)}
                            className="text-red-600 hover:text-red-800"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
                      </div>
                      
                      <div className="text-sm text-gray-600 space-y-1">
                        {rule.sender_filter && (
                          <div>Sender: <code className="bg-gray-100 px-1 rounded">{rule.sender_filter}</code></div>
                        )}
                        {rule.subject_filter && (
                          <div>Subject: <code className="bg-gray-100 px-1 rounded">{rule.subject_filter}</code></div>
                        )}
                        {rule.content_filter && (
                          <div>Content: <code className="bg-gray-100 px-1 rounded">{rule.content_filter}</code></div>
                        )}
                        <div className="flex items-center space-x-2 mt-2">
                          <Webhook className="h-3 w-3 text-gray-400" />
                          <span className="text-xs text-gray-500">Uses system webhook configuration</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Rule Form Modal */}
              {showRuleForm && (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
                  <div className="bg-white rounded-lg max-w-md w-full mx-4 p-6">
                    <h3 className="text-lg font-medium mb-4">Create Monitoring Rule</h3>
                    
                    <div className="space-y-4">
                      <div>
                        <label className="block text-sm font-medium mb-1">Rule Name</label>
                        <input
                          type="text"
                          value={ruleForm.rule_name}
                          onChange={(e) => setRuleForm({...ruleForm, rule_name: e.target.value})}
                          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                          placeholder="e.g., Yankee Candle Refunds"
                        />
                      </div>
                      
                      <div>
                        <label className="block text-sm font-medium mb-1">Sender Filter (optional)</label>
                        <input
                          type="text"
                          value={ruleForm.sender_filter}
                          onChange={(e) => setRuleForm({...ruleForm, sender_filter: e.target.value})}
                          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                          placeholder="reply@e.yankeecandle.com"
                        />
                      </div>
                      
                      <div>
                        <label className="block text-sm font-medium mb-1">Subject Filter (optional)</label>
                        <input
                          type="text"
                          value={ruleForm.subject_filter}
                          onChange={(e) => setRuleForm({...ruleForm, subject_filter: e.target.value})}
                          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                          placeholder="Here's your refund!"
                        />
                      </div>
                      
                      <div>
                        <label className="block text-sm font-medium mb-1">Content Filter (optional)</label>
                        <input
                          type="text"
                          value={ruleForm.content_filter}
                          onChange={(e) => setRuleForm({...ruleForm, content_filter: e.target.value})}
                          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                          placeholder="Text that must be in email body"
                        />
                      </div>
                      
                      <div className="p-3 bg-blue-50 rounded-md">
                        <p className="text-sm text-blue-700">
                          <strong>Note:</strong> Webhook notifications are configured by your administrator. 
                          All matching emails will be sent to the system webhook.
                        </p>
                      </div>
                    </div>
                    
                    <div className="flex justify-end space-x-3 mt-6">
                      <button
                        onClick={() => setShowRuleForm(false)}
                        className="px-4 py-2 text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50 text-sm"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={handleSaveRule}
                        disabled={!ruleForm.rule_name}
                        className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm disabled:opacity-50"
                      >
                        <Save className="h-4 w-4 mr-2 inline" />
                        Create Rule
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default EmailMonitoring;