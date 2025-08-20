import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { FeatureFlagsProvider } from './contexts/FeatureFlagsContext';
import LandingPage from './components/LandingPage';
import Login from './components/Login';
import Dashboard from './components/Dashboard';
import ProtectedRoute from './components/ProtectedRoute';
import axios from 'axios';
import './index.css';

// Configure axios defaults
axios.defaults.baseURL = process.env.REACT_APP_API_URL || 'https://internet-money-tools-production.up.railway.app';
axios.defaults.withCredentials = true;

function App() {
  return (
    <AuthProvider>
      <FeatureFlagsProvider>
        <Router>
          <div className="min-h-screen bg-gray-50">
            <Routes>
              <Route path="/" element={<LandingPage />} />
              <Route path="/login" element={<Login />} />
              <Route 
                path="/dashboard/*" 
                element={
                  <ProtectedRoute>
                    <Dashboard />
                  </ProtectedRoute>
                } 
              />
            </Routes>
          </div>
        </Router>
      </FeatureFlagsProvider>
    </AuthProvider>
  );
}

export default App;