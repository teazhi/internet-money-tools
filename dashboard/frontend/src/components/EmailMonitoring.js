import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  Mail, 
  Plus, 
  Trash2, 
  TestTube, 
  CheckCircle, 
  XCircle, 
  AlertCircle,
  Settings,
  Webhook,
  Clock,
  Eye,
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
  const [showConfigForm, setShowConfigForm] = useState(false);
  const [showRuleForm, setShowRuleForm] = useState(false);
  const [configForm, setConfigForm] = useState({
    email_address: '',
    imap_server: '',
    imap_port: 993,
    username: '',
    password: '',
    is_active: true
  });
  const [ruleForm, setRuleForm] = useState({
    rule_name: '',
    sender_filter: '',
    subject_filter: '',
    content_filter: '',
    webhook_url: '',
    is_active: true
  });
  
  const [testResult, setTestResult] = useState(null);
  const [testLoading, setTestLoading] = useState(false);
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

  const handleSaveConfig = async () => {
    try {
      await axios.post('/api/email-monitoring/config', configForm, { withCredentials: true });
      setShowConfigForm(false);
      setConfigForm({
        email_address: '',
        imap_server: '',
        imap_port: 993,
        username: '',
        password: '',
        is_active: true
      });
      fetchData();
    } catch (error) {
      console.error('Error saving email config:', error);
      alert('Failed to save email configuration');
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
        webhook_url: '',
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

  const handleTestConnection = async (config = null) => {
    const testConfig = config || configForm;
    setTestLoading(true);
    setTestResult(null);
    
    try {
      const response = await axios.post('/api/email-monitoring/test', testConfig, { withCredentials: true });
      setTestResult({ success: true, message: response.data.message });
    } catch (error) {
      setTestResult({ 
        success: false, 
        message: error.response?.data?.message || 'Connection test failed' 
      });
    } finally {
      setTestLoading(false);
    }
  };

  const handleQuickSetup = async (webhookUrl) => {
    try {
      const response = await axios.post('/api/email-monitoring/quick-setup', { webhook_url: webhookUrl }, { withCredentials: true });
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

  const getCommonEmailServers = () => [
    { name: 'Gmail', server: 'imap.gmail.com', port: 993 },
    { name: 'Outlook/Hotmail', server: 'outlook.office365.com', port: 993 },
    { name: 'Yahoo', server: 'imap.mail.yahoo.com', port: 993 },
    { name: 'iCloud', server: 'imap.mail.me.com', port: 993 }
  ];

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
                  onClick={() => setShowConfigForm(true)}
                  className="flex items-center px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm"
                >
                  <Plus className="h-4 w-4 mr-2" />
                  Add Email Account
                </button>
              </div>

              {configs.length === 0 ? (
                <div className="text-center py-12">
                  <Mail className="h-12 w-12 text-gray-300 mx-auto mb-4" />
                  <p className="text-gray-500 mb-4">No email accounts configured</p>
                  <button
                    onClick={() => setShowConfigForm(true)}
                    className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
                  >
                    Add Your First Email Account
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
                            {config.imap_server}:{config.imap_port} • {config.username}
                          </div>
                          {config.last_checked && (
                            <div className="text-xs text-gray-400 mt-1">
                              Last checked: {new Date(config.last_checked).toLocaleString()}
                            </div>
                          )}
                        </div>
                        <div className="flex items-center space-x-2">
                          <div className={`w-2 h-2 rounded-full ${config.is_active ? 'bg-green-500' : 'bg-gray-400'}`}></div>
                          <button
                            onClick={() => handleTestConnection(config)}
                            disabled={testLoading}
                            className="px-3 py-1 text-sm border border-gray-300 rounded-md hover:bg-gray-50"
                          >
                            <TestTube className="h-3 w-3 mr-1 inline" />
                            Test
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Email Configuration Form Modal */}
              {showConfigForm && (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
                  <div className="bg-white rounded-lg max-w-md w-full mx-4 p-6">
                    <h3 className="text-lg font-medium mb-4">Add Email Account</h3>
                    
                    <div className="space-y-4">
                      <div>
                        <label className="block text-sm font-medium mb-1">Email Address</label>
                        <input
                          type="email"
                          value={configForm.email_address}
                          onChange={(e) => setConfigForm({...configForm, email_address: e.target.value})}
                          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                          placeholder="your-email@example.com"
                        />
                      </div>
                      
                      <div>
                        <label className="block text-sm font-medium mb-1">IMAP Server</label>
                        <select
                          value={configForm.imap_server}
                          onChange={(e) => {
                            const server = getCommonEmailServers().find(s => s.server === e.target.value);
                            setConfigForm({
                              ...configForm, 
                              imap_server: e.target.value,
                              imap_port: server ? server.port : 993
                            });
                          }}
                          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                        >
                          <option value="">Select email provider or enter custom</option>
                          {getCommonEmailServers().map((server, index) => (
                            <option key={index} value={server.server}>
                              {server.name} ({server.server})
                            </option>
                          ))}
                        </select>
                        {!getCommonEmailServers().find(s => s.server === configForm.imap_server) && (
                          <input
                            type="text"
                            value={configForm.imap_server}
                            onChange={(e) => setConfigForm({...configForm, imap_server: e.target.value})}
                            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm mt-2"
                            placeholder="imap.example.com"
                          />
                        )}
                      </div>
                      
                      <div>
                        <label className="block text-sm font-medium mb-1">Port</label>
                        <input
                          type="number"
                          value={configForm.imap_port}
                          onChange={(e) => setConfigForm({...configForm, imap_port: parseInt(e.target.value)})}
                          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                        />
                      </div>
                      
                      <div>
                        <label className="block text-sm font-medium mb-1">Username</label>
                        <input
                          type="text"
                          value={configForm.username}
                          onChange={(e) => setConfigForm({...configForm, username: e.target.value})}
                          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                          placeholder="Usually your email address"
                        />
                      </div>
                      
                      <div>
                        <label className="block text-sm font-medium mb-1">Password</label>
                        <input
                          type="password"
                          value={configForm.password}
                          onChange={(e) => setConfigForm({...configForm, password: e.target.value})}
                          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                          placeholder="Email password or app password"
                        />
                        <p className="text-xs text-gray-500 mt-1">
                          For Gmail, use an App Password instead of your main password
                        </p>
                      </div>
                      
                      {testResult && (
                        <div className={`p-3 rounded-md text-sm ${
                          testResult.success ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'
                        }`}>
                          {testResult.message}
                        </div>
                      )}
                    </div>
                    
                    <div className="flex justify-between mt-6">
                      <button
                        onClick={() => handleTestConnection()}
                        disabled={testLoading || !configForm.email_address || !configForm.imap_server || !configForm.password}
                        className="px-4 py-2 text-blue-600 border border-blue-600 rounded-md hover:bg-blue-50 text-sm disabled:opacity-50"
                      >
                        {testLoading ? 'Testing...' : 'Test Connection'}
                      </button>
                      <div className="space-x-3">
                        <button
                          onClick={() => {
                            setShowConfigForm(false);
                            setTestResult(null);
                          }}
                          className="px-4 py-2 text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50 text-sm"
                        >
                          Cancel
                        </button>
                        <button
                          onClick={handleSaveConfig}
                          disabled={!configForm.email_address || !configForm.imap_server || !configForm.password}
                          className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm disabled:opacity-50"
                        >
                          <Save className="h-4 w-4 mr-2 inline" />
                          Save
                        </button>
                      </div>
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
                          <span className="text-xs text-gray-500 truncate">{rule.webhook_url}</span>
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
                      
                      <div>
                        <label className="block text-sm font-medium mb-1">Webhook URL *</label>
                        <input
                          type="url"
                          value={ruleForm.webhook_url}
                          onChange={(e) => setRuleForm({...ruleForm, webhook_url: e.target.value})}
                          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                          placeholder="https://hooks.slack.com/..."
                        />
                        <p className="text-xs text-gray-500 mt-1">
                          Discord webhook, Slack webhook, or any URL that accepts POST requests
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
                        disabled={!ruleForm.rule_name || !ruleForm.webhook_url}
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