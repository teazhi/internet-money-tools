import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, BarChart3, Shield, Zap, Users, CheckCircle, Star, ShoppingCart, Menu, X, TrendingUp, FileText, Database, Package, TrendingDown, Plus, Target, ClipboardList } from 'lucide-react';

const LandingPage = () => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const features = [
    {
      icon: <BarChart3 className="h-5 w-5" />,
      title: "Smart Analytics",
      description: "Advanced analytics and insights for your Amazon business with real-time data processing."
    },
    {
      icon: <Zap className="h-5 w-5" />,
      title: "Automated Workflows",
      description: "Streamline operations with intelligent automation and smart restock recommendations."
    },
    {
      icon: <Shield className="h-5 w-5" />,
      title: "Secure & Reliable",
      description: "Enterprise-grade security with bank-level encryption and 99.9% uptime guarantee."
    },
    {
      icon: <Users className="h-5 w-5" />,
      title: "Team Management",
      description: "Collaborate with your team through integrated VA management and permission controls."
    }
  ];

  const dashboardFeatures = [
    {
      icon: <TrendingUp className="h-4 w-4 text-builders-500" />,
      title: "Smart Restock",
      description: "AI-powered inventory recommendations with priority filtering and advanced analytics"
    },
    {
      icon: <Plus className="h-4 w-4 text-builders-500" />,
      title: "Purchase Manager",
      description: "Track and manage purchase orders with automated storage handling"
    },
    {
      icon: <Package className="h-4 w-4 text-builders-500" />,
      title: "Missing Listings",
      description: "Track and manage your expected arrivals and inventory gaps"
    },
    {
      icon: <TrendingDown className="h-4 w-4 text-builders-500" />,
      title: "Reimbursements",
      description: "Automated reimbursement analysis and claim tracking"
    },
    {
      icon: <Database className="h-4 w-4 text-builders-500" />,
      title: "Sheet Setup",
      description: "Seamless Google Sheets integration with automated data sync"
    },
    {
      icon: <Users className="h-4 w-4 text-builders-500" />,
      title: "VA Management",
      description: "Advanced team collaboration and permission controls"
    }
  ];

  const testimonials = [
    {
      name: "Sarah Chen",
      role: "Amazon Seller",
      content: "DMS transformed my inventory management. The smart restock feature alone saved me thousands in lost sales.",
      rating: 5
    },
    {
      name: "Michael Rodriguez",
      role: "E-commerce Entrepreneur",
      content: "The reimbursement tracker found money I didn't even know Amazon owed me. Incredible ROI.",
      rating: 5
    },
    {
      name: "Emily Johnson",
      role: "FBA Business Owner",
      content: "Finally, a dashboard that actually understands Amazon sellers. The VA management is a game-changer.",
      rating: 5
    }
  ];

  const renderStars = (rating) => {
    return Array.from({ length: 5 }, (_, i) => (
      <Star
        key={i}
        className={`h-3 w-3 ${i < rating ? 'text-builders-500 fill-current' : 'text-gray-300'}`}
      />
    ));
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Navigation */}
      <nav className="bg-white shadow-sm border-b border-gray-200 fixed w-full z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            {/* Logo */}
            <div className="flex items-center">
              <div className="p-2 bg-gradient-to-br from-amber-400 to-amber-600 rounded-lg shadow-lg">
                <ShoppingCart className="h-5 w-5 text-white" />
              </div>
              <div className="ml-3">
                <span className="text-lg font-bold text-gray-900">DMS</span>
                <p className="text-xs text-gray-500">Dashboard</p>
              </div>
            </div>
            
            {/* Desktop Navigation */}
            <div className="hidden md:flex items-center space-x-6">
              <a href="#features" className="text-sm text-gray-700 hover:text-builders-600 transition-colors">Features</a>
              <a href="#dashboard" className="text-sm text-gray-700 hover:text-builders-600 transition-colors">Dashboard</a>
              <a href="#testimonials" className="text-sm text-gray-700 hover:text-builders-600 transition-colors">Reviews</a>
              <Link 
                to="/login" 
                className="btn-primary"
              >
                Sign In
              </Link>
            </div>

            {/* Mobile menu button */}
            <div className="md:hidden">
              <button
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                className="p-2 rounded-md text-gray-500 hover:text-gray-900 hover:bg-gray-100"
              >
                {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
              </button>
            </div>
          </div>

          {/* Mobile Navigation */}
          {mobileMenuOpen && (
            <div className="md:hidden border-t border-gray-200 py-3">
              <div className="space-y-2">
                <a href="#features" className="block px-3 py-2 text-sm text-gray-700 hover:text-builders-600">Features</a>
                <a href="#dashboard" className="block px-3 py-2 text-sm text-gray-700 hover:text-builders-600">Dashboard</a>
                <a href="#testimonials" className="block px-3 py-2 text-sm text-gray-700 hover:text-builders-600">Reviews</a>
                <Link to="/login" className="block px-3 py-2 text-sm font-medium text-builders-600">Sign In</Link>
              </div>
            </div>
          )}
        </div>
      </nav>

      {/* Hero Section */}
      <section className="pt-24 pb-20 bg-gradient-to-br from-slate-900 to-slate-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center">
            <div className="mb-8">
              <div className="inline-flex items-center px-4 py-2 bg-amber-100 text-amber-800 text-sm font-medium rounded-full">
                <span className="w-2 h-2 bg-amber-400 rounded-full mr-2"></span>
                Trusted by 1000+ Amazon Sellers
              </div>
            </div>
            
            <h1 className="text-4xl md:text-6xl lg:text-7xl font-bold text-white mb-6 leading-tight">
              Your Amazon Business
              <br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-amber-400 to-amber-600">Command Center</span>
            </h1>
            <p className="text-xl md:text-2xl text-slate-300 mb-12 max-w-3xl mx-auto leading-relaxed">
              Professional dashboard for Amazon sellers. Smart analytics, inventory management, and automated workflows - all in one powerful platform.
            </p>
            
            <div className="flex flex-col sm:flex-row gap-4 justify-center items-center mb-16">
              <Link 
                to="/login"
                className="inline-flex items-center bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-600 hover:to-amber-700 text-white px-8 py-4 rounded-lg font-semibold text-lg shadow-lg shadow-amber-500/25 transition-all hover:scale-105"
              >
                Start Free Trial
                <ArrowRight className="ml-2 h-5 w-5" />
              </Link>
              <button className="text-slate-300 hover:text-white font-semibold px-8 py-4 text-lg transition-colors">
                View Demo
              </button>
            </div>

            {/* Dashboard Preview */}
            <div className="relative max-w-6xl mx-auto">
              <div className="bg-white rounded-xl shadow-2xl overflow-hidden">
                {/* Mock Sidebar */}
                <div className="flex">
                  <div className="w-20 md:w-64 bg-gradient-to-b from-slate-900 to-slate-800 flex-shrink-0">
                    <div className="p-3 md:p-4">
                      <div className="flex items-center">
                        <div className="p-2 bg-gradient-to-br from-amber-400 to-amber-600 rounded-lg shadow-lg">
                          <ShoppingCart className="h-4 w-4 text-white" />
                        </div>
                        <div className="ml-3 hidden md:block">
                          <span className="text-lg font-bold text-white">DMS</span>
                          <p className="text-xs text-slate-400">Dashboard</p>
                        </div>
                      </div>
                    </div>
                    
                    <nav className="px-2 md:px-3 space-y-1">
                      <div className="bg-gradient-to-r from-amber-500 to-amber-600 text-white px-2 md:px-3 py-2 rounded-lg flex items-center">
                        <TrendingUp className="h-4 w-4" />
                        <span className="ml-3 hidden md:block text-sm">Overview</span>
                      </div>
                      <div className="text-slate-300 px-2 md:px-3 py-2 rounded-lg flex items-center hover:bg-slate-700/50">
                        <TrendingUp className="h-4 w-4" />
                        <span className="ml-3 hidden md:block text-sm">Smart Restock</span>
                      </div>
                      <div className="text-slate-300 px-2 md:px-3 py-2 rounded-lg flex items-center hover:bg-slate-700/50">
                        <Plus className="h-4 w-4" />
                        <span className="ml-3 hidden md:block text-sm">Purchase Manager</span>
                      </div>
                      <div className="text-slate-300 px-2 md:px-3 py-2 rounded-lg flex items-center hover:bg-slate-700/50">
                        <Package className="h-4 w-4" />
                        <span className="ml-3 hidden md:block text-sm">Missing Listings</span>
                      </div>
                      <div className="text-slate-300 px-2 md:px-3 py-2 rounded-lg flex items-center hover:bg-slate-700/50">
                        <TrendingDown className="h-4 w-4" />
                        <span className="ml-3 hidden md:block text-sm">Reimbursements</span>
                      </div>
                      <div className="text-slate-300 px-2 md:px-3 py-2 rounded-lg flex items-center hover:bg-slate-700/50">
                        <Users className="h-4 w-4" />
                        <span className="ml-3 hidden md:block text-sm">VA Management</span>
                      </div>
                    </nav>
                  </div>
                  
                  {/* Main Content */}
                  <div className="flex-1 min-h-96">
                    {/* Header */}
                    <div className="bg-white border-b border-gray-200 px-4 md:px-6 py-4">
                      <h2 className="text-lg font-semibold text-gray-900">Overview</h2>
                    </div>
                    
                    {/* Welcome Header */}
                    <div className="p-4 md:p-6">
                      <div className="bg-gradient-to-r from-builders-500 to-builders-600 rounded-lg p-4 md:p-6 text-white mb-6">
                        <h3 className="text-lg md:text-xl font-bold mb-2">Welcome back, John!</h3>
                        <p className="text-builders-100 text-sm md:text-base">Here's your business overview for today</p>
                        <p className="text-builders-200 text-xs md:text-sm mt-1">Last updated: 2:35 PM</p>
                      </div>
                      
                      {/* Stats Cards */}
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 md:gap-4 mb-6">
                        <div className="card">
                          <div className="flex items-center justify-between">
                            <div>
                              <p className="caption-text">Today's Orders</p>
                              <p className="text-lg md:text-xl font-bold text-green-600">47</p>
                              <p className="text-xs text-green-600">↗ +12% from yesterday</p>
                            </div>
                            <div className="p-2 bg-green-50 rounded-lg">
                              <ShoppingCart className="h-4 w-4 md:h-5 md:w-5 text-green-600" />
                            </div>
                          </div>
                        </div>
                        <div className="card">
                          <div className="flex items-center justify-between">
                            <div>
                              <p className="caption-text">Revenue</p>
                              <p className="text-lg md:text-xl font-bold">$24,582</p>
                              <p className="text-xs text-blue-600">↗ +8% this week</p>
                            </div>
                            <div className="p-2 bg-blue-50 rounded-lg">
                              <TrendingUp className="h-4 w-4 md:h-5 md:w-5 text-blue-600" />
                            </div>
                          </div>
                        </div>
                        <div className="card">
                          <div className="flex items-center justify-between">
                            <div>
                              <p className="caption-text">Active Orders</p>
                              <p className="text-lg md:text-xl font-bold text-purple-600">8</p>
                              <p className="text-xs text-purple-600">Purchase Manager</p>
                            </div>
                            <div className="p-2 bg-purple-50 rounded-lg">
                              <Plus className="h-4 w-4 md:h-5 md:w-5 text-purple-600" />
                            </div>
                          </div>
                        </div>
                      </div>
                      
                      {/* Smart Restock Alerts */}
                      <div className="card">
                        <div className="flex items-center justify-between mb-4">
                          <h4 className="text-sm md:text-base font-semibold">Smart Restock Alerts</h4>
                          <span className="inline-flex items-center px-2 py-1 bg-red-100 text-red-800 text-xs font-medium rounded-full">
                            🚨 CRITICAL
                          </span>
                        </div>
                        <div className="space-y-3">
                          <div className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
                            <div className="flex items-center space-x-3">
                              <div className="w-8 h-8 bg-gradient-to-br from-blue-50 to-indigo-100 rounded border flex items-center justify-center">
                                <Package className="h-4 w-4 text-blue-600" />
                              </div>
                              <div>
                                <p className="font-medium text-sm">B08XYZ123</p>
                                <p className="text-xs text-gray-500">Wireless Headphones</p>
                              </div>
                            </div>
                            <div className="text-right">
                              <p className="text-sm text-red-600 font-medium">3 days left</p>
                              <p className="text-xs text-gray-500">Stock: 12 • Order: 50</p>
                            </div>
                          </div>
                          <div className="flex items-center justify-between py-2">
                            <div className="flex items-center space-x-3">
                              <div className="w-8 h-8 bg-gradient-to-br from-blue-50 to-indigo-100 rounded border flex items-center justify-center">
                                <Package className="h-4 w-4 text-blue-600" />
                              </div>
                              <div>
                                <p className="font-medium text-sm">B07ABC456</p>
                                <p className="text-xs text-gray-500">Phone Case - Clear</p>
                              </div>
                            </div>
                            <div className="text-right">
                              <p className="text-sm text-amber-600 font-medium">7 days left</p>
                              <p className="text-xs text-gray-500">Stock: 25 • Order: 100</p>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="py-16 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-2xl md:text-3xl font-bold text-gray-900 mb-3">
              Everything you need to scale
            </h2>
            <p className="text-gray-600 max-w-2xl mx-auto">
              Professional tools designed specifically for Amazon sellers. From inventory management to team collaboration.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            {features.map((feature, index) => (
              <div key={index} className="card text-center hover:shadow-md transition-shadow">
                <div className="text-builders-500 flex justify-center mb-3">
                  {feature.icon}
                </div>
                <h3 className="heading-sm text-gray-900 mb-2">{feature.title}</h3>
                <p className="body-text text-gray-600">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Dashboard Features */}
      <section id="dashboard" className="py-16 bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-2xl md:text-3xl font-bold text-gray-900 mb-3">
              Complete Dashboard Suite
            </h2>
            <p className="text-gray-600">
              All the tools you need in one unified platform
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
            {dashboardFeatures.map((feature, index) => (
              <div key={index} className="card hover:shadow-md transition-shadow">
                <div className="flex items-start space-x-3">
                  <div className="p-2 bg-amber-50 rounded-lg">
                    {feature.icon}
                  </div>
                  <div>
                    <h3 className="heading-sm text-gray-900 mb-1">{feature.title}</h3>
                    <p className="body-text text-gray-600">{feature.description}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="py-12 bg-gradient-to-r from-slate-900 to-slate-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid md:grid-cols-4 gap-6 text-center">
            <div>
              <div className="text-2xl font-bold text-amber-400 mb-1">1,000+</div>
              <div className="body-text text-slate-300">Active Sellers</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-amber-400 mb-1">$2.5M+</div>
              <div className="body-text text-slate-300">Reimbursements Found</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-amber-400 mb-1">99.9%</div>
              <div className="body-text text-slate-300">Uptime</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-amber-400 mb-1">24/7</div>
              <div className="body-text text-slate-300">Support</div>
            </div>
          </div>
        </div>
      </section>

      {/* Testimonials Section */}
      <section id="testimonials" className="py-16 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-2xl md:text-3xl font-bold text-gray-900 mb-3">
              Trusted by sellers worldwide
            </h2>
            <p className="text-gray-600">
              See what our customers say about their results
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            {testimonials.map((testimonial, index) => (
              <div key={index} className="card">
                <div className="flex mb-3">
                  {renderStars(testimonial.rating)}
                </div>
                <p className="body-text text-gray-600 mb-4 italic">"{testimonial.content}"</p>
                <div>
                  <div className="emphasis-text text-gray-900">{testimonial.name}</div>
                  <div className="caption-text">{testimonial.role}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-16 bg-gradient-to-r from-builders-500 to-builders-600">
        <div className="max-w-4xl mx-auto text-center px-4 sm:px-6 lg:px-8">
          <h2 className="text-2xl md:text-3xl font-bold text-white mb-4">
            Ready to optimize your Amazon business?
          </h2>
          <p className="text-lg text-amber-100 mb-6">
            Join thousands of sellers already using DMS to maximize their profits and streamline operations.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Link 
              to="/login"
              className="inline-flex items-center bg-white hover:bg-gray-100 text-builders-600 px-6 py-3 rounded-lg font-medium shadow-lg transition-colors"
            >
              Start Free Trial
              <ArrowRight className="ml-2 h-4 w-4" />
            </Link>
            <button className="border-2 border-white text-white hover:bg-white hover:text-builders-600 px-6 py-3 rounded-lg font-medium transition-colors">
              Contact Sales
            </button>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-slate-900 text-white py-8">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid md:grid-cols-4 gap-6">
            <div className="md:col-span-2">
              <div className="flex items-center mb-3">
                <div className="p-2 bg-gradient-to-br from-amber-400 to-amber-600 rounded-lg shadow-lg">
                  <ShoppingCart className="h-5 w-5 text-white" />
                </div>
                <div className="ml-3">
                  <span className="text-lg font-bold">DMS</span>
                  <p className="text-xs text-slate-400">Dashboard</p>
                </div>
              </div>
              <p className="body-text text-slate-400 max-w-md">
                Professional dashboard for Amazon sellers. Streamline your operations, maximize profits, and scale your business with confidence.
              </p>
            </div>
            
            <div>
              <h4 className="heading-sm mb-3">Product</h4>
              <ul className="space-y-2 body-text text-slate-400">
                <li><button className="hover:text-white transition-colors text-left">Features</button></li>
                <li><button className="hover:text-white transition-colors text-left">Dashboard</button></li>
                <li><button className="hover:text-white transition-colors text-left">Integrations</button></li>
                <li><button className="hover:text-white transition-colors text-left">API</button></li>
              </ul>
            </div>
            
            <div>
              <h4 className="heading-sm mb-3">Support</h4>
              <ul className="space-y-2 body-text text-slate-400">
                <li><button className="hover:text-white transition-colors text-left">Help Center</button></li>
                <li><button className="hover:text-white transition-colors text-left">Documentation</button></li>
                <li><button className="hover:text-white transition-colors text-left">Contact</button></li>
                <li><button className="hover:text-white transition-colors text-left">Privacy</button></li>
              </ul>
            </div>
          </div>
          
          <div className="border-t border-slate-800 mt-8 pt-6 text-center">
            <p className="body-text text-slate-400">&copy; 2024 DMS. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default LandingPage;