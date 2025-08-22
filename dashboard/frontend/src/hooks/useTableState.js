/**
 * Reusable Table State Management Hook
 * 
 * Provides standardized table functionality including filtering, sorting,
 * and pagination. Safe refactor - extracts common patterns.
 */

import { useState, useMemo, useCallback } from 'react';

export const useTableState = (initialData = [], options = {}) => {
  const {
    searchFields = [],
    defaultSort = null,
    pageSize = 25,
    filterFunctions = {}
  } = options;

  // Core state
  const [data, setData] = useState(initialData);
  const [searchTerm, setSearchTerm] = useState('');
  const [sortConfig, setSortConfig] = useState(defaultSort);
  const [currentPage, setCurrentPage] = useState(1);
  const [activeFilters, setActiveFilters] = useState({});

  // Update data when initialData changes
  const updateData = useCallback((newData) => {
    setData(newData);
    setCurrentPage(1); // Reset to first page when data changes
  }, []);

  // Search functionality
  const searchData = useMemo(() => {
    if (!searchTerm || !searchFields.length) {
      return data;
    }

    const lowercaseSearch = searchTerm.toLowerCase();
    
    return data.filter(item => {
      return searchFields.some(field => {
        const value = getNestedValue(item, field);
        return value && value.toString().toLowerCase().includes(lowercaseSearch);
      });
    });
  }, [data, searchTerm, searchFields]);

  // Filter functionality
  const filteredData = useMemo(() => {
    let result = searchData;

    Object.entries(activeFilters).forEach(([filterKey, filterValue]) => {
      if (filterValue && filterFunctions[filterKey]) {
        result = result.filter(item => filterFunctions[filterKey](item, filterValue));
      }
    });

    return result;
  }, [searchData, activeFilters, filterFunctions]);

  // Sort functionality
  const sortedData = useMemo(() => {
    if (!sortConfig) {
      return filteredData;
    }

    const { key, direction } = sortConfig;
    
    return [...filteredData].sort((a, b) => {
      const aValue = getNestedValue(a, key);
      const bValue = getNestedValue(b, key);

      // Handle null/undefined values
      if (aValue == null && bValue == null) return 0;
      if (aValue == null) return direction === 'asc' ? -1 : 1;
      if (bValue == null) return direction === 'asc' ? 1 : -1;

      // Handle different data types
      if (typeof aValue === 'number' && typeof bValue === 'number') {
        return direction === 'asc' ? aValue - bValue : bValue - aValue;
      }

      // Handle dates
      if (aValue instanceof Date && bValue instanceof Date) {
        return direction === 'asc' 
          ? aValue.getTime() - bValue.getTime()
          : bValue.getTime() - aValue.getTime();
      }

      // Handle strings (case-insensitive)
      const aStr = aValue.toString().toLowerCase();
      const bStr = bValue.toString().toLowerCase();
      
      if (aStr < bStr) return direction === 'asc' ? -1 : 1;
      if (aStr > bStr) return direction === 'asc' ? 1 : -1;
      return 0;
    });
  }, [filteredData, sortConfig]);

  // Pagination
  const paginatedData = useMemo(() => {
    const startIndex = (currentPage - 1) * pageSize;
    return sortedData.slice(startIndex, startIndex + pageSize);
  }, [sortedData, currentPage, pageSize]);

  // Calculated values
  const totalPages = Math.ceil(sortedData.length / pageSize);
  const totalItems = sortedData.length;
  const startItem = totalItems > 0 ? (currentPage - 1) * pageSize + 1 : 0;
  const endItem = Math.min(currentPage * pageSize, totalItems);

  // Action functions
  const handleSort = useCallback((key) => {
    setSortConfig(prevConfig => {
      if (prevConfig?.key === key) {
        // Toggle direction or clear sort
        if (prevConfig.direction === 'asc') {
          return { key, direction: 'desc' };
        } else {
          return null; // Clear sort
        }
      } else {
        return { key, direction: 'asc' };
      }
    });
  }, []);

  const handleSearch = useCallback((term) => {
    setSearchTerm(term);
    setCurrentPage(1); // Reset to first page when searching
  }, []);

  const handleFilter = useCallback((filterKey, filterValue) => {
    setActiveFilters(prev => ({
      ...prev,
      [filterKey]: filterValue
    }));
    setCurrentPage(1); // Reset to first page when filtering
  }, []);

  const clearFilters = useCallback(() => {
    setActiveFilters({});
    setSearchTerm('');
    setSortConfig(defaultSort);
    setCurrentPage(1);
  }, [defaultSort]);

  const goToPage = useCallback((page) => {
    setCurrentPage(Math.max(1, Math.min(page, totalPages)));
  }, [totalPages]);

  const nextPage = useCallback(() => {
    goToPage(currentPage + 1);
  }, [currentPage, goToPage]);

  const prevPage = useCallback(() => {
    goToPage(currentPage - 1);
  }, [currentPage, goToPage]);

  return {
    // Data
    data: paginatedData,
    allData: sortedData,
    rawData: data,
    
    // State
    searchTerm,
    sortConfig,
    currentPage,
    activeFilters,
    
    // Computed values
    totalPages,
    totalItems,
    startItem,
    endItem,
    hasNextPage: currentPage < totalPages,
    hasPrevPage: currentPage > 1,
    
    // Actions
    updateData,
    handleSort,
    handleSearch,
    handleFilter,
    clearFilters,
    goToPage,
    nextPage,
    prevPage
  };
};

/**
 * Get nested value from object using dot notation
 * e.g., getNestedValue(obj, 'user.profile.name')
 */
function getNestedValue(obj, path) {
  return path.split('.').reduce((current, key) => {
    return current?.[key];
  }, obj);
}