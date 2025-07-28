import React, { useState } from 'react';
import { Routes, Route, Link, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { 
  BarChart3, 
  Settings as SettingsIcon, 
  ShoppingCart, 
  TrendingUp, 
  FileText,
  User,
  LogOut,
  Home,
  Database,
  Link as LinkIcon,
  Shield
} from 'lucide-react';

import Overview from './dashboard/Overview';
import Analytics from './dashboard/Analytics';
import EnhancedAnalytics from './dashboard/EnhancedAnalytics';
import SettingsPage from './dashboard/Settings';
import SheetConfig from './dashboard/SheetConfig';
import FileManager from './dashboard/FileManager';
import Admin from './dashboard/Admin';
import AdminUserDashboard from './AdminUserDashboard';
import Onboarding from './Onboarding';

const Dashboard = () => {
  const { user, logout } = useAuth();
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Check if current user is admin
  const isAdmin = user?.discord_id === '1278565917206249503';

  const navigation = [
    { name: 'Overview', href: '/dashboard', icon: Home, current: location.pathname === '/dashboard' },
    { name: 'Analytics', href: '/dashboard/analytics', icon: BarChart3, current: location.pathname === '/dashboard/analytics' },
    { name: 'Smart Restock', href: '/dashboard/enhanced-analytics', icon: TrendingUp, current: location.pathname === '/dashboard/enhanced-analytics' },
    { name: 'File Manager', href: '/dashboard/files', icon: FileText, current: location.pathname === '/dashboard/files' },
    { name: 'Sheet Setup', href: '/dashboard/sheet-config', icon: Database, current: location.pathname === '/dashboard/sheet-config' },
    { name: 'Settings', href: '/dashboard/settings', icon: SettingsIcon, current: location.pathname === '/dashboard/settings' },
    ...(isAdmin ? [{ name: 'Admin', href: '/dashboard/admin', icon: Shield, current: location.pathname === '/dashboard/admin' }] : []),
  ];

  const getStatusColor = () => {
    if (!user?.profile_configured) return 'bg-red-100 text-red-800';
    if (!user?.google_linked) return 'bg-yellow-100 text-yellow-800';
    if (!user?.sheet_configured) return 'bg-blue-100 text-blue-800';
    return 'bg-green-100 text-green-800';
  };

  const getStatusText = () => {
    if (!user?.profile_configured) return 'Setup Required';
    if (!user?.google_linked) return 'Google Linking Required';
    if (!user?.sheet_configured) return 'Sheet Configuration Required';
    return 'Fully Configured';
  };

  // Show onboarding for new users who haven't completed setup
  const needsOnboarding = !user?.profile_configured || !user?.google_linked || !user?.sheet_configured;
  
  if (needsOnboarding) {
    return <Onboarding />;
  }

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Sidebar */}
      <div className="hidden md:flex md:w-64 md:flex-col">
        <div className="flex flex-col flex-grow pt-5 pb-4 overflow-y-auto bg-white border-r border-gray-200">
          <div className="flex items-center flex-shrink-0 px-4">
            <ShoppingCart className="h-8 w-8 text-builders-500" />
            <span className="ml-2 text-xl font-bold text-gray-900">builders+</span>
          </div>
          <div className="mt-5 flex-grow flex flex-col">
            <nav className="flex-1 px-2 space-y-1">
              {navigation.map((item) => {
                const Icon = item.icon;
                return (
                  <Link
                    key={item.name}
                    to={item.href}
                    className={`${
                      item.current
                        ? 'bg-builders-100 border-builders-500 text-builders-700'
                        : 'border-transparent text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                    } group flex items-center px-2 py-2 text-sm font-medium border-l-4 transition-colors duration-200`}
                  >
                    <Icon
                      className={`${
                        item.current ? 'text-builders-500' : 'text-gray-400 group-hover:text-gray-500'
                      } mr-3 h-5 w-5`}
                    />
                    {item.name}
                  </Link>
                );
              })}
            </nav>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <header className="bg-white shadow-sm border-b border-gray-200">
          <div className="px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between items-center py-4">
              <div className="flex items-center">
                <button
                  type="button"
                  className="md:hidden -ml-0.5 -mt-0.5 h-12 w-12 inline-flex items-center justify-center rounded-md text-gray-500 hover:text-gray-900"
                  onClick={() => setSidebarOpen(!sidebarOpen)}
                >
                  <span className="sr-only">Open sidebar</span>
                  <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                  </svg>
                </button>
                <h1 className="text-2xl font-semibold text-gray-900 ml-4 md:ml-0">
                  {navigation.find(item => item.current)?.name || 'Dashboard'}
                </h1>
              </div>
              
              <div className="flex items-center space-x-4">
                {/* Status Badge */}
                <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor()}`}>
                  {getStatusText()}
                </span>
                
                {/* User Menu */}
                <div className="flex items-center space-x-3">
                  <div className="text-right">
                    <p className="text-sm font-medium text-gray-900">{user?.discord_username}</p>
                    <p className="text-xs text-gray-500">Discord User</p>
                  </div>
                  {user?.discord_avatar ? (
                    <img
                      className="h-8 w-8 rounded-full"
                      src={`https://cdn.discordapp.com/avatars/${user.discord_id}/${user.discord_avatar}.png`}
                      alt="User avatar"
                    />
                  ) : (
                    <div className="h-8 w-8 rounded-full bg-builders-500 flex items-center justify-center">
                      <User className="h-5 w-5 text-white" />
                    </div>
                  )}
                  <button
                    onClick={logout}
                    className="text-gray-400 hover:text-gray-500 transition-colors duration-200"
                    title="Logout"
                  >
                    <LogOut className="h-5 w-5" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto bg-gray-50">
          <div className="px-4 sm:px-6 lg:px-8 py-8">
            <Routes>
              <Route path="/" element={<Overview />} />
              <Route path="/analytics" element={<Analytics />} />
              <Route path="/enhanced-analytics" element={<EnhancedAnalytics />} />
              <Route path="/files" element={<FileManager />} />
              <Route path="/sheet-config" element={<SheetConfig />} />
              <Route path="/settings" element={<SettingsPage />} />
              {isAdmin && <Route path="/admin" element={<Admin />} />}
              {isAdmin && <Route path="/admin/view-user-dashboard/:userId" element={<AdminUserDashboard />} />}
            </Routes>
          </div>
        </main>
      </div>
    </div>
  );
};

export default Dashboard;