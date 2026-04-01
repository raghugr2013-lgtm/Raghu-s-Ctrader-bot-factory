import dayjs from 'dayjs';

/**
 * Date formatting utilities for consistent date display across the app
 */

/**
 * Format date to DD-MMM-YYYY format
 * @param {string|Date} date - ISO date string or Date object
 * @returns {string} Formatted date (e.g., "01-JAN-2026")
 */
export const formatDate = (date) => {
  if (!date) return 'N/A';
  return dayjs(date).format('DD-MMM-YYYY');
};

/**
 * Format date with time to DD-MMM-YYYY HH:mm format
 * @param {string|Date} date - ISO date string or Date object
 * @returns {string} Formatted date with time (e.g., "01-JAN-2026 14:30")
 */
export const formatDateTime = (date) => {
  if (!date) return 'N/A';
  return dayjs(date).format('DD-MMM-YYYY HH:mm');
};

/**
 * Format date range to "DD-MMM-YYYY → DD-MMM-YYYY" format
 * @param {string|Date} startDate - Start date
 * @param {string|Date} endDate - End date
 * @returns {string} Formatted date range (e.g., "01-JAN-2024 → 31-DEC-2024")
 */
export const formatDateRange = (startDate, endDate) => {
  if (!startDate || !endDate) return 'N/A';
  return `${formatDate(startDate)} → ${formatDate(endDate)}`;
};

/**
 * Format date for debugging with time
 * @param {string|Date} date - ISO date string or Date object
 * @returns {string} Formatted date for debugging (e.g., "01-JAN-2026 14:30:45")
 */
export const formatDebugDate = (date) => {
  if (!date) return 'N/A';
  return dayjs(date).format('DD-MMM-YYYY HH:mm:ss');
};
