import React, { useState, useEffect } from 'react';
import { Routes, Route, Link, useLocation, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../contexts/AuthContext';
import { 
  Settings as SettingsIcon, 
  ShoppingCart, 
  TrendingUp, 
  FileText,
  User,
  LogOut,
  Home,
  Database,
  Shield,
  Eye,
  ArrowLeft,
  Users,
  TrendingDown,
  Menu,
  ChevronLeft,
  ChevronRight,
  X,
  Package,
  Zap,
  TestTube
} from 'lucide-react';

import Overview from './dashboard/Overview';
import EnhancedAnalytics from './dashboard/EnhancedAnalytics';
import SmartRestockRecommendations from './dashboard/SmartRestockRecommendations';
import RetailerLeadAnalysis from './dashboard/RetailerLeadAnalysis';
import DiscountOpportunities from './dashboard/DiscountOpportunities';
import AllProductAnalytics from './dashboard/AllProductAnalytics';
import SettingsPage from './dashboard/Settings';
import SheetConfig from './dashboard/SheetConfig';
import FileManager from './dashboard/FileManager';
import AdminCompact from './dashboard/AdminCompact';
import SubUserManager from './dashboard/SubUserManager';
import ReimbursementAnalyzer from './dashboard/ReimbursementAnalyzer';
import ExpectedArrivals from './dashboard/ExpectedArrivals';
import LambdaDeployment from './dashboard/LambdaDeployment';
import Onboarding from './Onboarding';
import ImageTest from './ImageTest';

const Dashboard = () => {
  const { user, logout, refreshUser } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [demoMode, setDemoMode] = useState(false);

  // Check if current user is admin
  const isAdmin = user?.discord_id === '712147636463075389';

  // Check for demo mode
  useEffect(() => {
    const checkDemoMode = async () => {
      try {
        const response = await axios.get('/api/demo/status');
        setDemoMode(response.data.demo_mode);
      } catch (error) {
        // Failed to check demo mode, continue with normal operation
      }
    };
    checkDemoMode();
  }, []);

  // Demo mode controls
  const toggleDemoMode = async () => {
    try {
      const endpoint = demoMode ? '/api/demo/disable' : '/api/demo/enable';
      const response = await axios.post(endpoint);
      setDemoMode(response.data.demo_mode);
      // Refresh user data to reflect demo mode changes
      await refreshUser();
    } catch (error) {
      // Failed to toggle demo mode
    }
  };

  // Handle returning from impersonation
  const handleReturnFromImpersonation = async () => {
    try {
      await axios.post('/api/admin/stop-impersonate', {}, { 
        withCredentials: true 
      });
      
      // Refresh user data to restore admin session
      await refreshUser();
      
      // Navigate back to admin panel
      navigate('/dashboard/admin');
      
    } catch (error) {
      // Failed to stop impersonation
      // Force navigate back even if API call fails
      navigate('/dashboard/admin');
    }
  };

  // Check if user is main user (not sub-user)
  const isMainUser = !user?.user_type || user?.user_type === 'main';
  
  // Check if user has specific permissions
  const hasPermission = (permission) => {
    // Main users and admins have access to everything
    if (isMainUser || isAdmin) return true;
    
    // Subusers now have full access to everything their parent has
    // This allows VAs to perform all tasks for their main user
    return true;
  };

  const navigation = [
    { name: 'Overview', href: '/dashboard', icon: Home, current: location.pathname === '/dashboard' },
    { name: 'Smart Restock', href: '/dashboard/enhanced-analytics', icon: TrendingUp, current: location.pathname === '/dashboard/enhanced-analytics' || location.pathname.startsWith('/dashboard/smart-restock') || location.pathname.startsWith('/dashboard/lead-analysis') || location.pathname.startsWith('/dashboard/discount-opportunities') || location.pathname.startsWith('/dashboard/all-product-analytics') },
    { name: 'Missing Listings', href: '/dashboard/expected-arrivals', icon: Package, current: location.pathname === '/dashboard/expected-arrivals' },
    { name: 'Reimbursements', href: '/dashboard/reimbursements', icon: TrendingDown, current: location.pathname === '/dashboard/reimbursements' },
    { name: 'File Manager', href: '/dashboard/files', icon: FileText, current: location.pathname === '/dashboard/files' },
    { name: 'Sheet Setup', href: '/dashboard/sheet-config', icon: Database, current: location.pathname === '/dashboard/sheet-config' },
    ...(isMainUser ? [{ name: 'VA Management', href: '/dashboard/subusers', icon: Users, current: location.pathname === '/dashboard/subusers' }] : []),
    ...(isAdmin ? [{ name: 'Admin', href: '/dashboard/admin', icon: Shield, current: location.pathname === '/dashboard/admin' }] : []),
    ...(isAdmin ? [{ name: 'Lambda Deploy', href: '/dashboard/automation', icon: Zap, current: location.pathname === '/dashboard/automation' }] : []),
    { name: 'Settings', href: '/dashboard/settings', icon: SettingsIcon, current: location.pathname === '/dashboard/settings' },
  ];

  const getStatusColor = () => {
    // Subusers inherit configuration from their parent, so they're always configured
    if (!isMainUser) return 'bg-green-100 text-green-800';
    
    // Main users need individual setup steps
    if (!user?.profile_configured) return 'bg-red-100 text-red-800';
    if (!user?.google_linked) return 'bg-yellow-100 text-yellow-800';
    if (!user?.sheet_configured) return 'bg-blue-100 text-blue-800';
    return 'bg-green-100 text-green-800';
  };

  const getStatusText = () => {
    // Subusers inherit configuration from their parent, so they're always configured
    if (!isMainUser) return 'Fully Configured';
    
    // Main users need individual setup steps
    if (!user?.profile_configured) return 'Setup Required';
    if (!user?.google_linked) return 'Google Linking Required';
    if (!user?.sheet_configured) return 'Sheet Configuration Required';
    return 'Fully Configured';
  };

  // Show onboarding only for main users who haven't completed setup
  // VA subusers should skip setup and use their parent's configuration
  const needsOnboarding = isMainUser && (!user?.profile_configured || !user?.google_linked || !user?.sheet_configured);
  
  if (needsOnboarding) {
    return <Onboarding />;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Admin Impersonation Banner */}
      {user?.admin_impersonating && (
        <div className="bg-yellow-100 border-b border-yellow-200 px-4 py-3">
          <div className="max-w-7xl mx-auto flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Eye className="h-4 w-4 text-yellow-600" />
              <div>
                <p className="text-xs font-medium text-yellow-800">
                  Admin View: Viewing as {user?.discord_username || 'Unknown User'}
                </p>
                <p className="text-xs text-yellow-700">
                  You are seeing this user's dashboard exactly as they would see it
                </p>
              </div>
            </div>
            <button
              onClick={handleReturnFromImpersonation}
              className="inline-flex items-center px-2 py-1 border border-yellow-300 rounded-md text-xs font-medium text-yellow-800 bg-yellow-50 hover:bg-yellow-100 transition-colors"
            >
              <ArrowLeft className="h-3 w-3 mr-1" />
              Return to Admin
            </button>
          </div>
        </div>
      )}
      
      <div className="flex min-h-screen">
      {/* Mobile sidebar */}
      <div className={`fixed inset-0 flex z-40 md:hidden ${sidebarOpen ? '' : 'pointer-events-none'}`}>
        {/* Backdrop */}
        <div 
          className={`fixed inset-0 bg-gray-600 bg-opacity-75 transition-opacity ${
            sidebarOpen ? 'opacity-100' : 'opacity-0'
          }`} 
          onClick={() => setSidebarOpen(false)}
        />
        
        {/* Sidebar panel */}
        <div className={`relative flex-1 flex flex-col max-w-xs w-full bg-gradient-to-b from-slate-900 to-slate-800 transform transition-transform ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}>
          <div className="absolute top-0 right-0 -mr-12 pt-2">
            <button
              type="button"
              className="ml-1 flex items-center justify-center h-10 w-10 rounded-full focus:outline-none focus:ring-2 focus:ring-inset focus:ring-white bg-slate-600 hover:bg-slate-500"
              onClick={() => setSidebarOpen(false)}
            >
              <span className="sr-only">Close sidebar</span>
              <X className="h-6 w-6 text-white" />
            </button>
          </div>
          
          <div className="flex-1 h-0 pt-6 pb-4 overflow-y-auto">
            {/* Logo section */}
            <div className="flex items-center px-4 pb-6">
              <div className="p-2 bg-gradient-to-br from-amber-400 to-amber-600 rounded-lg shadow-lg">
                <ShoppingCart className="h-6 w-6 text-white" />
              </div>
              <div className="ml-3">
                <span className="text-xl font-bold text-white">DMS</span>
                <p className="text-xs text-slate-400">Dashboard</p>
              </div>
            </div>
            
            {/* Navigation */}
            <nav className="px-3 space-y-1">
              {navigation.map((item) => {
                const Icon = item.icon;
                return (
                  <Link
                    key={item.name}
                    to={item.href}
                    onClick={() => setSidebarOpen(false)}
                    className={`group flex items-center px-3 py-2.5 text-sm font-medium rounded-lg transition-all duration-200 ${
                      item.current
                        ? 'bg-gradient-to-r from-amber-500 to-amber-600 text-white shadow-lg shadow-amber-500/25'
                        : 'text-slate-300 hover:text-white hover:bg-slate-700'
                    }`}
                  >
                    <Icon
                      className={`mr-3 h-5 w-5 ${
                        item.current ? 'text-white' : 'text-slate-400 group-hover:text-white'
                      }`}
                    />
                    {item.name}
                  </Link>
                );
              })}
            </nav>
          </div>
          
          {/* Mobile user section */}
          <div className="border-t border-slate-700 px-3 py-4">
            <div className="flex items-center px-3 py-2">
              <div className="w-8 h-8 bg-gradient-to-br from-amber-400 to-amber-600 rounded-full flex items-center justify-center">
                <User className="h-4 w-4 text-white" />
              </div>
              <div className="ml-3 min-w-0 flex-1">
                <p className="text-sm font-medium text-white truncate">
                  {user?.discord_username || 'User'}
                </p>
                <div className="flex items-center space-x-1 mt-1">
                  <div className={`w-2 h-2 rounded-full ${getStatusColor().replace('bg-', 'bg-').replace('text-', '')}`}></div>
                  <p className="text-xs text-slate-400 truncate">{getStatusText()}</p>
                </div>
              </div>
            </div>
            
            <button
              onClick={logout}
              className="mt-2 w-full flex items-center px-3 py-2 text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-700 rounded-lg transition-colors"
            >
              <LogOut className="mr-3 h-4 w-4" />
              Sign out
            </button>
          </div>
        </div>
      </div>

      {/* Desktop sidebar */}
      <div className={`hidden md:flex ${sidebarCollapsed ? 'md:w-16' : 'md:w-64'} md:flex-col transition-all duration-300 fixed left-0 top-0 h-screen z-30 bg-gradient-to-b from-slate-900 to-slate-800 border-r border-slate-700 shadow-2xl`}>
          {/* Logo section */}
          <div className="flex items-center justify-between px-4 py-6">
            <div className="flex items-center">
              <div className="p-2 bg-gradient-to-br from-amber-400 to-amber-600 rounded-lg shadow-lg">
                <ShoppingCart className="h-6 w-6 text-white" />
              </div>
              {!sidebarCollapsed && (
                <div className="ml-3">
                  <span className="text-xl font-bold text-white">DMS</span>
                  <p className="text-xs text-slate-400">Dashboard</p>
                </div>
              )}
            </div>
            {!sidebarCollapsed && (
              <button
                onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
                className="p-1.5 rounded-md text-slate-400 hover:text-white hover:bg-slate-700 transition-colors"
                title="Collapse sidebar"
              >
                <ChevronLeft className="h-5 w-5" />
              </button>
            )}
          </div>

          {/* Expand button for collapsed state */}
          {sidebarCollapsed && (
            <div className="px-3 pb-4">
              <button
                onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
                className="w-full p-2 rounded-md text-slate-400 hover:text-white hover:bg-slate-700 transition-colors"
                title="Expand sidebar"
              >
                <ChevronRight className="h-5 w-5 mx-auto" />
              </button>
            </div>
          )}

          {/* Navigation */}
          <nav className="flex-1 px-3 pb-4 space-y-1">
            {navigation.map((item) => {
              const Icon = item.icon;
              return (
                <Link
                  key={item.name}
                  to={item.href}
                  className={`group flex items-center px-3 py-2.5 text-sm font-medium rounded-lg transition-all duration-200 ${
                    item.current
                      ? 'bg-gradient-to-r from-amber-500 to-amber-600 text-white shadow-lg shadow-amber-500/25'
                      : 'text-slate-300 hover:text-white hover:bg-slate-700'
                  }`}
                  title={sidebarCollapsed ? item.name : ''}
                >
                  <Icon
                    className={`${sidebarCollapsed ? 'mx-auto' : 'mr-3'} h-5 w-5 ${
                      item.current ? 'text-white' : 'text-slate-400 group-hover:text-white'
                    }`}
                  />
                  {!sidebarCollapsed && (
                    <span className="truncate">{item.name}</span>
                  )}
                </Link>
              );
            })}
          </nav>

          {/* User info section */}
          {!sidebarCollapsed && (
            <div className="border-t border-slate-700 px-3 py-4">
              <div className="flex items-center px-3 py-2">
                <div className="w-8 h-8 bg-gradient-to-br from-amber-400 to-amber-600 rounded-full flex items-center justify-center">
                  <User className="h-4 w-4 text-white" />
                </div>
                <div className="ml-3 min-w-0 flex-1">
                  <p className="text-sm font-medium text-white truncate">
                    {user?.discord_username || 'User'}
                  </p>
                  <div className="flex items-center space-x-1 mt-1">
                    <div className={`w-2 h-2 rounded-full ${getStatusColor().replace('bg-', 'bg-').replace('text-', '')}`}></div>
                    <p className="text-xs text-slate-400 truncate">{getStatusText()}</p>
                  </div>
                </div>
              </div>
              
              <button
                onClick={logout}
                className="mt-2 w-full flex items-center px-3 py-2 text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-700 rounded-lg transition-colors"
              >
                <LogOut className="mr-3 h-4 w-4" />
                Sign out
              </button>
            </div>
          )}

          {/* Collapsed user section */}
          {sidebarCollapsed && (
            <div className="border-t border-slate-700 px-3 py-4">
              <div className="flex flex-col items-center space-y-3">
                <div className="w-8 h-8 bg-gradient-to-br from-amber-400 to-amber-600 rounded-full flex items-center justify-center">
                  <User className="h-4 w-4 text-white" />
                </div>
                <button
                  onClick={logout}
                  className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-700 transition-colors"
                  title="Sign out"
                >
                  <LogOut className="h-4 w-4" />
                </button>
              </div>
            </div>
          )}
      </div>

      {/* Main content */}
      <div className={`flex-1 flex flex-col overflow-hidden transition-all duration-300 ${sidebarCollapsed ? 'md:ml-16' : 'md:ml-64'}`}>
        {/* Header */}
        <header className="bg-white shadow-sm border-b border-gray-200">
          <div className="px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between items-center py-4">
              <div className="flex items-center">
                <button
                  type="button"
                  className="md:hidden p-2 rounded-md text-gray-500 hover:text-gray-900 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-amber-500"
                  onClick={() => setSidebarOpen(!sidebarOpen)}
                >
                  <span className="sr-only">Open sidebar</span>
                  <Menu className="h-6 w-6" />
                </button>
                <h1 className="text-lg font-semibold text-gray-900 ml-3 md:ml-0">
                  {navigation.find(item => item.current)?.name || 'Dashboard'}
                </h1>
              </div>
            </div>
          </div>
        </header>

        {/* Demo Mode Banner */}
        {demoMode && (
          <div className="bg-orange-100 border-l-4 border-orange-500 p-4">
            <div className="flex items-center justify-between">
              <div className="flex">
                <div className="flex-shrink-0">
                  <Eye className="h-5 w-5 text-orange-400" />
                </div>
                <div className="ml-3">
                  <p className="text-sm text-orange-700">
                    <strong>Demo Mode Active:</strong> All data shown is simulated for demonstration purposes only.
                  </p>
                </div>
              </div>
              <button
                onClick={toggleDemoMode}
                className="bg-orange-200 hover:bg-orange-300 text-orange-800 px-3 py-1 rounded text-xs font-medium transition-colors"
              >
                Exit Demo
              </button>
            </div>
          </div>
        )}

        {/* Page content */}
        <main className="flex-1 overflow-y-auto bg-gray-50">
          <div className="px-4 sm:px-6 lg:px-8 py-8">
            <Routes>
              <Route path="/" element={<Overview />} />
              <Route path="/enhanced-analytics" element={<EnhancedAnalytics />} />
              <Route path="/smart-restock" element={<SmartRestockRecommendations />} />
              <Route path="/lead-analysis" element={<RetailerLeadAnalysis />} />
              <Route path="/discount-opportunities" element={<DiscountOpportunities />} />
              <Route path="/image-test" element={<ImageTest />} />
              <Route path="/all-product-analytics" element={<AllProductAnalytics />} />
              <Route path="/expected-arrivals" element={<ExpectedArrivals />} />
              <Route path="/reimbursements" element={<ReimbursementAnalyzer />} />
              <Route path="/files" element={<FileManager />} />
              <Route path="/sheet-config" element={<SheetConfig />} />
              <Route path="/settings" element={<SettingsPage />} />
              {isMainUser && <Route path="/subusers" element={<SubUserManager />} />}
              {isAdmin && <Route path="/admin" element={<AdminCompact />} />}
              {isAdmin && <Route path="/automation" element={<LambdaDeployment />} />}
            </Routes>
          </div>
        </main>

        {/* Floating Demo Mode Toggle Button */}
        <button
          onClick={toggleDemoMode}
          className={`fixed bottom-6 right-6 z-50 p-3 rounded-full shadow-lg transition-all duration-200 hover:scale-105 ${
            demoMode 
              ? 'bg-orange-500 hover:bg-orange-600 text-white' 
              : 'bg-gray-200 hover:bg-gray-300 text-gray-700'
          }`}
          title={demoMode ? "Exit Demo Mode" : "Enter Demo Mode"}
        >
          <TestTube className="h-5 w-5" />
        </button>
      </div>
      </div>
    </div>
  );
};

export default Dashboard;