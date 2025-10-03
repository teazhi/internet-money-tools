import React from 'react';
import { Check, X, Zap, TrendingUp } from 'lucide-react';

const Pricing = () => {
  const plans = [
    {
      name: 'Professional',
      price: '$49.99',
      period: '/month',
      description: 'Perfect for growing Amazon sellers ready to scale smartly',
      icon: Zap,
      color: 'blue',
      features: [
        {
          name: 'Smart Restock Analytics',
          included: true,
          description: 'AI-powered inventory recommendations'
        },
        {
          name: 'All Product Analytics Dashboard',
          included: true,
          description: 'Comprehensive inventory insights'
        },
        {
          name: 'Google Sheets Integration',
          included: true,
          description: 'Sync with your leads and COGS data'
        },
        {
          name: 'Discount Opportunity Alerts',
          included: true,
          description: 'Real-time sourcing opportunities'
        },
        {
          name: 'Bulk COGS Updates',
          included: true,
          description: 'Update seller costs in bulk'
        },
        {
          name: 'Basic Email Monitoring',
          included: true,
          description: 'Track important seller emails'
        },
        {
          name: 'Up to 500 SKUs',
          included: true,
          description: 'Track up to 500 products'
        },
        {
          name: 'VA Sub-accounts',
          included: false,
          description: 'Manage team members'
        },
        {
          name: 'Priority Support',
          included: false,
          description: '24-hour response time'
        },
        {
          name: 'Custom Integrations',
          included: false,
          description: 'API access & webhooks'
        }
      ],
      cta: 'Start Professional',
      popular: false
    },
    {
      name: 'Scaler',
      price: '$99.99',
      period: '/month',
      description: 'For established sellers optimizing operations at scale',
      icon: TrendingUp,
      color: 'purple',
      features: [
        {
          name: 'Everything in Professional',
          included: true,
          description: 'All Professional features included'
        },
        {
          name: 'Unlimited SKUs',
          included: true,
          description: 'No limits on product tracking'
        },
        {
          name: 'VA Sub-accounts',
          included: true,
          description: 'Up to 5 team member accounts'
        },
        {
          name: 'Advanced Reimbursement Analyzer',
          included: true,
          description: 'Maximize FBA reimbursements'
        },
        {
          name: 'Multi-marketplace Support',
          included: true,
          description: 'Manage inventory across channels'
        },
        {
          name: 'Priority Email Monitoring',
          included: true,
          description: 'Real-time alerts & automation'
        },
        {
          name: 'Custom Reporting',
          included: true,
          description: 'Tailored analytics & exports'
        },
        {
          name: 'API Access',
          included: true,
          description: 'Integrate with your tools'
        },
        {
          name: 'Priority Support',
          included: true,
          description: 'Same-day response'
        },
        {
          name: 'Onboarding Session',
          included: true,
          description: '1-on-1 setup assistance'
        }
      ],
      cta: 'Scale Your Business',
      popular: true
    }
  ];

  return (
    <div className="bg-gray-50 py-24" id="pricing">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="text-center">
          <h2 className="text-3xl font-extrabold text-gray-900 sm:text-4xl">
            Simple, Transparent Pricing
          </h2>
          <p className="mt-4 max-w-2xl mx-auto text-xl text-gray-600">
            Choose the plan that fits your business. Upgrade or downgrade anytime.
          </p>
        </div>

        {/* Pricing Cards */}
        <div className="mt-16 grid grid-cols-1 gap-8 lg:grid-cols-2 lg:gap-12 max-w-5xl mx-auto">
          {plans.map((plan) => (
            <div
              key={plan.name}
              className={`relative bg-white rounded-2xl shadow-lg overflow-hidden ${
                plan.popular ? 'ring-2 ring-purple-600' : ''
              }`}
            >
              {/* Popular Badge */}
              {plan.popular && (
                <div className="absolute top-0 right-0 bg-purple-600 text-white px-4 py-1 rounded-bl-lg text-sm font-medium">
                  Most Popular
                </div>
              )}

              {/* Plan Header */}
              <div className="p-8">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-2xl font-bold text-gray-900">{plan.name}</h3>
                  <plan.icon className={`h-8 w-8 text-${plan.color}-600`} />
                </div>
                
                <p className="text-gray-600 mb-6">{plan.description}</p>
                
                <div className="flex items-baseline mb-8">
                  <span className="text-5xl font-extrabold text-gray-900">{plan.price}</span>
                  <span className="text-xl text-gray-500 ml-2">{plan.period}</span>
                </div>

                {/* CTA Button */}
                <button
                  className={`w-full py-3 px-6 rounded-lg font-medium transition-colors ${
                    plan.popular
                      ? 'bg-purple-600 text-white hover:bg-purple-700'
                      : 'bg-gray-100 text-gray-900 hover:bg-gray-200'
                  }`}
                >
                  {plan.cta}
                </button>
              </div>

              {/* Features List */}
              <div className="px-8 pb-8">
                <h4 className="text-sm font-semibold text-gray-900 uppercase tracking-wide mb-4">
                  What's Included
                </h4>
                <ul className="space-y-3">
                  {plan.features.map((feature) => (
                    <li key={feature.name} className="flex items-start">
                      <div className="flex-shrink-0 mt-0.5">
                        {feature.included ? (
                          <Check className="h-5 w-5 text-green-500" />
                        ) : (
                          <X className="h-5 w-5 text-gray-300" />
                        )}
                      </div>
                      <div className="ml-3">
                        <p className={`text-sm ${
                          feature.included ? 'text-gray-900' : 'text-gray-400'
                        }`}>
                          {feature.name}
                        </p>
                        <p className={`text-xs ${
                          feature.included ? 'text-gray-600' : 'text-gray-400'
                        }`}>
                          {feature.description}
                        </p>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          ))}
        </div>

        {/* Additional Info */}
        <div className="mt-16 text-center">
          <div className="max-w-3xl mx-auto">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              All Plans Include
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm text-gray-600">
              <div className="flex items-center justify-center space-x-2">
                <Check className="h-4 w-4 text-green-500" />
                <span>SSL Encrypted Data</span>
              </div>
              <div className="flex items-center justify-center space-x-2">
                <Check className="h-4 w-4 text-green-500" />
                <span>Daily Backups</span>
              </div>
              <div className="flex items-center justify-center space-x-2">
                <Check className="h-4 w-4 text-green-500" />
                <span>Cancel Anytime</span>
              </div>
            </div>
          </div>

          {/* FAQ Link */}
          <div className="mt-8">
            <p className="text-gray-600">
              Questions about pricing?{' '}
              <a href="#faq" className="text-blue-600 hover:text-blue-700 font-medium">
                Check our FAQ
              </a>{' '}
              or{' '}
              <a href="#contact" className="text-blue-600 hover:text-blue-700 font-medium">
                contact sales
              </a>
            </p>
          </div>

          {/* Money Back Guarantee */}
          <div className="mt-8 bg-green-50 rounded-lg p-4 max-w-md mx-auto">
            <p className="text-green-800 font-medium">
              💰 30-Day Money-Back Guarantee
            </p>
            <p className="text-green-700 text-sm mt-1">
              Try risk-free. If you're not satisfied, get a full refund.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Pricing;