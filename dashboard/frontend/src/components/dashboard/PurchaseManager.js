import React, { useState, useEffect, Component } from 'react';
import { 
  Plus, 
  ShoppingCart, 
  Package, 
  AlertTriangle,
  ExternalLink,
  Edit3,
  Save,
  X,
  CheckCircle,
  Clock,
  TrendingUp,
  Target,
  User,
  Users,
  ClipboardList,
  RefreshCw
} from 'lucide-react';
import axios from 'axios';
import { useAuth } from '../../contexts/AuthContext';

// Error Boundary Component
class FormErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('Form Error Boundary caught an error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="card">
          <div className="text-center py-8">
            <h3 className="text-lg font-semibold text-red-600 mb-2">Form Error</h3>
            <p className="text-sm text-gray-600 mb-4">
              The form encountered an error and couldn't render properly.
            </p>
            <button
              onClick={() => {
                this.setState({ hasError: false, error: null });
                if (this.props.onReset) this.props.onReset();
              }}
              className="btn-primary"
            >
              Try Again
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

const PurchaseManager = () => {
  const { user } = useAuth();
  const [purchases, setPurchases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [editingRow, setEditingRow] = useState(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [showBulkForm, setShowBulkForm] = useState(false);
  const [bulkInput, setBulkInput] = useState('');
  const [bulkParsedItems, setBulkParsedItems] = useState([]);
  const [bulkProcessing, setBulkProcessing] = useState(false);
  const [newPurchase, setNewPurchase] = useState({
    buyLink: '',
    sellLink: '',
    name: '',
    price: '',
    targetQuantity: '',
    notes: ''
  });

  // Determine if user is VA (sub-user) or main user
  const isVA = user?.user_type === 'sub' || user?.user_type === 'va';
  const isMainUser = !user?.user_type || user?.user_type === 'main';
  
  // Debug logging
  console.log('Purchase Manager - User Info:', {
    user_type: user?.user_type,
    discord_id: user?.discord_id,
    isVA,
    isMainUser
  });

  // Error boundary for debugging
  useEffect(() => {
    window.addEventListener('error', (e) => {
      console.error('Global error caught:', e);
    });
    return () => window.removeEventListener('error', () => {});
  }, []);

  useEffect(() => {
    fetchPurchases();
  }, []);

  const fetchPurchases = async () => {
    try {
      setLoading(true);
      const response = await axios.get('/api/purchases', {
        withCredentials: true
      });
      
      if (response.data.success) {
        setPurchases(response.data.purchases);
      } else {
        setError('Failed to load purchases');
      }
    } catch (err) {
      console.error('Error fetching purchases:', err);
      setError('Failed to load purchases. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const extractASIN = (amazonUrl) => {
    const match = amazonUrl.match(/\/dp\/([A-Z0-9]{10})/i);
    return match ? match[1] : '';
  };

  const parseBulkInput = (input) => {
    const lines = input.trim().split('\n');
    const parsedItems = [];
    
    for (const line of lines) {
      const trimmedLine = line.trim();
      if (!trimmedLine) continue;
      
      // Find all URLs in the line
      const urlRegex = /(https?:\/\/[^\s]+)/g;
      const urls = trimmedLine.match(urlRegex) || [];
      
      if (urls.length >= 2) {
        // Identify source and Amazon URLs
        let sourceUrl = '';
        let amazonUrl = '';
        
        for (const url of urls) {
          if (url.includes('amazon.com/dp/')) {
            amazonUrl = url;
          } else {
            sourceUrl = url; // First non-Amazon URL is the source
          }
        }
        
        if (sourceUrl && amazonUrl) {
          const asin = extractASIN(amazonUrl);
          parsedItems.push({
            buyLink: sourceUrl,
            sellLink: amazonUrl,
            asin: asin,
            name: `Product ${asin}`, // Will be auto-fetched
            price: '',
            targetQuantity: '',
            notes: ''
          });
        }
      }
    }
    
    return parsedItems;
  };

  const handleBulkParse = () => {
    const items = parseBulkInput(bulkInput);
    setBulkParsedItems(items);
    
    if (items.length === 0) {
      setError('No valid source/Amazon link pairs found. Make sure each line has both a source URL and an Amazon URL.');
    } else {
      setError('');
    }
  };

  const submitBulkItems = async () => {
    setBulkProcessing(true);
    setError('');
    let successCount = 0;
    
    try {
      for (const item of bulkParsedItems) {
        // Get default values from form inputs
        const defaultPrice = document.getElementById('bulk-default-price')?.value || '0';
        const defaultQuantity = document.getElementById('bulk-default-quantity')?.value || '50';
        const defaultNotes = document.getElementById('bulk-default-notes')?.value || '';
        
        const purchaseData = {
          ...item,
          price: item.price || defaultPrice,
          targetQuantity: item.targetQuantity || defaultQuantity,
          notes: item.notes || defaultNotes
        };
        
        const response = await axios.post('/api/purchases', purchaseData, {
          withCredentials: true
        });
        
        if (response.data.success) {
          successCount++;
        }
      }
      
      if (successCount === bulkParsedItems.length) {
        // All successful - refresh and close
        await fetchPurchases();
        setBulkInput('');
        setBulkParsedItems([]);
        setShowBulkForm(false);
        setError('');
      } else {
        setError(`Added ${successCount} of ${bulkParsedItems.length} items. Some may have failed.`);
      }
    } catch (err) {
      setError('Failed to add some items. Please try again.');
    } finally {
      setBulkProcessing(false);
    }
  };

  const getStockStatus = (currentStock, spm, targetQuantity) => {
    if (!currentStock || currentStock === 0) {
      return { status: 'out-of-stock', color: 'bg-red-100 text-red-800', text: 'Out of Stock' };
    }
    
    const daysOfStock = spm > 0 ? Math.floor(currentStock / (spm / 30)) : 999;
    
    if (daysOfStock <= 15) {
      return { status: 'low-stock', color: 'bg-yellow-100 text-yellow-800', text: `Low Stock (${daysOfStock}d)` };
    }
    
    if (currentStock >= targetQuantity) {
      return { status: 'well-stocked', color: 'bg-green-100 text-green-800', text: 'Well Stocked' };
    }
    
    return { status: 'needs-restock', color: 'bg-blue-100 text-blue-800', text: 'Needs Restock' };
  };

  const addNewPurchase = async () => {
    try {
      // Safety check for newPurchase object
      if (!newPurchase || typeof newPurchase !== 'object') {
        setError('Form data is invalid. Please refresh the page and try again.');
        return;
      }
      
      // Validate required fields
      if (!newPurchase.buyLink || !newPurchase.sellLink) {
        setError('Please provide both source and Amazon links');
        return;
      }
      
      if (!newPurchase.name) {
        setError('Please provide a product name');
        return;
      }
      
      console.log('Submitting purchase request:', newPurchase);
      
      const response = await axios.post('/api/purchases', newPurchase, {
        withCredentials: true
      });
      
      if (response.data.success) {
        console.log('Purchase request created successfully');
        
        // Add the new purchase to the list
        const newPurchaseItem = response.data.purchase;
        setPurchases(prevPurchases => [newPurchaseItem, ...prevPurchases]);
        
        // Reset form
        setNewPurchase({
          buyLink: '',
          sellLink: '',
          name: '',
          price: '',
          targetQuantity: '',
          notes: ''
        });
        setShowAddForm(false);
        setError('');
      } else {
        setError(response.data.message || 'Failed to add purchase');
      }
    } catch (err) {
      console.error('Error adding purchase:', err);
      if (err.response?.data?.message) {
        setError(err.response.data.message);
      } else {
        setError('Failed to add purchase. Please try again.');
      }
    }
  };

  const updatePurchase = async (id, updates) => {
    try {
      const response = await axios.put(`/api/purchases/${id}`, updates, {
        withCredentials: true
      });
      
      if (response.data.success) {
        setPurchases(purchases.map(p => 
          p.id === id ? { ...p, ...updates } : p
        ));
        setEditingRow(null);
      } else {
        setError('Failed to update purchase');
      }
    } catch (err) {
      setError('Failed to update purchase. Please try again.');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-amber-600 mx-auto"></div>
          <p className="mt-2 text-sm text-gray-600">Loading purchases...</p>
        </div>
      </div>
    );
  }

  // Safety check
  if (!user) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <p className="text-sm text-gray-600">User session not found. Please refresh the page.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className={`rounded-lg p-6 text-white ${
        isVA 
          ? 'bg-gradient-to-r from-blue-500 to-blue-600' 
          : 'bg-gradient-to-r from-green-500 to-green-600'
      }`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-white/20 rounded-lg">
              {isVA ? <ClipboardList className="h-6 w-6" /> : <ShoppingCart className="h-6 w-6" />}
            </div>
            <div>
              <h1 className="text-2xl font-bold">
                {isVA ? 'Purchase Tasks' : 'Purchase Manager'}
              </h1>
              <p className={isVA ? 'text-blue-100' : 'text-green-100'}>
                {isVA 
                  ? 'Review and complete purchase requests' 
                  : 'Create purchase requests for your VA team'
                }
              </p>
            </div>
          </div>
          
          {/* Role indicator */}
          <div className="flex items-center space-x-3">
            <div className="flex items-center space-x-2 bg-white/20 px-3 py-1 rounded-lg">
              {isVA ? <User className="h-4 w-4" /> : <Users className="h-4 w-4" />}
              <span className="text-sm font-medium">
                {isVA ? 'VA Mode' : 'Manager Mode'}
              </span>
            </div>
            
            {isMainUser && (
              <div className="flex space-x-2">
                <button
                  onClick={() => setShowBulkForm(true)}
                  className="bg-white/20 hover:bg-white/30 px-4 py-2 rounded-lg flex items-center transition-colors"
                >
                  <ClipboardList className="h-4 w-4 mr-2" />
                  Bulk Import
                </button>
                <button
                  type="button"
                  onClick={() => {
                    console.log('Opening single request form');
                    try {
                      // Reset any previous errors first
                      setError('');
                      
                      // Ensure newPurchase is properly initialized
                      setNewPurchase({
                        buyLink: '',
                        sellLink: '',
                        name: '',
                        price: '',
                        targetQuantity: '',
                        notes: ''
                      });
                      
                      // Close bulk form if open and show single form
                      setShowBulkForm(false);
                      setShowAddForm(true);
                      
                      console.log('Single request form opened successfully');
                    } catch (err) {
                      console.error('Error opening form:', err);
                      setError('Failed to open form. Please refresh the page and try again.');
                    }
                  }}
                  className="bg-white/20 hover:bg-white/30 px-4 py-2 rounded-lg flex items-center transition-colors"
                >
                  <Plus className="h-4 w-4 mr-2" />
                  Single Request
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-center">
            <AlertTriangle className="h-5 w-5 text-red-500 mr-2" />
            <span className="text-red-800">{error}</span>
          </div>
        </div>
      )}

      {/* Bulk Import Form - Main User Only */}
      {showBulkForm && isMainUser && (
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="heading-sm">Bulk Import Purchase Requests</h3>
            <button
              onClick={() => {
                setShowBulkForm(false);
                setBulkInput('');
                setBulkParsedItems([]);
                setError('');
              }}
              className="text-gray-400 hover:text-gray-600"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
          
          <div className="space-y-4">
            <div>
              <label className="label-text">Paste Source and Amazon Links</label>
              <p className="text-xs text-gray-500 mb-2">
                Each line should contain a source URL and an Amazon URL separated by spaces or tabs
              </p>
              <textarea
                value={bulkInput}
                onChange={(e) => setBulkInput(e.target.value)}
                placeholder={`https://walmart.com/item123    https://amazon.com/dp/B001234567
https://target.com/item456    https://amazon.com/dp/B002345678
...`}
                rows="10"
                className="input-field font-mono text-sm"
              />
            </div>
            
            {bulkInput && (
              <div className="flex justify-end">
                <button
                  onClick={handleBulkParse}
                  className="btn-secondary"
                >
                  Parse Links ({bulkInput.split('\n').filter(line => line.trim()).length} lines)
                </button>
              </div>
            )}
            
            {/* Parsed Items Preview */}
            {bulkParsedItems.length > 0 && (
              <>
                <div className="border-t pt-4">
                  <h4 className="heading-sm mb-3">Found {bulkParsedItems.length} Items</h4>
                  
                  {/* Default Settings */}
                  <div className="bg-gray-50 rounded-lg p-4 mb-4">
                    <h5 className="text-sm font-medium text-gray-700 mb-3">Default Settings for All Items</h5>
                    <div className="grid md:grid-cols-3 gap-3">
                      <div>
                        <label className="label-text">Default Price</label>
                        <input
                          id="bulk-default-price"
                          type="number"
                          step="0.01"
                          defaultValue="0"
                          placeholder="0.00"
                          className="input-field"
                        />
                      </div>
                      <div>
                        <label className="label-text">Default Target Quantity</label>
                        <input
                          id="bulk-default-quantity"
                          type="number"
                          defaultValue="50"
                          placeholder="50"
                          className="input-field"
                        />
                      </div>
                      <div>
                        <label className="label-text">Default Notes</label>
                        <input
                          id="bulk-default-notes"
                          type="text"
                          placeholder="Instructions for VA..."
                          className="input-field"
                        />
                      </div>
                    </div>
                  </div>
                  
                  {/* Items List */}
                  <div className="space-y-2 max-h-64 overflow-y-auto">
                    {bulkParsedItems.map((item, index) => (
                      <div key={index} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg text-sm">
                        <div className="flex-1">
                          <div className="font-medium">ASIN: {item.asin}</div>
                          <div className="text-xs text-gray-500 truncate">
                            Source: {new URL(item.buyLink).hostname}
                          </div>
                        </div>
                        <div className="flex space-x-2">
                          <a
                            href={item.buyLink}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-600 hover:text-blue-800"
                          >
                            <ExternalLink className="h-4 w-4" />
                          </a>
                          <a
                            href={item.sellLink}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-orange-600 hover:text-orange-800"
                          >
                            <ExternalLink className="h-4 w-4" />
                          </a>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                
                <div className="flex space-x-3">
                  <button
                    onClick={submitBulkItems}
                    disabled={bulkProcessing}
                    className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
                  >
                    {bulkProcessing ? (
                      <>
                        <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                        Processing...
                      </>
                    ) : (
                      <>
                        <CheckCircle className="h-4 w-4 mr-2" />
                        Create {bulkParsedItems.length} Requests
                      </>
                    )}
                  </button>
                  <button
                    onClick={() => {
                      setBulkParsedItems([]);
                      setBulkInput('');
                    }}
                    className="btn-secondary"
                  >
                    Clear
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* Add New Purchase Form - Main User Only */}
      {showAddForm && isMainUser && (
        <FormErrorBoundary onReset={() => {
          setShowAddForm(false);
          setNewPurchase({
            buyLink: '',
            sellLink: '',
            name: '',
            price: '',
            targetQuantity: '',
            notes: ''
          });
          setError('');
        }}>
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h3 className="heading-sm">Create Purchase Request</h3>
              <button
                type="button"
                onClick={() => {
                  setShowAddForm(false);
                  setError('');
                }}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            
            <form onSubmit={(e) => {
              e.preventDefault();
              addNewPurchase();
            }}>
              <div className="grid md:grid-cols-2 gap-4">
                <div>
                  <label className="label-text">Buy Link (Source)</label>
                  <input
                    type="url"
                    value={newPurchase?.buyLink || ''}
                    onChange={(e) => setNewPurchase(prev => ({...prev, buyLink: e.target.value}))}
                    placeholder="https://www.walmart.com/..."
                    className="input-field"
                  />
                </div>
                
                <div>
                  <label className="label-text">Amazon Sell Link</label>
                  <input
                    type="url"
                    value={newPurchase?.sellLink || ''}
                    onChange={(e) => setNewPurchase(prev => ({...prev, sellLink: e.target.value}))}
                    placeholder="https://www.amazon.com/dp/..."
                    className="input-field"
                  />
                </div>
                
                <div className="md:col-span-2">
                  <label className="label-text">Product Name</label>
                  <input
                    type="text"
                    value={newPurchase?.name || ''}
                    onChange={(e) => setNewPurchase(prev => ({...prev, name: e.target.value}))}
                    placeholder="Product name"
                    className="input-field"
                  />
                </div>
                
                <div>
                  <label className="label-text">Source Price</label>
                  <input
                    type="number"
                    step="0.01"
                    value={newPurchase?.price || ''}
                    onChange={(e) => setNewPurchase(prev => ({...prev, price: e.target.value}))}
                    placeholder="0.00"
                    className="input-field"
                  />
                </div>
                
                <div>
                  <label className="label-text">Target Quantity</label>
                  <input
                    type="number"
                    value={newPurchase?.targetQuantity || ''}
                    onChange={(e) => setNewPurchase(prev => ({...prev, targetQuantity: e.target.value}))}
                    placeholder="50"
                    className="input-field"
                  />
                </div>
                
                <div className="md:col-span-2">
                  <label className="label-text">Instructions for VA</label>
                  <textarea
                    value={newPurchase?.notes || ''}
                    onChange={(e) => setNewPurchase(prev => ({...prev, notes: e.target.value}))}
                    placeholder="Special instructions, preferences, or notes for your VA..."
                    rows="3"
                    className="input-field"
                  />
                </div>
              </div>
              
              <div className="flex space-x-3 mt-4">
                <button
                  type="submit"
                  className="btn-primary"
                >
                  Create Request
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowAddForm(false);
                    setError('');
                  }}
                  className="btn-secondary"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </FormErrorBoundary>
      )}

      {/* Purchase List */}
      <div className="card">
        <h3 className="heading-sm mb-4">
          {isVA ? 'Purchase Tasks Queue' : 'Purchase Requests'}
        </h3>
        
        {purchases.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <Package className="h-12 w-12 mx-auto mb-4 text-gray-300" />
            <p>{isVA ? 'No purchase tasks assigned' : 'No purchase requests created'}</p>
            <p className="text-sm">
              {isVA 
                ? 'Check back later for new tasks from your manager' 
                : 'Create your first purchase request to get started'
              }
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-3 px-4 font-medium text-gray-600">Product</th>
                  <th className="text-left py-3 px-4 font-medium text-gray-600">Stock Status</th>
                  <th className="text-left py-3 px-4 font-medium text-gray-600">Current Inventory</th>
                  <th className="text-left py-3 px-4 font-medium text-gray-600">Target Qty</th>
                  {isVA && <th className="text-left py-3 px-4 font-medium text-gray-600">Progress</th>}
                  {isMainUser && <th className="text-left py-3 px-4 font-medium text-gray-600">VA Progress</th>}
                  <th className="text-left py-3 px-4 font-medium text-gray-600">
                    {isVA ? 'Purchase Actions' : 'Status'}
                  </th>
                </tr>
              </thead>
              <tbody>
                {purchases.map((purchase) => {
                  const asin = extractASIN(purchase.sellLink);
                  const stockStatus = getStockStatus(
                    purchase.currentStock, 
                    purchase.spm, 
                    purchase.targetQuantity
                  );
                  
                  return (
                    <tr key={purchase.id} className="border-b border-gray-100 hover:bg-gray-50">
                      <td className="py-3 px-4">
                        <div className="space-y-1">
                          <p className="font-medium text-gray-900 text-sm">{purchase.name}</p>
                          <div className="flex space-x-2 text-xs">
                            <span className="text-gray-500">ASIN: {asin}</span>
                            <span className="text-green-600">${purchase.price}</span>
                          </div>
                          <div className="flex space-x-2">
                            <a
                              href={purchase.buyLink}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-blue-600 hover:text-blue-800 text-xs flex items-center"
                            >
                              <ExternalLink className="h-3 w-3 mr-1" />
                              Source
                            </a>
                            <a
                              href={purchase.sellLink}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-orange-600 hover:text-orange-800 text-xs flex items-center"
                            >
                              <ExternalLink className="h-3 w-3 mr-1" />
                              Amazon
                            </a>
                          </div>
                        </div>
                      </td>
                      
                      <td className="py-3 px-4">
                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${stockStatus.color}`}>
                          {stockStatus.text}
                        </span>
                      </td>
                      
                      <td className="py-3 px-4">
                        <div className="text-sm">
                          <div className="flex items-center space-x-2">
                            <Package className="h-4 w-4 text-gray-400" />
                            <span>{purchase.currentStock || 0} units</span>
                          </div>
                          {purchase.spm > 0 && (
                            <div className="flex items-center space-x-2 text-xs text-gray-500">
                              <TrendingUp className="h-3 w-3" />
                              <span>{purchase.spm}/month</span>
                            </div>
                          )}
                        </div>
                      </td>
                      
                      <td className="py-3 px-4">
                        <div className="flex items-center space-x-2 text-sm">
                          <Target className="h-4 w-4 text-gray-400" />
                          <span>{purchase.targetQuantity} units</span>
                        </div>
                      </td>
                      
                      {/* Progress Column */}
                      {isVA && (
                        <td className="py-3 px-4">
                          <div className="space-y-2">
                            <div className="text-sm">
                              <span className="font-medium">{purchase.purchased || 0}</span>
                              <span className="text-gray-500">/{purchase.targetQuantity} purchased</span>
                            </div>
                            {editingRow === purchase.id ? (
                              <div className="flex space-x-2">
                                <input
                                  type="number"
                                  min="0"
                                  max={purchase.targetQuantity}
                                  defaultValue={purchase.purchased || 0}
                                  className="w-20 px-2 py-1 border rounded text-sm"
                                  onKeyPress={(e) => {
                                    if (e.key === 'Enter') {
                                      const newAmount = parseInt(e.target.value);
                                      updatePurchase(purchase.id, { purchased: newAmount });
                                    }
                                  }}
                                />
                                <button
                                  onClick={() => setEditingRow(null)}
                                  className="text-green-600 hover:text-green-800 p-1"
                                >
                                  <Save className="h-3 w-3" />
                                </button>
                              </div>
                            ) : (
                              <div className="w-full bg-gray-200 rounded-full h-2">
                                <div 
                                  className="bg-blue-600 h-2 rounded-full" 
                                  style={{
                                    width: `${Math.min(100, (purchase.purchased || 0) / purchase.targetQuantity * 100)}%`
                                  }}
                                ></div>
                              </div>
                            )}
                          </div>
                        </td>
                      )}
                      
                      {/* VA Progress Column for Main User */}
                      {isMainUser && (
                        <td className="py-3 px-4">
                          <div className="space-y-2">
                            <div className="text-sm">
                              <span className="font-medium">{purchase.purchased || 0}</span>
                              <span className="text-gray-500">/{purchase.targetQuantity}</span>
                            </div>
                            <div className="w-full bg-gray-200 rounded-full h-2">
                              <div 
                                className="bg-blue-600 h-2 rounded-full" 
                                style={{
                                  width: `${Math.min(100, (purchase.purchased || 0) / purchase.targetQuantity * 100)}%`
                                }}
                              ></div>
                            </div>
                            {purchase.va_notes && (
                              <p className="text-xs text-gray-600 italic">"{purchase.va_notes}"</p>
                            )}
                          </div>
                        </td>
                      )}
                      
                      {/* Actions Column */}
                      <td className="py-3 px-4">
                        {isVA ? (
                          <div className="flex space-x-2">
                            <button
                              onClick={() => setEditingRow(editingRow === purchase.id ? null : purchase.id)}
                              className="text-blue-600 hover:text-blue-800 p-1 text-sm"
                            >
                              {editingRow === purchase.id ? (
                                <>
                                  <X className="h-4 w-4" />
                                </>
                              ) : (
                                <>
                                  <Edit3 className="h-4 w-4" />
                                </>
                              )}
                            </button>
                            {(purchase.purchased || 0) >= purchase.targetQuantity && (
                              <span className="text-green-600 p-1">
                                <CheckCircle className="h-4 w-4" />
                              </span>
                            )}
                          </div>
                        ) : (
                          <div className="text-sm">
                            {(purchase.purchased || 0) >= purchase.targetQuantity ? (
                              <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                                <CheckCircle className="h-3 w-3 mr-1" />
                                Complete
                              </span>
                            ) : (purchase.purchased || 0) > 0 ? (
                              <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                                <Clock className="h-3 w-3 mr-1" />
                                In Progress
                              </span>
                            ) : (
                              <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                                <Clock className="h-3 w-3 mr-1" />
                                Pending
                              </span>
                            )}
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Instructions */}
      <div className={`card border ${isVA ? 'bg-blue-50 border-blue-200' : 'bg-green-50 border-green-200'}`}>
        <h3 className={`heading-sm mb-3 ${isVA ? 'text-blue-800' : 'text-green-800'}`}>
          {isVA ? 'VA Instructions' : 'Manager Instructions'}
        </h3>
        <div className={`space-y-2 text-sm ${isVA ? 'text-blue-700' : 'text-green-700'}`}>
          {isVA ? (
            <>
              <p>1. Review purchase tasks assigned by your manager</p>
              <p>2. Check current inventory levels and stock status automatically provided</p>
              <p>3. Click the edit button to update quantities as you purchase items</p>
              <p>4. Progress bars show completion status for each task</p>
              <p>5. Tasks turn green when target quantity is reached</p>
              <p><strong>Note:</strong> All inventory data is live from Sellerboard - no manual checking needed!</p>
            </>
          ) : (
            <>
              <p>1. Create purchase requests with source links and Amazon ASINs</p>
              <p>2. System automatically pulls current stock and sales data from Sellerboard</p>
              <p>3. Your VAs see all requests with live inventory data</p>
              <p>4. Track VA progress and completion status in real-time</p>
              <p>5. Stock alerts help prioritize urgent purchases</p>
              <p><strong>Note:</strong> VAs can update purchase quantities without accessing your Amazon account.</p>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default PurchaseManager;