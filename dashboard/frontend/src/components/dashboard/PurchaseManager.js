import React, { useState, useEffect } from 'react';
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
  Target
} from 'lucide-react';
import axios from 'axios';

const PurchaseManager = () => {
  const [purchases, setPurchases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [editingRow, setEditingRow] = useState(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [newPurchase, setNewPurchase] = useState({
    buyLink: '',
    sellLink: '',
    name: '',
    price: '',
    targetQuantity: '',
    notes: ''
  });

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
      const response = await axios.post('/api/purchases', newPurchase, {
        withCredentials: true
      });
      
      if (response.data.success) {
        setPurchases([response.data.purchase, ...purchases]);
        setNewPurchase({
          buyLink: '',
          sellLink: '',
          name: '',
          price: '',
          targetQuantity: '',
          notes: ''
        });
        setShowAddForm(false);
      } else {
        setError('Failed to add purchase');
      }
    } catch (err) {
      setError('Failed to add purchase. Please try again.');
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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-green-500 to-green-600 rounded-lg p-6 text-white">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-white/20 rounded-lg">
              <ShoppingCart className="h-6 w-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold">Purchase Manager</h1>
              <p className="text-green-100">Track purchases with live inventory data</p>
            </div>
          </div>
          <button
            onClick={() => setShowAddForm(true)}
            className="bg-white/20 hover:bg-white/30 px-4 py-2 rounded-lg flex items-center transition-colors"
          >
            <Plus className="h-4 w-4 mr-2" />
            Add Purchase
          </button>
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

      {/* Add New Purchase Form */}
      {showAddForm && (
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="heading-sm">Add New Purchase</h3>
            <button
              onClick={() => setShowAddForm(false)}
              className="text-gray-400 hover:text-gray-600"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
          
          <div className="grid md:grid-cols-2 gap-4">
            <div>
              <label className="label-text">Buy Link (Source)</label>
              <input
                type="url"
                value={newPurchase.buyLink}
                onChange={(e) => setNewPurchase({...newPurchase, buyLink: e.target.value})}
                placeholder="https://www.walmart.com/..."
                className="input-field"
              />
            </div>
            
            <div>
              <label className="label-text">Amazon Sell Link</label>
              <input
                type="url"
                value={newPurchase.sellLink}
                onChange={(e) => setNewPurchase({...newPurchase, sellLink: e.target.value})}
                placeholder="https://www.amazon.com/dp/..."
                className="input-field"
              />
            </div>
            
            <div className="md:col-span-2">
              <label className="label-text">Product Name</label>
              <input
                type="text"
                value={newPurchase.name}
                onChange={(e) => setNewPurchase({...newPurchase, name: e.target.value})}
                placeholder="Product name"
                className="input-field"
              />
            </div>
            
            <div>
              <label className="label-text">Source Price</label>
              <input
                type="number"
                step="0.01"
                value={newPurchase.price}
                onChange={(e) => setNewPurchase({...newPurchase, price: e.target.value})}
                placeholder="0.00"
                className="input-field"
              />
            </div>
            
            <div>
              <label className="label-text">Target Quantity</label>
              <input
                type="number"
                value={newPurchase.targetQuantity}
                onChange={(e) => setNewPurchase({...newPurchase, targetQuantity: e.target.value})}
                placeholder="50"
                className="input-field"
              />
            </div>
            
            <div className="md:col-span-2">
              <label className="label-text">Notes</label>
              <textarea
                value={newPurchase.notes}
                onChange={(e) => setNewPurchase({...newPurchase, notes: e.target.value})}
                placeholder="Purchase notes..."
                rows="2"
                className="input-field"
              />
            </div>
          </div>
          
          <div className="flex space-x-3 mt-4">
            <button
              onClick={addNewPurchase}
              className="btn-primary"
            >
              Add Purchase
            </button>
            <button
              onClick={() => setShowAddForm(false)}
              className="btn-secondary"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Purchase List */}
      <div className="card">
        <h3 className="heading-sm mb-4">Purchase Tracking</h3>
        
        {purchases.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <Package className="h-12 w-12 mx-auto mb-4 text-gray-300" />
            <p>No purchases tracked yet</p>
            <p className="text-sm">Add your first purchase to get started</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-3 px-4 font-medium text-gray-600">Product</th>
                  <th className="text-left py-3 px-4 font-medium text-gray-600">Stock Status</th>
                  <th className="text-left py-3 px-4 font-medium text-gray-600">Inventory</th>
                  <th className="text-left py-3 px-4 font-medium text-gray-600">Target</th>
                  <th className="text-left py-3 px-4 font-medium text-gray-600">Purchased</th>
                  <th className="text-left py-3 px-4 font-medium text-gray-600">Actions</th>
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
                      
                      <td className="py-3 px-4">
                        <div className="text-sm">
                          <span className="font-medium">{purchase.purchased || 0}</span>
                          <span className="text-gray-500 ml-1">purchased</span>
                        </div>
                      </td>
                      
                      <td className="py-3 px-4">
                        <div className="flex space-x-2">
                          <button
                            onClick={() => setEditingRow(purchase.id)}
                            className="text-blue-600 hover:text-blue-800 p-1"
                          >
                            <Edit3 className="h-4 w-4" />
                          </button>
                        </div>
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
      <div className="card bg-blue-50 border border-blue-200">
        <h3 className="heading-sm mb-3 text-blue-800">How It Works</h3>
        <div className="space-y-2 text-sm text-blue-700">
          <p>1. Add purchase requests with source links and Amazon ASINs</p>
          <p>2. System automatically pulls current stock and sales data from Sellerboard</p>
          <p>3. VAs can see inventory levels without manually checking Amazon</p>
          <p>4. Track purchase status and quantities in one centralized location</p>
          <p>5. Stock status updates automatically based on sales velocity</p>
        </div>
      </div>
    </div>
  );
};

export default PurchaseManager;