import React, { useState, useEffect, useMemo } from 'react';
import {
  Search,
  Filter,
  GripVertical,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  RotateCcw,
  Package,
  Maximize2,
  Minimize2,
  X
} from 'lucide-react';

/**
 * StandardTable - A reusable table component with consistent styling and features
 * Based on the Smart Restock Recommendations table design
 */
const StandardTable = ({
  // Data
  data = [],
  
  // Configuration
  tableKey, // Unique key for localStorage (e.g., 'discount-opportunities')
  columns, // Column definitions object
  defaultColumnOrder, // Default column order array
  
  // Rendering
  renderCell, // Function to render cell content: (columnKey, row) => JSX
  
  // Features (optional)
  enableSearch = true,
  enableFilters = false,
  enableSorting = true,
  enableColumnReordering = true,
  enableColumnResetting = true,
  enableFullscreen = true,
  
  // Search
  searchPlaceholder = "Search...",
  searchFields = [], // Array of field names to search in
  
  // Filters
  filters = [], // Array of filter objects: { key, label, options: [{ value, label }] }
  
  // Empty state
  emptyIcon: EmptyIcon = Package,
  emptyTitle = "No Data",
  emptyDescription = "No items found matching your criteria",
  
  // Additional props
  className = "",
  title = "", // Table title for fullscreen mode
  
  // Callbacks
  onRowClick = null, // Optional row click handler
}) => {
  
  // State management
  const [searchQuery, setSearchQuery] = useState('');
  const [activeFilters, setActiveFilters] = useState({});
  const [sortConfig, setSortConfig] = useState({ key: null, direction: 'asc' });
  const [draggedColumn, setDraggedColumn] = useState(null);
  const [dragOverColumn, setDragOverColumn] = useState(null);
  const [dropIndicatorPosition, setDropIndicatorPosition] = useState(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  
  // Column ordering - ensure 'product' is always first and excluded from reordering
  const [columnOrder, setColumnOrder] = useState(() => {
    if (!enableColumnReordering || !tableKey) return defaultColumnOrder;
    
    const saved = localStorage.getItem(`table-column-order-${tableKey}`);
    let order = saved ? JSON.parse(saved) : defaultColumnOrder;
    
    // Ensure 'product' column is always first if it exists
    if (order.includes('product')) {
      order = ['product', ...order.filter(col => col !== 'product')];
    }
    
    return order;
  });
  
  // Initialize filters
  useEffect(() => {
    const initialFilters = {};
    filters.forEach(filter => {
      initialFilters[filter.key] = filter.defaultValue || 'all';
    });
    setActiveFilters(initialFilters);
  }, [filters]);
  
  // Handle escape key for fullscreen
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape' && isFullscreen) {
        setIsFullscreen(false);
      }
    };

    if (isFullscreen) {
      document.addEventListener('keydown', handleEscape);
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = 'auto';
    }

    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.body.style.overflow = 'auto';
    };
  }, [isFullscreen]);
  
  // Sorting function
  const handleSort = (key) => {
    if (!enableSorting) return;
    
    let direction = 'asc';
    if (sortConfig.key === key && sortConfig.direction === 'asc') {
      direction = 'desc';
    }
    setSortConfig({ key, direction });
  };
  
  // Get sort icon
  const getSortIcon = (columnKey) => {
    if (!enableSorting) return null;
    
    if (sortConfig.key !== columnKey) {
      return <ArrowUpDown className="h-3 w-3 text-gray-400" />;
    }
    return sortConfig.direction === 'asc' 
      ? <ArrowUp className="h-3 w-3 text-gray-600" />
      : <ArrowDown className="h-3 w-3 text-gray-600" />;
  };
  
  // Drag and drop handlers
  const handleDragStart = (e, columnKey) => {
    if (!enableColumnReordering) return;
    // Prevent dragging the product column
    if (columnKey === 'product') return;
    setDraggedColumn({ key: columnKey });
    e.dataTransfer.effectAllowed = 'move';
  };
  
  const handleDragOver = (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  };
  
  const handleDragEnter = (e, columnKey) => {
    if (!enableColumnReordering || !draggedColumn || draggedColumn.key === columnKey) return;
    // Prevent dropping on the product column
    if (columnKey === 'product') return;
    e.preventDefault();
    
    const rect = e.currentTarget.getBoundingClientRect();
    const mouseX = e.clientX;
    const columnCenter = rect.left + rect.width / 2;
    
    // Determine if we're on the left or right side of the column
    const position = mouseX < columnCenter ? 'left' : 'right';
    
    setDragOverColumn(columnKey);
    setDropIndicatorPosition(position);
  };
  
  const handleDragLeave = (e) => {
    // Only clear drag over if we're actually leaving the column area
    // Check if the related target is not a child of the current target
    if (!e.currentTarget.contains(e.relatedTarget)) {
      setDragOverColumn(null);
      setDropIndicatorPosition(null);
    }
  };
  
  const handleDrop = (e, targetColumnKey) => {
    e.preventDefault();
    
    if (!draggedColumn || !enableColumnReordering) {
      setDraggedColumn(null);
      setDragOverColumn(null);
      setDropIndicatorPosition(null);
      return;
    }
    
    // Prevent dropping on or around the product column
    if (targetColumnKey === 'product' || draggedColumn.key === 'product') {
      setDraggedColumn(null);
      setDragOverColumn(null);
      setDropIndicatorPosition(null);
      return;
    }
    
    const newOrder = [...columnOrder];
    const draggedIndex = newOrder.indexOf(draggedColumn.key);
    const targetIndex = newOrder.indexOf(targetColumnKey);
    
    if (draggedIndex !== -1 && targetIndex !== -1 && draggedIndex !== targetIndex) {
      // Remove dragged item
      const [draggedItem] = newOrder.splice(draggedIndex, 1);
      
      // Determine insertion point based on drop indicator position
      let insertIndex = targetIndex;
      if (dropIndicatorPosition === 'right') {
        insertIndex = targetIndex + 1;
      }
      // Adjust for removed item if inserting after its original position
      if (draggedIndex < insertIndex) {
        insertIndex -= 1;
      }
      
      // Insert at new position
      newOrder.splice(insertIndex, 0, draggedItem);
      
      // Ensure product column stays first after reordering
      const finalOrder = ['product', ...newOrder.filter(col => col !== 'product')];
      
      setColumnOrder(finalOrder);
      
      // Save to localStorage
      if (tableKey) {
        localStorage.setItem(`table-column-order-${tableKey}`, JSON.stringify(finalOrder));
      }
    }
    
    setDraggedColumn(null);
    setDragOverColumn(null);
    setDropIndicatorPosition(null);
  };
  
  const handleDragEnd = () => {
    setDraggedColumn(null);
    setDragOverColumn(null);
    setDropIndicatorPosition(null);
  };
  
  // Reset column order
  const resetColumnOrder = () => {
    if (!enableColumnResetting) return;
    
    // Ensure product column is first when resetting
    let resetOrder = [...defaultColumnOrder];
    if (resetOrder.includes('product')) {
      resetOrder = ['product', ...resetOrder.filter(col => col !== 'product')];
    }
    
    setColumnOrder(resetOrder);
    if (tableKey) {
      localStorage.setItem(`table-column-order-${tableKey}`, JSON.stringify(resetOrder));
    }
  };
  
  // Filter and sort data
  const processedData = useMemo(() => {
    let filtered = [...data];
    
    // Apply search filter
    if (enableSearch && searchQuery && searchFields.length > 0) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(item => 
        searchFields.some(field => {
          const value = item[field];
          return value && String(value).toLowerCase().includes(query);
        })
      );
    }
    
    // Apply custom filters
    if (enableFilters) {
      Object.entries(activeFilters).forEach(([filterKey, filterValue]) => {
        if (filterValue && filterValue !== 'all') {
          const filter = filters.find(f => f.key === filterKey);
          if (filter && filter.filterFn) {
            filtered = filtered.filter(item => filter.filterFn(item, filterValue));
          }
        }
      });
    }
    
    // Apply sorting
    if (enableSorting && sortConfig.key) {
      const column = columns[sortConfig.key];
      if (column && column.sortKey) {
        filtered.sort((a, b) => {
          let aValue = a[column.sortKey];
          let bValue = b[column.sortKey];
          
          // Handle custom sort functions
          if (column.sortFn) {
            return column.sortFn(a, b, sortConfig.direction);
          }
          
          // Default sorting
          if (aValue < bValue) return sortConfig.direction === 'asc' ? -1 : 1;
          if (aValue > bValue) return sortConfig.direction === 'asc' ? 1 : -1;
          return 0;
        });
      }
    }
    
    return filtered;
  }, [data, searchQuery, activeFilters, sortConfig, searchFields, columns, enableSearch, enableFilters, enableSorting, filters]);
  
  // Fullscreen wrapper
  if (isFullscreen) {
    return (
      <div className="fixed inset-0 z-50 bg-white flex flex-col">
        {/* Fullscreen Header */}
        <div className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">{title || 'Table View'}</h2>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setIsFullscreen(false)}
              className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
              title="Exit fullscreen"
            >
              <Minimize2 className="h-5 w-5" />
            </button>
            <button
              onClick={() => setIsFullscreen(false)}
              className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
              title="Close"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Fullscreen Content */}
        <div className="flex-1 overflow-auto bg-gray-50 p-6">
          <div className="bg-white rounded-lg shadow-sm p-6">
            <TableContent />
          </div>
        </div>
      </div>
    );
  }

  // Normal view
  return (
    <div className={`space-y-4 ${className} relative`}>
      {/* Fullscreen Toggle Button */}
      {enableFullscreen && (
        <button
          onClick={() => setIsFullscreen(true)}
          className="absolute -top-10 right-0 p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
          title="Enter fullscreen"
        >
          <Maximize2 className="h-4 w-4" />
        </button>
      )}
      
      <TableContent />
    </div>
  );
  
  // Extract table content to avoid duplication
  function TableContent() {
    return (
      <>
        {/* Filter Controls */}
      {(enableSearch || enableFilters || enableColumnResetting) && (
        <div className="flex flex-col sm:flex-row gap-4">
          {/* Search */}
          {enableSearch && (
            <div className="flex-1 relative">
              <Search className="absolute left-2 top-1/2 transform -translate-y-1/2 h-3 w-3 text-gray-400" />
              <input
                type="text"
                placeholder={searchPlaceholder}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-8 pr-2 py-1.5 text-xs border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          )}
          
          {/* Filters and Controls */}
          <div className="flex items-center space-x-2">
            {enableFilters && filters.map(filter => (
              <div key={filter.key} className="flex items-center space-x-1">
                <Filter className="h-3 w-3 text-gray-400" />
                <select
                  value={activeFilters[filter.key] || 'all'}
                  onChange={(e) => setActiveFilters(prev => ({
                    ...prev,
                    [filter.key]: e.target.value
                  }))}
                  className="px-2 py-1.5 text-xs border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  <option value="all">{filter.allLabel || `All ${filter.label}`}</option>
                  {filter.options.map(option => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
            ))}
            
            {enableColumnResetting && (
              <button
                onClick={resetColumnOrder}
                className="flex items-center px-2 py-1.5 text-xs text-gray-600 hover:text-gray-800 border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
                title="Reset column order"
              >
                <RotateCcw className="h-3 w-3 mr-1" />
                Reset Columns
              </button>
            )}
          </div>
        </div>
      )}
      
      {/* Table */}
      <div className="overflow-x-auto border border-gray-200 rounded-lg">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              {columnOrder.map((columnKey) => {
                const column = columns[columnKey];
                if (!column) return null;
                
                return (
                  <th 
                    key={columnKey}
                    className={`relative px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wide transition-all duration-150 ${
                      enableColumnReordering && column.draggable !== false && columnKey !== 'product' ? 'cursor-move hover:bg-gray-100' : ''
                    } ${
                      draggedColumn?.key === columnKey ? 'opacity-30 bg-gray-100' : ''
                    } ${
                      dragOverColumn === columnKey && draggedColumn?.key !== columnKey 
                        ? 'bg-blue-50' 
                        : ''
                    }`}
                    draggable={enableColumnReordering && column.draggable !== false && columnKey !== 'product'}
                    onDragStart={(e) => handleDragStart(e, columnKey)}
                    onDragOver={handleDragOver}
                    onDragEnter={(e) => handleDragEnter(e, columnKey)}
                    onDragLeave={handleDragLeave}
                    onDrop={(e) => handleDrop(e, columnKey)}
                    onDragEnd={handleDragEnd}
                  >
                    <>
                      {/* Drop indicator - Left side */}
                      {dragOverColumn === columnKey && dropIndicatorPosition === 'left' && draggedColumn?.key !== columnKey && (
                        <div className="absolute left-0 top-0 bottom-0 w-1 bg-blue-500 z-10 shadow-lg" />
                      )}
                      
                      {/* Drop indicator - Right side */}
                      {dragOverColumn === columnKey && dropIndicatorPosition === 'right' && draggedColumn?.key !== columnKey && (
                        <div className="absolute right-0 top-0 bottom-0 w-1 bg-blue-500 z-10 shadow-lg" />
                      )}
                      
                      <div className="flex items-center space-x-1 relative z-0">
                        {enableColumnReordering && column.draggable !== false && columnKey !== 'product' && (
                          <GripVertical className={`h-3 w-3 transition-colors ${
                            draggedColumn?.key === columnKey ? 'text-gray-600' : 'text-gray-400'
                          }`} />
                        )}
                        {enableSorting && column.sortKey ? (
                          <button
                            onClick={() => handleSort(columnKey)}
                            className="flex items-center space-x-1 hover:text-gray-700 text-xs"
                          >
                            <span>{column.label}</span>
                            {getSortIcon(columnKey)}
                          </button>
                        ) : (
                          <span className="text-xs">{column.label}</span>
                        )}
                      </div>
                    </>
                  
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {processedData.length > 0 ? (
              processedData.map((row, index) => (
                <tr 
                  key={row.id || index} 
                  className={`hover:bg-gray-50 ${onRowClick ? 'cursor-pointer' : ''}`}
                  onClick={() => onRowClick && onRowClick(row)}
                >
                  {columnOrder.map((columnKey) => 
                    renderCell(columnKey, row, index)
                  )}
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={columnOrder.length} className="px-3 py-8 text-center">
                  <div className="flex flex-col items-center">
                    <EmptyIcon className="h-8 w-8 text-gray-400 mb-2" />
                    <h3 className="text-xs font-medium text-gray-900 mb-1">{emptyTitle}</h3>
                    <p className="text-xs text-gray-500">{emptyDescription}</p>
                  </div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      </>
    );
  }
};

export default StandardTable;