/**
 * Date Formatting Utilities
 * Provides consistent date formatting across the application
 */

import dayjs from 'dayjs';

/**
 * Format a date string to DD-MMM-YYYY format
 * @param {string|Date} date - ISO date string or Date object
 * @param {boolean} includeTime - Whether to include time (HH:mm)
 * @returns {string} Formatted date string (e.g., "01-JAN-2026" or "01-JAN-2026 14:30")
 */
export const formatDate = (date, includeTime = false) => {
  if (!date) return 'N/A';
  
  try {
    const d = dayjs(date);
    if (!d.isValid()) return 'Invalid Date';
    
    if (includeTime) {
      return d.format('DD-MMM-YYYY HH:mm').toUpperCase();
    }
    return d.format('DD-MMM-YYYY').toUpperCase();
  } catch (error) {
    console.error('Date formatting error:', error);
    return 'Invalid Date';
  }
};

/**
 * Format a date range (start → end)
 * @param {string|Date} start - Start date
 * @param {string|Date} end - End date
 * @param {boolean} includeTime - Whether to include time
 * @returns {string} Formatted date range
 */
export const formatDateRange = (start, end, includeTime = false) => {
  const startFormatted = formatDate(start, includeTime);
  const endFormatted = formatDate(end, includeTime);
  return `${startFormatted} → ${endFormatted}`;
};

/**
 * Format a date for display in logs with full timestamp
 * @param {string|Date} date - ISO date string or Date object
 * @returns {string} Formatted datetime string (e.g., "01-JAN-2026 14:30:45")
 */
export const formatDateTime = (date) => {
  if (!date) return 'N/A';
  
  try {
    const d = dayjs(date);
    if (!d.isValid()) return 'Invalid Date';
    
    return d.format('DD-MMM-YYYY HH:mm:ss').toUpperCase();
  } catch (error) {
    console.error('DateTime formatting error:', error);
    return 'Invalid Date';
  }
};

/**
 * Format a date range showing duration
 * @param {string|Date} start - Start date
 * @param {string|Date} end - End date
 * @returns {object} Object with formatted range and duration
 */
export const formatDateRangeWithDuration = (start, end) => {
  const startFormatted = formatDate(start);
  const endFormatted = formatDate(end);
  
  const startDay = dayjs(start);
  const endDay = dayjs(end);
  const days = endDay.diff(startDay, 'day');
  
  return {
    range: `${startFormatted} → ${endFormatted}`,
    duration: days > 0 ? `${days} days` : 'Same day'
  };
};

/**
 * Get relative time description
 * @param {string|Date} date - ISO date string or Date object
 * @returns {string} Relative time description (e.g., "2 days ago")
 */
export const getRelativeTime = (date) => {
  if (!date) return 'N/A';
  
  try {
    const d = dayjs(date);
    const now = dayjs();
    const diffDays = now.diff(d, 'day');
    
    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return `${diffDays} days ago`;
    if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
    if (diffDays < 365) return `${Math.floor(diffDays / 30)} months ago`;
    return `${Math.floor(diffDays / 365)} years ago`;
  } catch (error) {
    return 'Unknown';
  }
};

export default {
  formatDate,
  formatDateRange,
  formatDateTime,
  formatDateRangeWithDuration,
  getRelativeTime
};
