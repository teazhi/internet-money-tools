import React from 'react';
import { Check, X, Minus } from 'lucide-react';

const PricingComparison = () => {
  const features = [
    {
      category: 'Core Features',
      items: [
        {
          name: 'Smart Restock Analytics',
          professional: true,
          scaler: true,
          description: 'AI-powered inventory recommendations based on velocity and seasonality'
        },
        {
          name: 'Product Analytics Dashboard',
          professional: true,
          scaler: true,
          description: 'Real-time insights on all your products'
        },
        {
          name: 'Google Sheets Integration',
          professional: true,
          scaler: true,
          description: 'Seamlessly sync with your existing spreadsheets'
        },
        {
          name: 'SKU Limit',
          professional: '500',
          scaler: 'Unlimited',
          description: 'Number of products you can track'
        }
      ]
    },
    {
      category: 'Automation & Efficiency',
      items: [
        {
          name: 'Bulk COGS Updates',
          professional: true,
          scaler: true,
          description: 'Update costs for hundreds of products at once'
        },
        {
          name: 'Email Monitoring',
          professional: 'Basic',
          scaler: 'Priority',
          description: 'Automated tracking of supplier and marketplace emails'
        },
        {
          name: 'Discount Alerts',
          professional: true,
          scaler: true,
          description: 'Real-time notifications for sourcing opportunities'
        },
        {
          name: 'Custom Automation Rules',
          professional: false,
          scaler: true,
          description: 'Set up custom triggers and workflows'
        }
      ]
    },
    {
      category: 'Team & Collaboration',
      items: [
        {
          name: 'User Accounts',
          professional: '1',
          scaler: 'Up to 6',
          description: 'Main account plus team members'
        },
        {
          name: 'VA Sub-accounts',
          professional: false,
          scaler: '5 included',
          description: 'Secure access for your virtual assistants'
        },
        {
          name: 'Permission Controls',
          professional: false,
          scaler: true,
          description: 'Granular access control for team members'
        },
        {
          name: 'Activity Logs',
          professional: false,
          scaler: true,
          description: 'Track all team actions and changes'
        }
      ]
    },
    {
      category: 'Advanced Features',
      items: [
        {
          name: 'Reimbursement Analyzer',
          professional: false,
          scaler: true,
          description: 'Identify and claim FBA reimbursements'
        },
        {
          name: 'Multi-marketplace',
          professional: false,
          scaler: true,
          description: 'Manage inventory across Amazon, eBay, etc.'
        },
        {
          name: 'API Access',
          professional: false,
          scaler: true,
          description: 'Integrate with your custom tools'
        },
        {
          name: 'Custom Reports',
          professional: 'Basic',
          scaler: 'Advanced',
          description: 'Tailored analytics and exports'
        }
      ]
    },
    {
      category: 'Support & Services',
      items: [
        {
          name: 'Email Support',
          professional: '48 hours',
          scaler: 'Same day',
          description: 'Response time for support tickets'
        },
        {
          name: 'Onboarding',
          professional: 'Self-serve',
          scaler: '1-on-1 session',
          description: 'Getting started assistance'
        },
        {
          name: 'Priority Updates',
          professional: false,
          scaler: true,
          description: 'Early access to new features'
        },
        {
          name: 'Dedicated Account Manager',
          professional: false,
          scaler: 'Available',
          description: 'Personal point of contact for enterprise needs'
        }
      ]
    }
  ];

  const renderValue = (value) => {
    if (value === true) return <Check className="h-5 w-5 text-green-500 mx-auto" />;
    if (value === false) return <X className="h-5 w-5 text-gray-300 mx-auto" />;
    if (typeof value === 'string') return <span className="text-sm font-medium">{value}</span>;
    return <Minus className="h-5 w-5 text-gray-400 mx-auto" />;
  };

  return (
    <div className="bg-white py-16">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-12">
          <h2 className="text-3xl font-extrabold text-gray-900">
            Detailed Feature Comparison
          </h2>
          <p className="mt-4 text-lg text-gray-600">
            See exactly what you get with each plan
          </p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left py-4 px-4 text-sm font-medium text-gray-900">
                  Features
                </th>
                <th className="text-center py-4 px-4">
                  <div className="text-lg font-bold text-gray-900">Professional</div>
                  <div className="text-2xl font-bold text-blue-600 mt-1">$49.99</div>
                  <div className="text-sm text-gray-500">per month</div>
                </th>
                <th className="text-center py-4 px-4">
                  <div className="inline-flex items-center">
                    <span className="text-lg font-bold text-gray-900">Scaler</span>
                    <span className="ml-2 bg-purple-100 text-purple-800 text-xs font-medium px-2 py-1 rounded">
                      Popular
                    </span>
                  </div>
                  <div className="text-2xl font-bold text-purple-600 mt-1">$99.99</div>
                  <div className="text-sm text-gray-500">per month</div>
                </th>
              </tr>
            </thead>
            <tbody>
              {features.map((category, categoryIdx) => (
                <React.Fragment key={categoryIdx}>
                  <tr className="bg-gray-50">
                    <td colSpan="3" className="py-3 px-4 text-sm font-semibold text-gray-900">
                      {category.category}
                    </td>
                  </tr>
                  {category.items.map((feature, featureIdx) => (
                    <tr key={featureIdx} className="border-b border-gray-100">
                      <td className="py-4 px-4">
                        <div className="text-sm font-medium text-gray-900">{feature.name}</div>
                        <div className="text-xs text-gray-500 mt-1">{feature.description}</div>
                      </td>
                      <td className="py-4 px-4 text-center">
                        {renderValue(feature.professional)}
                      </td>
                      <td className="py-4 px-4 text-center">
                        {renderValue(feature.scaler)}
                      </td>
                    </tr>
                  ))}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>

        {/* CTAs */}
        <div className="mt-12 grid grid-cols-1 gap-4 sm:grid-cols-2 max-w-md mx-auto">
          <button className="w-full bg-gray-100 text-gray-900 py-3 px-6 rounded-lg font-medium hover:bg-gray-200 transition-colors">
            Start with Professional
          </button>
          <button className="w-full bg-purple-600 text-white py-3 px-6 rounded-lg font-medium hover:bg-purple-700 transition-colors">
            Start with Scaler
          </button>
        </div>
      </div>
    </div>
  );
};

export default PricingComparison;