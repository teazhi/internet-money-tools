import React from 'react';
import { Link } from 'react-router-dom';
import { 
  Shield, 
  FileText,
  Package,
  TrendingDown
} from 'lucide-react';

const AdminTasks = () => {
  const tasks = [
    {
      id: 'update-seller-costs',
      name: 'Update Seller Costs',
      description: 'Upload Excel files to update seller costs with latest sourcing data from Google Sheets',
      icon: FileText,
      color: 'bg-blue-500',
      href: '/dashboard/admin-tasks/update-seller-costs'
    },
    {
      id: 'missing-listings',
      name: 'Missing Listings',
      description: 'Track and manage your expected arrivals and inventory gaps',
      icon: Package,
      color: 'bg-orange-500',
      href: '/dashboard/admin-tasks/missing-listings'
    },
    {
      id: 'reimbursements',
      name: 'Reimbursements',
      description: 'Automated reimbursement analysis and claim tracking',
      icon: TrendingDown,
      color: 'bg-green-500',
      href: '/dashboard/admin-tasks/reimbursements'
    }
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center space-x-3">
        <Shield className="h-8 w-8 text-builders-500" />
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Admin Tasks</h1>
          <p className="text-gray-600">Manage your account and administrative functions</p>
        </div>
      </div>

      {/* Tasks Selection Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {tasks.map((task) => {
          const Icon = task.icon;
          const isAvailable = task.href !== null;
          
          return (
            <Link
              key={task.id}
              to={task.href}
              className={`group relative bg-white rounded-lg shadow-sm border border-gray-200 p-6 transition-all duration-200 ${
                isAvailable 
                  ? 'hover:shadow-md hover:border-gray-300 cursor-pointer' 
                  : 'opacity-50 cursor-not-allowed pointer-events-none'
              }`}
            >
              {/* Icon */}
              <div className={`inline-flex items-center justify-center w-12 h-12 rounded-lg ${task.color} mb-4`}>
                <Icon className="h-6 w-6 text-white" />
              </div>

              {/* Content */}
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">
                  {task.name}
                </h3>
                <p className="text-gray-600 text-sm mb-4">
                  {task.description}
                </p>
              </div>

              {/* Status Badge */}
              <div className="absolute top-4 right-4">
                <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                  Available
                </span>
              </div>

              {/* Hover Effect Arrow */}
              <div className="absolute bottom-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity">
                <div className="w-6 h-6 bg-gray-100 rounded-full flex items-center justify-center">
                  <div className="h-3 w-3 border-r-2 border-t-2 border-gray-600 transform rotate-45" />
                </div>
              </div>
            </Link>
          );
        })}
      </div>

      {/* Info Box */}
      <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
        <div className="flex items-start space-x-3">
          <Shield className="h-5 w-5 text-purple-500 mt-0.5" />
          <div>
            <h4 className="text-sm font-medium text-purple-900">Administrative Functions</h4>
            <p className="text-sm text-purple-700 mt-1">
              These tools help you manage core administrative tasks for your Amazon business. 
              Update costs, track missing inventory, and manage reimbursements all in one place.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AdminTasks;