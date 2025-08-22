/**
 * Reusable Loading Spinner Component
 * 
 * Provides consistent loading indicators across the application.
 * Safe refactor - standardizes existing loading patterns.
 */

import React from 'react';
import { Loader2 } from 'lucide-react';

const LoadingSpinner = ({ 
  size = 'medium', 
  text = null, 
  className = '',
  showText = true,
  color = 'blue'
}) => {
  const sizeClasses = {
    small: 'h-4 w-4',
    medium: 'h-6 w-6', 
    large: 'h-8 w-8',
    xlarge: 'h-12 w-12'
  };

  const colorClasses = {
    blue: 'text-blue-600',
    gray: 'text-gray-600',
    green: 'text-green-600',
    red: 'text-red-600',
    purple: 'text-purple-600',
    white: 'text-white'
  };

  const textSizeClasses = {
    small: 'text-xs',
    medium: 'text-sm',
    large: 'text-base',
    xlarge: 'text-lg'
  };

  return (
    <div className={`flex flex-col items-center justify-center ${className}`}>
      <Loader2 
        className={`animate-spin ${sizeClasses[size]} ${colorClasses[color]}`}
      />
      {showText && (
        <span className={`mt-2 ${textSizeClasses[size]} ${colorClasses[color]} opacity-75`}>
          {text || 'Loading...'}
        </span>
      )}
    </div>
  );
};

/**
 * Inline spinner for buttons and small spaces
 */
export const InlineSpinner = ({ size = 'small', className = '' }) => {
  const sizeClasses = {
    small: 'h-3 w-3',
    medium: 'h-4 w-4',
    large: 'h-5 w-5'
  };

  return (
    <Loader2 
      className={`animate-spin ${sizeClasses[size]} ${className}`}
    />
  );
};

/**
 * Full page loading overlay
 */
export const PageLoader = ({ text = 'Loading...', backdrop = true }) => {
  return (
    <div className={`fixed inset-0 z-50 flex items-center justify-center ${
      backdrop ? 'bg-white bg-opacity-75' : ''
    }`}>
      <div className="text-center">
        <LoadingSpinner size="xlarge" text={text} />
      </div>
    </div>
  );
};

/**
 * Loading state for tables and lists
 */
export const TableLoader = ({ rows = 5, columns = 4 }) => {
  return (
    <div className="animate-pulse">
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <div key={rowIndex} className="flex space-x-4 py-3 border-b border-gray-200">
          {Array.from({ length: columns }).map((_, colIndex) => (
            <div 
              key={colIndex} 
              className="h-4 bg-gray-200 rounded flex-1"
              style={{ 
                width: colIndex === 0 ? '25%' : colIndex === columns - 1 ? '15%' : '20%' 
              }}
            />
          ))}
        </div>
      ))}
    </div>
  );
};

/**
 * Loading skeleton for cards
 */
export const CardLoader = ({ className = '' }) => {
  return (
    <div className={`animate-pulse p-4 ${className}`}>
      <div className="h-4 bg-gray-200 rounded w-3/4 mb-2"></div>
      <div className="h-3 bg-gray-200 rounded w-1/2 mb-4"></div>
      <div className="space-y-2">
        <div className="h-3 bg-gray-200 rounded"></div>
        <div className="h-3 bg-gray-200 rounded w-5/6"></div>
      </div>
    </div>
  );
};

export default LoadingSpinner;