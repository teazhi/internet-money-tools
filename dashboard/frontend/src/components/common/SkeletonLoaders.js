import React from 'react';

// Skeleton pulse animation
const SkeletonPulse = ({ className = '' }) => (
  <div className={`animate-pulse bg-gray-200 rounded ${className}`} />
);

// Text skeleton with multiple lines
export const SkeletonText = ({ lines = 1, className = '' }) => (
  <div className={`space-y-2 ${className}`}>
    {Array.from({ length: lines }).map((_, i) => (
      <SkeletonPulse 
        key={i} 
        className={`h-4 ${i === lines - 1 && lines > 1 ? 'w-3/4' : 'w-full'}`} 
      />
    ))}
  </div>
);

// Number/metric skeleton
export const SkeletonMetric = ({ className = '' }) => (
  <div className={`${className}`}>
    <SkeletonPulse className="h-8 w-24" />
  </div>
);

// Card skeleton
export const SkeletonCard = ({ className = '' }) => (
  <div className={`card ${className}`}>
    <div className="flex items-center">
      <div className="flex-shrink-0">
        <SkeletonPulse className="h-8 w-8 rounded" />
      </div>
      <div className="ml-4 flex-1">
        <SkeletonPulse className="h-4 w-24 mb-2" />
        <SkeletonPulse className="h-8 w-16" />
      </div>
    </div>
  </div>
);

// Table row skeleton
export const SkeletonTableRow = ({ columns = 4 }) => (
  <div className="flex items-center justify-between py-3 px-4 border-b border-gray-100">
    {Array.from({ length: columns }).map((_, i) => (
      <SkeletonPulse 
        key={i} 
        className={`h-4 ${i === 0 ? 'w-32' : i === columns - 1 ? 'w-20' : 'w-24'}`} 
      />
    ))}
  </div>
);

// List item skeleton
export const SkeletonListItem = () => (
  <div className="flex items-center justify-between py-2">
    <div className="flex items-center space-x-3">
      <SkeletonPulse className="h-6 w-6 rounded-full" />
      <div>
        <SkeletonPulse className="h-4 w-24 mb-1" />
        <SkeletonPulse className="h-3 w-32" />
      </div>
    </div>
    <SkeletonPulse className="h-4 w-16" />
  </div>
);

// Product item skeleton (for top products)
export const SkeletonProductItem = () => (
  <div className="flex items-center justify-between">
    <div className="flex items-center space-x-3">
      <SkeletonPulse className="h-6 w-6 rounded-full" />
      <div>
        <SkeletonPulse className="h-4 w-20 mb-1" />
        <SkeletonPulse className="h-3 w-28" />
      </div>
    </div>
    <div className="text-right">
      <SkeletonPulse className="h-4 w-16 mb-1" />
      <SkeletonPulse className="h-3 w-12" />
    </div>
  </div>
);

// Stock alert skeleton
export const SkeletonStockAlert = () => (
  <div className="flex items-center justify-between">
    <div className="flex-1">
      <div className="flex items-center space-x-2 mb-1">
        <SkeletonPulse className="h-4 w-20" />
      </div>
      <SkeletonPulse className="h-3 w-40" />
    </div>
    <div className="text-right ml-4">
      <SkeletonPulse className="h-4 w-16 mb-1" />
      <SkeletonPulse className="h-3 w-24" />
    </div>
  </div>
);

// Chart skeleton
export const SkeletonChart = ({ height = 'h-64' }) => (
  <div className={`${height} flex items-end justify-between space-x-2 px-4`}>
    {Array.from({ length: 7 }).map((_, i) => (
      <SkeletonPulse
        key={i}
        className="flex-1"
        style={{ height: `${Math.random() * 60 + 40}%` }}
      />
    ))}
  </div>
);

// Badge skeleton
export const SkeletonBadge = () => (
  <SkeletonPulse className="h-6 w-20 rounded-full" />
);

// Welcome header skeleton
export const SkeletonWelcomeHeader = () => (
  <div className="bg-gradient-to-r from-builders-500 to-builders-600 rounded-lg shadow-sm p-6 text-white">
    <div className="flex justify-between items-start">
      <div>
        <SkeletonPulse className="h-8 w-64 mb-2 bg-white/20" />
        <SkeletonPulse className="h-4 w-96 mb-2 bg-white/20" />
        <SkeletonPulse className="h-3 w-48 bg-white/20" />
      </div>
      <SkeletonPulse className="h-10 w-10 rounded-lg bg-white/20" />
    </div>
  </div>
);

// Table skeleton
export const SkeletonTable = ({ columns = 6, rows = 3, title = "Loading Data" }) => (
  <div className="card">
    <h3 className="text-lg font-semibold text-gray-900 mb-4">{title}</h3>
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            {Array.from({ length: columns }).map((_, i) => (
              <th key={i} className="px-6 py-3 text-left">
                <SkeletonPulse className="h-4 w-20" />
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {Array.from({ length: rows }).map((_, rowIndex) => (
            <tr key={rowIndex}>
              {Array.from({ length: columns }).map((_, colIndex) => (
                <td key={colIndex} className="px-6 py-4">
                  <SkeletonPulse className={`h-4 ${colIndex === 0 ? 'w-24' : colIndex === 1 ? 'w-32' : 'w-16'}`} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  </div>
);