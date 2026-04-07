import { useState, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Card } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { toast } from 'sonner';
import {
  Upload, Database, CheckCircle2, XCircle, AlertCircle, TrendingUp,
  Calendar, FileText, ArrowLeft, Loader2, FileSpreadsheet, BarChart3,
  Download, Activity, AlertTriangle, RefreshCw, FileDown, Layers, Zap, Trash2
} from 'lucide-react';
import { formatDate, formatDateRange, formatDateTime } from '@/lib/dateUtils';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const SYMBOLS = [
  { value: 'XAUUSD', label: 'XAU/USD (Gold)', enabled: true },
  { value: 'EURUSD', label: 'EUR/USD', enabled: true },
  { value: 'GBPUSD', label: 'GBP/USD', enabled: true },
  { value: 'USDJPY', label: 'USD/JPY', enabled: true },
  { value: 'NAS100', label: 'NAS100 (US100)', enabled: true },
];

const TIMEFRAMES = [
  { value: '1m', label: '1 Minute (M1)' },
  { value: '5m', label: '5 Minutes (M5)' },
  { value: '15m', label: '15 Minutes (M15)' },
  { value: '30m', label: '30 Minutes (M30)' },
  { value: '1h', label: '1 Hour (H1)' },
  { value: '4h', label: '4 Hours (H4)' },
  { value: '1d', label: '1 Day (D1)' },
  { value: '1w', label: '1 Week (W1)' },
];

const CSV_FORMATS = [
  { value: 'mt4', label: 'MetaTrader 4 (MT4)' },
  { value: 'mt5', label: 'MetaTrader 5 (MT5)' },
  { value: 'ctrader', label: 'cTrader' },
  { value: 'custom', label: 'Dukascopy / Custom CSV' },
];

export default function MarketDataPage() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('download');
  
  // CSV Upload States
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [symbol, setSymbol] = useState('EURUSD');
  const [timeframe, setTimeframe] = useState('1h');
  const [csvFormat, setCsvFormat] = useState('custom');
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);
  
  // Dukascopy Download States
  const [selectedSymbols, setSelectedSymbols] = useState(['XAUUSD', 'EURUSD']);
  const [dukaTimeframe, setDukaTimeframe] = useState('H1');
  const [startDate, setStartDate] = useState('2024-01-08');
  const [endDate, setEndDate] = useState('2024-01-31');
  const [downloading, setDownloading] = useState(false);
  const [downloadTaskId, setDownloadTaskId] = useState(null);
  const [downloadProgress, setDownloadProgress] = useState(0);
  const [downloadMessage, setDownloadMessage] = useState('');
  const [downloadResults, setDownloadResults] = useState(null);
  
  // Coverage States
  const [coverage, setCoverage] = useState(null);
  const [loadingCoverage, setLoadingCoverage] = useState(false);
  
  // Data Integrity States
  const [dataIntegrity, setDataIntegrity] = useState(null);
  
  // Gap Fix States
  const [fixingGaps, setFixingGaps] = useState(false);
  const [gapFixTasks, setGapFixTasks] = useState({});
  const [gapFixProgress, setGapFixProgress] = useState(null);
  
  // Export States
  const [exportSymbol, setExportSymbol] = useState('EURUSD');
  const [exportTimeframe, setExportTimeframe] = useState('H1');
  const [exportStartDate, setExportStartDate] = useState('2024-01-01');
  const [exportEndDate, setExportEndDate] = useState('2024-01-31');
  const [exporting, setExporting] = useState(false);
  
  // Delete States
  const [deletingDataset, setDeletingDataset] = useState(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [pendingDelete, setPendingDelete] = useState(null);

  useEffect(() => {
    if (activeTab === 'coverage') {
      loadCoverage();
    }
  }, [activeTab]);

  // Poll download status
  useEffect(() => {
    if (downloadTaskId && downloading) {
      const interval = setInterval(async () => {
        try {
          const response = await axios.get(`${API}/dukascopy/status/${downloadTaskId}`);
          if (response.data.success) {
            const task = response.data.task;
            setDownloadProgress(task.progress);
            setDownloadMessage(task.message);
            
            if (task.status === 'completed') {
              setDownloading(false);
              setDownloadResults(task.results);
              toast.success('Download completed!');
              clearInterval(interval);
              // Reload coverage if on that tab
              if (activeTab === 'coverage') {
                loadCoverage();
              }
            } else if (task.status === 'failed') {
              setDownloading(false);
              toast.error(`Download failed: ${task.error}`);
              clearInterval(interval);
            }
          }
        } catch (error) {
          console.error('Failed to check status:', error);
        }
      }, 2000);
      
      return () => clearInterval(interval);
    }
  }, [downloadTaskId, downloading, activeTab]);

  // Poll gap fix status
  useEffect(() => {
    const taskIds = Object.keys(gapFixTasks);
    if (taskIds.length === 0) return;

    const interval = setInterval(async () => {
      let allCompleted = true;
      const updatedTasks = { ...gapFixTasks };

      for (const taskId of taskIds) {
        try {
          const response = await axios.get(`${API}/marketdata/fix-gaps/status/${taskId}`);
          updatedTasks[taskId] = response.data;
          
          if (response.data.status === 'running' || response.data.status === 'pending') {
            allCompleted = false;
          }
        } catch (error) {
          console.error('Failed to check gap fix status:', error);
        }
      }

      setGapFixTasks(updatedTasks);

      // Calculate overall progress
      let totalGaps = 0;
      let completedGaps = 0;
      let failedGaps = 0;
      let candlesFixed = 0;

      Object.values(updatedTasks).forEach(task => {
        totalGaps += task.progress?.total_gaps || 0;
        completedGaps += task.progress?.completed || 0;
        failedGaps += task.progress?.failed || 0;
        candlesFixed += task.candles_fixed || 0;
      });

      setGapFixProgress({
        totalGaps,
        completedGaps,
        failedGaps,
        remaining: totalGaps - completedGaps - failedGaps,
        candlesFixed,
        percent: totalGaps > 0 ? Math.round((completedGaps + failedGaps) / totalGaps * 100) : 0
      });

      if (allCompleted) {
        setFixingGaps(false);
        toast.success(`Gap fixing completed! ${candlesFixed} candles added.`);
        loadCoverage();
        clearInterval(interval);
      }
    }, 1500);

    return () => clearInterval(interval);
  }, [gapFixTasks]);

  const loadCoverage = async () => {
    setLoadingCoverage(true);
    try {
      const response = await axios.get(`${API}/marketdata/coverage`);
      if (response.data.success) {
        setCoverage(response.data);
        // Extract data integrity info
        if (response.data.data_integrity) {
          setDataIntegrity(response.data.data_integrity);
        }
      }
    } catch (error) {
      console.error('Failed to load coverage:', error);
      toast.error('Failed to load coverage data');
    } finally {
      setLoadingCoverage(false);
    }
  };

  const purgeSyntheticData = async () => {
    try {
      const response = await axios.delete(`${API}/data-integrity/purge-synthetic`);
      if (response.data.success) {
        toast.success(`Purged ${response.data.deleted} synthetic candles`);
        loadCoverage(); // Reload coverage
      }
    } catch (error) {
      toast.error('Failed to purge synthetic data');
    }
  };

  const toggleSymbol = (symbolValue) => {
    setSelectedSymbols(prev => 
      prev.includes(symbolValue)
        ? prev.filter(s => s !== symbolValue)
        : [...prev, symbolValue]
    );
  };

  const startDukascopyDownload = async () => {
    if (selectedSymbols.length === 0) {
      toast.error('Please select at least one symbol');
      return;
    }

    setDownloading(true);
    setDownloadProgress(0);
    setDownloadMessage('Starting download...');
    setDownloadResults(null);

    try {
      const response = await axios.post(`${API}/dukascopy/download`, {
        symbols: selectedSymbols,
        start_date: startDate,
        end_date: endDate,
        timeframe: dukaTimeframe
      });

      if (response.data.success) {
        setDownloadTaskId(response.data.task_id);
        toast.info('Download started in background');
      }
    } catch (error) {
      setDownloading(false);
      const errorMsg = error.response?.data?.detail || error.message;
      toast.error(`Failed to start download: ${errorMsg}`);
    }
  };

  const retryMissingData = async (symbol, timeframe, missingRanges) => {
    if (!missingRanges || missingRanges.length === 0) {
      toast.info('No missing data to download');
      return;
    }

    try {
      setFixingGaps(true);
      toast.info(`Starting gap fix for ${symbol} ${timeframe}...`);
      
      const response = await axios.post(
        `${API}/marketdata/fix-gaps?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}&fix_all=false`,
        { gaps: missingRanges }
      );

      if (response.data.success && response.data.task_id) {
        setGapFixTasks(prev => ({
          ...prev,
          [response.data.task_id]: { status: 'pending', symbol, timeframe }
        }));
        toast.success(`Started fixing ${response.data.total_gaps} gaps for ${symbol}`);
      }
    } catch (error) {
      setFixingGaps(false);
      const errorMsg = error.response?.data?.detail || error.message;
      toast.error(`Failed to start gap fix: ${errorMsg}`);
    }
  };

  const fixAllGapsForSymbol = async (symbol, timeframe) => {
    try {
      setFixingGaps(true);
      toast.info(`Starting to fix all gaps for ${symbol} ${timeframe}...`);
      
      const response = await axios.post(
        `${API}/marketdata/fix-gaps?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}&fix_all=true`
      );

      if (response.data.success && response.data.task_id) {
        setGapFixTasks(prev => ({
          ...prev,
          [response.data.task_id]: { status: 'pending', symbol, timeframe }
        }));
        toast.success(`Started fixing all ${response.data.total_gaps} gaps for ${symbol}`);
      } else if (response.data.message === 'No gaps to fix') {
        setFixingGaps(false);
        toast.info('No gaps to fix - data is complete');
      }
    } catch (error) {
      setFixingGaps(false);
      const errorMsg = error.response?.data?.detail || error.message;
      toast.error(`Failed to start gap fix: ${errorMsg}`);
    }
  };

  const fixAllGapsGlobal = async () => {
    try {
      setFixingGaps(true);
      toast.info('Starting to fix ALL gaps across all symbols...');
      
      const response = await axios.post(`${API}/marketdata/fix-all-gaps`);

      if (response.data.success && response.data.tasks) {
        const newTasks = {};
        response.data.tasks.forEach(task => {
          newTasks[task.task_id] = { status: 'pending', symbol: task.symbol, timeframe: task.timeframe };
        });
        setGapFixTasks(prev => ({ ...prev, ...newTasks }));
        toast.success(`Started fixing ${response.data.total_gaps} gaps across ${response.data.tasks.length} datasets`);
      } else {
        setFixingGaps(false);
        toast.info('No gaps to fix - all data is complete');
      }
    } catch (error) {
      setFixingGaps(false);
      const errorMsg = error.response?.data?.detail || error.message;
      toast.error(`Failed to start global gap fix: ${errorMsg}`);
    }
  };

  const formatTimeRemaining = (seconds) => {
    if (!seconds) return 'Calculating...';
    if (seconds < 60) return `${Math.round(seconds)}s`;
    if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
    return `${Math.round(seconds / 3600)}h ${Math.round((seconds % 3600) / 60)}m`;
  };

  const exportData = async () => {
    setExporting(true);
    try {
      const params = new URLSearchParams({
        symbol: exportSymbol,
        timeframe: exportTimeframe,
        start_date: exportStartDate,
        end_date: exportEndDate
      });

      const response = await axios.get(`${API}/marketdata/export?${params}`, {
        responseType: 'blob'
      });

      // Create download link
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `${exportSymbol}_${exportTimeframe}_${new Date().toISOString().split('T')[0]}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();

      toast.success('CSV exported successfully!');
    } catch (error) {
      const errorMsg = error.response?.data?.detail || error.message;
      toast.error(`Export failed: ${errorMsg}`);
    } finally {
      setExporting(false);
    }
  };

  // Delete dataset functions
  const confirmDeleteDataset = (symbol, timeframe) => {
    setPendingDelete({ symbol, timeframe });
    setShowDeleteConfirm(true);
  };

  const cancelDelete = () => {
    setShowDeleteConfirm(false);
    setPendingDelete(null);
  };

  const executeDelete = async () => {
    if (!pendingDelete) return;
    
    const { symbol, timeframe } = pendingDelete;
    setDeletingDataset(`${symbol}-${timeframe}`);
    setShowDeleteConfirm(false);
    
    try {
      const response = await axios.delete(`${API}/marketdata/${symbol}/${timeframe}`);
      
      if (response.data.success) {
        toast.success(`Deleted ${response.data.deleted_count} candles for ${symbol} ${timeframe}`);
        loadCoverage(); // Refresh coverage data
      }
    } catch (error) {
      const errorMsg = error.response?.data?.detail || error.message;
      toast.error(`Delete failed: ${errorMsg}`);
    } finally {
      setDeletingDataset(null);
      setPendingDelete(null);
    }
  };

  // CSV Upload functions
  const handleDrag = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    const files = e.dataTransfer.files;
    if (files && files[0]) {
      handleFileSelect(files[0]);
    }
  }, []);

  const handleFileSelect = (file) => {
    if (!file.name.endsWith('.csv')) {
      toast.error('Please select a CSV file');
      return;
    }
    setSelectedFile(file);
    setUploadResult(null);
  };

  const handleFileInput = (e) => {
    const files = e.target.files;
    if (files && files[0]) {
      handleFileSelect(files[0]);
    }
  };

  const uploadCSV = async () => {
    if (!selectedFile) {
      toast.error('Please select a CSV file');
      return;
    }

    setUploading(true);
    setUploadResult(null);

    try {
      const fileContent = await selectedFile.text();
      const requestData = {
        symbol: symbol,
        timeframe: timeframe,
        format_type: csvFormat,
        data: fileContent,
        skip_validation: false
      };

      toast.info('Uploading CSV data...');
      const response = await axios.post(`${API}/marketdata/import/csv`, requestData);

      if (response.data.success) {
        setUploadResult({
          success: true,
          symbol: response.data.symbol,
          timeframe: response.data.timeframe,
          imported: response.data.imported,
          skipped: response.data.skipped,
          total: response.data.total_processed
        });

        toast.success(`✅ Uploaded ${response.data.imported} candles`);
        setSelectedFile(null);
        
        // Reload coverage if on that tab
        if (activeTab === 'coverage') {
          loadCoverage();
        }
      }
    } catch (error) {
      const errorMsg = error.response?.data?.detail || error.message;
      toast.error(`Upload failed: ${errorMsg}`);
      setUploadResult({ success: false, error: errorMsg });
    } finally {
      setUploading(false);
    }
  };

  const getStatusColor = (status) => {
    switch(status) {
      case 'complete': return 'text-emerald-400 border-emerald-500/40';
      case 'partial': return 'text-yellow-400 border-yellow-500/40';
      case 'incomplete': return 'text-red-400 border-red-500/40';
      default: return 'text-zinc-400 border-zinc-500/40';
    }
  };

  const getStatusIcon = (status) => {
    switch(status) {
      case 'complete': return <CheckCircle2 className="w-4 h-4" />;
      case 'partial': return <AlertCircle className="w-4 h-4" />;
      case 'incomplete': return <XCircle className="w-4 h-4" />;
      default: return <Database className="w-4 h-4" />;
    }
  };

  return (
    <div className="min-h-screen bg-[#0A0A0B] text-white overflow-y-auto">
      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && pendingDelete && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#18181B] border border-red-500/30 rounded-xl p-6 max-w-md w-full shadow-2xl">
            <div className="flex items-start gap-4">
              <div className="p-3 bg-red-500/20 rounded-full">
                <AlertTriangle className="w-6 h-6 text-red-500" />
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-bold text-white mb-2">Delete Dataset?</h3>
                <p className="text-sm text-zinc-400 mb-4">
                  Are you sure you want to delete all market data for{' '}
                  <span className="font-mono text-white font-bold">{pendingDelete.symbol}</span>{' '}
                  <span className="font-mono text-blue-400">{pendingDelete.timeframe}</span>?
                </p>
                <p className="text-xs text-red-400 mb-4">
                  This action cannot be undone. All candle data will be permanently removed.
                </p>
                <div className="flex gap-3">
                  <Button
                    onClick={cancelDelete}
                    variant="outline"
                    className="flex-1 border-zinc-600"
                  >
                    Cancel
                  </Button>
                  <Button
                    onClick={executeDelete}
                    className="flex-1 bg-red-600 hover:bg-red-700 text-white"
                    data-testid="confirm-delete-btn"
                  >
                    <Trash2 className="w-4 h-4 mr-2" />
                    Delete
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
      {/* Header */}
      <div className="border-b border-white/10 bg-[#0F0F10]/50 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button
                onClick={() => navigate('/')}
                variant="ghost"
                size="sm"
                className="text-zinc-400 hover:text-white"
                data-testid="back-to-dashboard"
              >
                <ArrowLeft className="w-4 h-4 mr-2" />
                Back to Dashboard
              </Button>
              <div className="w-px h-6 bg-white/10" />
              <div className="flex items-center gap-3">
                <Database className="w-6 h-6 text-blue-400" />
                <div>
                  <h1 className="text-xl font-bold">Market Data Management</h1>
                  <p className="text-xs text-zinc-500">Complete data lifecycle management</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-8 overflow-y-auto">
        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
          <TabsList className="bg-[#0F0F10] border border-white/10 p-1 sticky top-0 z-10">
            <TabsTrigger value="download" className="data-[state=active]:bg-blue-600">
              <Download className="w-4 h-4 mr-2" />
              Download
            </TabsTrigger>
            <TabsTrigger value="upload" className="data-[state=active]:bg-blue-600">
              <Upload className="w-4 h-4 mr-2" />
              Upload
            </TabsTrigger>
            <TabsTrigger value="coverage" className="data-[state=active]:bg-blue-600">
              <Layers className="w-4 h-4 mr-2" />
              Coverage
            </TabsTrigger>
            <TabsTrigger value="export" className="data-[state=active]:bg-blue-600">
              <FileDown className="w-4 h-4 mr-2" />
              Export
            </TabsTrigger>
          </TabsList>

          {/* Download Tab */}
          <TabsContent value="download" className="space-y-6 overflow-y-auto">
            <Card className="bg-[#0F0F10] border-white/10 p-6">
              <h2 className="text-lg font-bold mb-6 flex items-center gap-2">
                <Download className="w-5 h-5 text-blue-400" />
                Dukascopy Data Download
              </h2>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="space-y-4">
                  <div>
                    <label className="text-xs text-zinc-400 uppercase tracking-wider mb-3 block">
                      Select Symbols
                    </label>
                    <div className="space-y-2">
                      {SYMBOLS.map(sym => (
                        <div key={sym.value} className="flex items-center gap-3 p-3 bg-[#18181B] rounded-md border border-white/5">
                          <Checkbox
                            checked={selectedSymbols.includes(sym.value)}
                            onCheckedChange={() => toggleSymbol(sym.value)}
                          />
                          <label className="text-sm flex-1">{sym.label}</label>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-xs text-zinc-400 uppercase tracking-wider mb-2 block">Start Date</label>
                      <input
                        type="date"
                        value={startDate}
                        onChange={(e) => setStartDate(e.target.value)}
                        className="w-full bg-[#18181B] border border-white/10 rounded-md px-3 py-2 text-sm"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-zinc-400 uppercase tracking-wider mb-2 block">End Date</label>
                      <input
                        type="date"
                        value={endDate}
                        onChange={(e) => setEndDate(e.target.value)}
                        className="w-full bg-[#18181B] border border-white/10 rounded-md px-3 py-2 text-sm"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="text-xs text-zinc-400 uppercase tracking-wider mb-2 block">Timeframe</label>
                    <Select value={dukaTimeframe} onValueChange={setDukaTimeframe}>
                      <SelectTrigger className="bg-[#18181B] border-white/10">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {TIMEFRAMES.map(tf => (
                          <SelectItem key={tf.value} value={tf.value}>{tf.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <Button
                    onClick={startDukascopyDownload}
                    disabled={downloading || selectedSymbols.length === 0}
                    className="w-full bg-blue-600 hover:bg-blue-700 h-12"
                    data-testid="download-button"
                  >
                    {downloading ? (
                      <>
                        <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                        Downloading... {downloadProgress.toFixed(0)}%
                      </>
                    ) : (
                      <>
                        <Download className="w-5 h-5 mr-2" />
                        Download & Prepare Data
                      </>
                    )}
                  </Button>

                  {downloading && (
                    <div className="bg-[#18181B] p-4 rounded-md border border-blue-500/30">
                      <p className="text-sm font-mono text-blue-400 mb-2">{downloadMessage}</p>
                      <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-blue-500 transition-all duration-300"
                          style={{ width: `${downloadProgress}%` }}
                        />
                      </div>
                    </div>
                  )}
                </div>

                <div>
                  {downloadResults ? (
                    <div className="space-y-3">
                      <h3 className="text-sm font-bold text-emerald-400 mb-3">Download Results</h3>
                      {Object.entries(downloadResults).map(([sym, result]) => (
                        <div key={sym} className="bg-[#18181B] p-4 rounded-md border border-white/10">
                          <div className="flex items-center justify-between mb-3">
                            <span className="font-mono font-bold">{sym}</span>
                            {result.error ? (
                              <Badge variant="outline" className="border-red-500/40 text-red-400">Failed</Badge>
                            ) : (
                              <Badge variant="outline" className="border-emerald-500/40 text-emerald-400">Success</Badge>
                            )}
                          </div>
                          
                          {!result.error && (
                            <div className="space-y-2 text-xs">
                              <div className="flex justify-between">
                                <span className="text-zinc-500">Coverage:</span>
                                <span className="text-white font-mono">{result.coverage_percent}%</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-zinc-500">Quality Score:</span>
                                <span className="text-blue-400 font-mono">{result.data_quality_score}/100</span>
                              </div>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="h-full flex items-center justify-center border-2 border-dashed border-white/10 rounded-lg p-8">
                      <div className="text-center">
                        <BarChart3 className="w-12 h-12 mx-auto text-zinc-600 mb-3" />
                        <p className="text-sm text-zinc-500">Results will appear here</p>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </Card>
          </TabsContent>

          {/* Upload Tab */}
          <TabsContent value="upload" className="overflow-y-auto">
            <Card className="bg-[#0F0F10] border-white/10 p-6">
              <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
                <Upload className="w-5 h-5 text-blue-400" />
                Upload CSV Data
              </h2>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="space-y-4">
                  <div>
                    <label className="text-xs text-zinc-400 uppercase tracking-wider mb-2 block">Symbol</label>
                    <Select value={symbol} onValueChange={setSymbol}>
                      <SelectTrigger className="bg-[#18181B] border-white/10">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {SYMBOLS.map(s => (
                          <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div>
                    <label className="text-xs text-zinc-400 uppercase tracking-wider mb-2 block">Timeframe</label>
                    <Select value={timeframe} onValueChange={setTimeframe}>
                      <SelectTrigger className="bg-[#18181B] border-white/10">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {TIMEFRAMES.map(tf => (
                          <SelectItem key={tf.value} value={tf.value}>{tf.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div>
                    <label className="text-xs text-zinc-400 uppercase tracking-wider mb-2 block">CSV Format</label>
                    <Select value={csvFormat} onValueChange={setCsvFormat}>
                      <SelectTrigger className="bg-[#18181B] border-white/10">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {CSV_FORMATS.map(fmt => (
                          <SelectItem key={fmt.value} value={fmt.value}>{fmt.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div
                    className={`border-2 border-dashed rounded-lg p-8 text-center transition-all ${
                      dragActive ? 'border-blue-500 bg-blue-500/10' : 'border-white/20 bg-[#18181B]'
                    }`}
                    onDragEnter={handleDrag}
                    onDragLeave={handleDrag}
                    onDragOver={handleDrag}
                    onDrop={handleDrop}
                  >
                    <input type="file" id="csv-file-input" accept=".csv" onChange={handleFileInput} className="hidden" />
                    
                    {selectedFile ? (
                      <div className="space-y-3">
                        <FileSpreadsheet className="w-12 h-12 mx-auto text-emerald-400" />
                        <div>
                          <p className="text-sm font-mono text-white">{selectedFile.name}</p>
                          <p className="text-xs text-zinc-500">{(selectedFile.size / 1024).toFixed(2)} KB</p>
                        </div>
                        <Button onClick={() => setSelectedFile(null)} variant="outline" size="sm">Remove</Button>
                      </div>
                    ) : (
                      <div className="space-y-3">
                        <Upload className="w-12 h-12 mx-auto text-zinc-500" />
                        <div>
                          <p className="text-sm text-zinc-300 mb-1">Drag & drop CSV file here</p>
                          <p className="text-xs text-zinc-500 mb-3">or</p>
                          <label htmlFor="csv-file-input" className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-md cursor-pointer">
                            <FileText className="w-4 h-4" />
                            Browse Files
                          </label>
                        </div>
                      </div>
                    )}
                  </div>

                  <Button onClick={uploadCSV} disabled={!selectedFile || uploading} className="w-full bg-blue-600 hover:bg-blue-700">
                    {uploading ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Uploading...
                      </>
                    ) : (
                      <>
                        <Upload className="w-4 h-4 mr-2" />
                        Upload CSV Data
                      </>
                    )}
                  </Button>

                  {uploadResult && (
                    <div className={`p-4 rounded-md border ${uploadResult.success ? 'bg-emerald-500/10 border-emerald-500/30' : 'bg-red-500/10 border-red-500/30'}`}>
                      <div className="flex items-start gap-3">
                        {uploadResult.success ? <CheckCircle2 className="w-5 h-5 text-emerald-400" /> : <XCircle className="w-5 h-5 text-red-400" />}
                        <div className="flex-1 text-sm">
                          {uploadResult.success ? (
                            <>
                              <p className="font-bold text-emerald-400 mb-2">Upload Successful!</p>
                              <div className="space-y-1 text-xs text-zinc-300">
                                <p>Symbol: <span className="font-mono text-white">{uploadResult.symbol}</span></p>
                                <p>Imported: <span className="font-mono text-emerald-400">{uploadResult.imported}</span></p>
                              </div>
                            </>
                          ) : (
                            <>
                              <p className="font-bold text-red-400 mb-1">Upload Failed</p>
                              <p className="text-xs text-zinc-300">{uploadResult.error}</p>
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                <Card className="bg-[#0F0F10] border-blue-500/30 p-6">
                  <div className="flex items-start gap-3">
                    <AlertCircle className="w-5 h-5 text-blue-400 mt-0.5" />
                    <div className="text-sm space-y-2">
                      <p className="font-bold text-blue-400">CSV Upload Guidelines</p>
                      <p className="text-zinc-400 text-xs">Upload historical OHLCV data in CSV format.</p>
                      <div className="pt-2 space-y-1 text-xs text-zinc-500">
                        <p>• Must contain: timestamp, open, high, low, close, volume</p>
                        <p>• Supported: MT4, MT5, cTrader, Dukascopy, Custom</p>
                        <p>• Data will be validated before storage</p>
                      </div>
                    </div>
                  </div>
                </Card>
              </div>
            </Card>
          </TabsContent>

          {/* Coverage Tab */}
          <TabsContent value="coverage" className="overflow-y-auto">
            <div className="space-y-4">
              <div className="flex items-center justify-between flex-wrap gap-3">
                <h2 className="text-lg font-bold flex items-center gap-2">
                  <Layers className="w-5 h-5 text-blue-400" />
                  Data Coverage Overview
                </h2>
                <div className="flex items-center gap-2">
                  {/* Fix All Gaps Global Button */}
                  {coverage?.symbols?.some(s => s.timeframes?.some(tf => tf.gap_count > 0)) && (
                    <Button 
                      onClick={fixAllGapsGlobal} 
                      disabled={fixingGaps}
                      className="bg-yellow-600 hover:bg-yellow-700 text-black font-bold"
                      data-testid="fix-all-gaps-global"
                    >
                      {fixingGaps ? (
                        <>
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          Fixing Gaps...
                        </>
                      ) : (
                        <>
                          <Zap className="w-4 h-4 mr-2" />
                          Fix All Gaps
                        </>
                      )}
                    </Button>
                  )}
                  <Button onClick={loadCoverage} disabled={loadingCoverage} variant="outline" size="sm">
                    {loadingCoverage ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                    <span className="ml-2">Refresh</span>
                  </Button>
                </div>
              </div>

              {/* DATA INTEGRITY WARNING BANNER */}
              {dataIntegrity && !dataIntegrity.integrity_ok && (
                <Card className="bg-red-950/30 border-red-500/50 p-4">
                  <div className="flex items-start gap-3">
                    <AlertTriangle className="w-6 h-6 text-red-500 flex-shrink-0 mt-0.5" />
                    <div className="flex-1">
                      <h3 className="text-sm font-bold text-red-400 mb-1">
                        SYNTHETIC DATA DETECTED - BACKTESTING BLOCKED
                      </h3>
                      <p className="text-xs text-red-300/80 mb-3">
                        {dataIntegrity.synthetic_count?.toLocaleString()} synthetic candles found. 
                        Strategy generation and backtesting are disabled until synthetic data is removed.
                        Results would be unreliable.
                      </p>
                      <Button
                        onClick={purgeSyntheticData}
                        size="sm"
                        className="bg-red-600 hover:bg-red-700 text-white"
                        data-testid="purge-synthetic-btn"
                      >
                        <XCircle className="w-4 h-4 mr-2" />
                        Purge {dataIntegrity.synthetic_count?.toLocaleString()} Synthetic Candles
                      </Button>
                    </div>
                  </div>
                </Card>
              )}

              {/* DATA INTEGRITY OK BANNER */}
              {dataIntegrity && dataIntegrity.integrity_ok && (
                <Card className="bg-emerald-950/20 border-emerald-500/30 p-3">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                    <span className="text-sm text-emerald-400">
                      Data Integrity OK - {dataIntegrity.real_count?.toLocaleString()} verified candles from Dukascopy/CSV
                    </span>
                  </div>
                </Card>
              )}

              {/* Gap Fix Progress Panel */}
              {fixingGaps && gapFixProgress && (
                <Card className="bg-[#0F0F10] border-yellow-500/30 p-4">
                  <div className="flex items-center gap-3 mb-3">
                    <Loader2 className="w-5 h-5 animate-spin text-yellow-400" />
                    <h3 className="text-sm font-bold text-yellow-400">Fixing Gaps in Progress</h3>
                  </div>
                  
                  {/* Progress Bar */}
                  <div className="mb-3">
                    <div className="flex justify-between text-xs text-zinc-400 mb-1">
                      <span>Progress</span>
                      <span className="font-mono">{gapFixProgress.percent}%</span>
                    </div>
                    <div className="h-3 bg-zinc-800 rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-gradient-to-r from-yellow-500 to-emerald-500 transition-all duration-300"
                        style={{ width: `${gapFixProgress.percent}%` }}
                      />
                    </div>
                  </div>

                  {/* Stats Grid */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-center">
                    <div className="bg-zinc-800/50 rounded p-2">
                      <p className="text-xs text-zinc-500">Total Gaps</p>
                      <p className="text-lg font-bold font-mono text-white">{gapFixProgress.totalGaps}</p>
                    </div>
                    <div className="bg-zinc-800/50 rounded p-2">
                      <p className="text-xs text-zinc-500">Completed</p>
                      <p className="text-lg font-bold font-mono text-emerald-400">{gapFixProgress.completedGaps}</p>
                    </div>
                    <div className="bg-zinc-800/50 rounded p-2">
                      <p className="text-xs text-zinc-500">Remaining</p>
                      <p className="text-lg font-bold font-mono text-yellow-400">{gapFixProgress.remaining}</p>
                    </div>
                    <div className="bg-zinc-800/50 rounded p-2">
                      <p className="text-xs text-zinc-500">Candles Added</p>
                      <p className="text-lg font-bold font-mono text-blue-400">{gapFixProgress.candlesFixed?.toLocaleString()}</p>
                    </div>
                  </div>

                  {/* Active Tasks */}
                  {Object.entries(gapFixTasks).length > 0 && (
                    <div className="mt-3 space-y-2">
                      <p className="text-xs text-zinc-500">Active Tasks:</p>
                      <div className="max-h-32 overflow-y-auto space-y-1">
                        {Object.entries(gapFixTasks).map(([taskId, task]) => (
                          <div key={taskId} className="flex items-center justify-between text-xs bg-zinc-800/30 px-2 py-1 rounded">
                            <span className="font-mono text-zinc-300">
                              {task.symbol} {task.timeframe}
                            </span>
                            <Badge variant="outline" className={
                              task.status === 'completed' ? 'border-emerald-500 text-emerald-400' :
                              task.status === 'running' ? 'border-blue-500 text-blue-400' :
                              'border-zinc-500 text-zinc-400'
                            }>
                              {task.status === 'running' ? (
                                <><Loader2 className="w-3 h-3 mr-1 animate-spin" />{task.progress?.percent || 0}%</>
                              ) : task.status}
                            </Badge>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </Card>
              )}

              {loadingCoverage ? (
                <Card className="bg-[#0F0F10] border-white/10 p-12">
                  <div className="text-center">
                    <Loader2 className="w-8 h-8 animate-spin mx-auto text-blue-400 mb-3" />
                    <p className="text-sm text-zinc-500">Analyzing data coverage...</p>
                  </div>
                </Card>
              ) : coverage && coverage.symbols && coverage.symbols.length > 0 ? (
                <div className="grid grid-cols-1 gap-4">
                  {coverage.symbols.map((symbolData, idx) => (
                    <Card key={idx} className="bg-[#0F0F10] border-white/10 p-6">
                      <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center gap-3">
                          <TrendingUp className="w-5 h-5 text-emerald-400" />
                          <h3 className="text-lg font-bold font-mono">{symbolData.symbol}</h3>
                          <Badge variant="outline" className="text-xs">
                            {symbolData.timeframes?.length || 0} Timeframes
                          </Badge>
                        </div>
                        {/* Fix All Gaps for this Symbol */}
                        {symbolData.timeframes?.some(tf => tf.gap_count > 0) && (
                          <Button
                            onClick={() => {
                              symbolData.timeframes?.forEach(tf => {
                                if (tf.gap_count > 0) {
                                  fixAllGapsForSymbol(symbolData.symbol, tf.timeframe);
                                }
                              });
                            }}
                            disabled={fixingGaps}
                            size="sm"
                            className="bg-yellow-600/80 hover:bg-yellow-600 text-black text-xs"
                            data-testid={`fix-all-${symbolData.symbol}`}
                          >
                            <Zap className="w-3 h-3 mr-1" />
                            Fix All ({symbolData.timeframes?.reduce((sum, tf) => sum + (tf.gap_count || 0), 0)} gaps)
                          </Button>
                        )}
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {symbolData.timeframes?.map((tf, tfIdx) => (
                          <div key={tfIdx} className="bg-[#18181B] border border-white/10 rounded-lg p-4">
                            <div className="flex items-center justify-between mb-3">
                              <span className="font-mono font-bold text-white">{tf.timeframe}</span>
                              <Badge variant="outline" className={getStatusColor(tf.status)}>
                                {getStatusIcon(tf.status)}
                                <span className="ml-1 capitalize">{tf.status}</span>
                              </Badge>
                            </div>

                            {/* Coverage Bar */}
                            <div className="mb-3">
                              <div className="flex justify-between text-xs text-zinc-500 mb-1">
                                <span>Coverage</span>
                                <span className={`font-mono ${tf.coverage_percent < 95 ? 'text-yellow-400' : 'text-emerald-400'}`}>
                                  {tf.coverage_percent}%
                                </span>
                              </div>
                              <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
                                <div
                                  className={`h-full transition-all ${
                                    tf.coverage_percent >= 99 ? 'bg-emerald-500' :
                                    tf.coverage_percent >= 90 ? 'bg-yellow-500' : 'bg-red-500'
                                  }`}
                                  style={{ width: `${Math.min(tf.coverage_percent, 100)}%` }}
                                />
                              </div>
                            </div>

                            {/* Stats */}
                            <div className="space-y-2 text-xs mb-3">
                              <div className="flex justify-between">
                                <span className="text-zinc-500">Actual Candles:</span>
                                <span className="text-white font-mono">{tf.total_candles?.toLocaleString()}</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-zinc-500">Expected:</span>
                                <span className="text-zinc-400 font-mono">{tf.expected_candles?.toLocaleString() || '-'}</span>
                              </div>
                              {tf.gap_count > 0 && (
                                <div className="flex justify-between">
                                  <span className="text-yellow-500">Gaps Found:</span>
                                  <span className="text-yellow-400 font-mono font-bold">{tf.gap_count}</span>
                                </div>
                              )}
                            </div>

                            {/* Date Range */}
                            {tf.first_date && tf.last_date && (
                              <div className="mb-3 p-2 bg-zinc-800/50 rounded">
                                <p className="text-[10px] text-zinc-500 mb-1">Date Range:</p>
                                <p className="text-xs font-mono text-zinc-300">
                                  {formatDateRange(tf.first_date, tf.last_date)}
                                </p>
                              </div>
                            )}

                            {/* Missing Ranges - Always show if gaps exist */}
                            {tf.missing_ranges && tf.missing_ranges.length > 0 && (
                              <div className="mb-3 border border-yellow-500/30 rounded-lg p-3 bg-yellow-500/5">
                                <p className="text-xs text-yellow-500 mb-2 flex items-center gap-1 font-bold">
                                  <AlertTriangle className="w-3 h-3" />
                                  {tf.missing_ranges.length} Gap{tf.missing_ranges.length > 1 ? 's' : ''} Detected
                                </p>
                                <div className="space-y-1 mb-3 max-h-24 overflow-y-auto">
                                  {tf.missing_ranges.slice(0, 5).map((gap, i) => (
                                    <div key={i} className="text-[10px] bg-zinc-900/50 px-2 py-1 rounded font-mono text-yellow-400/80">
                                      <span>{formatDateRange(gap.start, gap.end)}</span>
                                      {gap.gap_hours && (
                                        <span className="ml-2 text-zinc-500">({gap.gap_hours}h / {gap.missing_candles} candles)</span>
                                      )}
                                    </div>
                                  ))}
                                  {tf.missing_ranges.length > 5 && (
                                    <p className="text-[10px] text-zinc-500">+{tf.missing_ranges.length - 5} more gaps...</p>
                                  )}
                                </div>
                                <Button
                                  onClick={() => retryMissingData(symbolData.symbol, tf.timeframe, tf.missing_ranges)}
                                  size="sm"
                                  variant="outline"
                                  className="w-full text-xs border-yellow-500/40 text-yellow-400 hover:bg-yellow-500/10"
                                  data-testid={`retry-missing-${symbolData.symbol}-${tf.timeframe}`}
                                >
                                  <RefreshCw className="w-3 h-3 mr-1" />
                                  Retry Missing Data ({tf.missing_ranges.length} gaps)
                                </Button>
                              </div>
                            )}

                            {/* Show complete status if no gaps */}
                            {(!tf.missing_ranges || tf.missing_ranges.length === 0) && tf.coverage_percent >= 99 && (
                              <div className="p-2 bg-emerald-500/10 border border-emerald-500/30 rounded text-center">
                                <p className="text-xs text-emerald-400 flex items-center justify-center gap-1">
                                  <CheckCircle2 className="w-3 h-3" />
                                  No gaps detected - Data complete
                                </p>
                              </div>
                            )}

                            {/* Delete Dataset Button */}
                            <Button
                              onClick={() => confirmDeleteDataset(symbolData.symbol, tf.timeframe)}
                              disabled={deletingDataset === `${symbolData.symbol}-${tf.timeframe}`}
                              size="sm"
                              variant="outline"
                              className="w-full mt-3 text-xs border-red-500/30 text-red-400 hover:bg-red-500/10 hover:border-red-500/50"
                              data-testid={`delete-dataset-${symbolData.symbol}-${tf.timeframe}`}
                            >
                              {deletingDataset === `${symbolData.symbol}-${tf.timeframe}` ? (
                                <>
                                  <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                                  Deleting...
                                </>
                              ) : (
                                <>
                                  <Trash2 className="w-3 h-3 mr-1" />
                                  Delete Dataset
                                </>
                              )}
                            </Button>
                          </div>
                        ))}
                      </div>
                    </Card>
                  ))}
                </div>
              ) : (
                <Card className="bg-[#0F0F10] border-white/10 p-12">
                  <div className="text-center">
                    <Database className="w-12 h-12 mx-auto text-zinc-600 mb-3" />
                    <p className="text-sm text-zinc-500 mb-1">No market data found</p>
                    <p className="text-xs text-zinc-600">Download or upload data to see coverage</p>
                  </div>
                </Card>
              )}
            </div>
          </TabsContent>

          {/* Export Tab */}
          <TabsContent value="export" className="overflow-y-auto">
            <Card className="bg-[#0F0F10] border-white/10 p-6">
              <h2 className="text-lg font-bold mb-6 flex items-center gap-2">
                <FileDown className="w-5 h-5 text-blue-400" />
                Export Market Data
              </h2>

              <div className="max-w-xl mx-auto space-y-4">
                <div>
                  <label className="text-xs text-zinc-400 uppercase tracking-wider mb-2 block">Symbol</label>
                  <Select value={exportSymbol} onValueChange={setExportSymbol}>
                    <SelectTrigger className="bg-[#18181B] border-white/10">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {SYMBOLS.map(s => (
                        <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <label className="text-xs text-zinc-400 uppercase tracking-wider mb-2 block">Timeframe</label>
                  <Select value={exportTimeframe} onValueChange={setExportTimeframe}>
                    <SelectTrigger className="bg-[#18181B] border-white/10">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {TIMEFRAMES.map(tf => (
                        <SelectItem key={tf.value} value={tf.value}>{tf.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-zinc-400 uppercase tracking-wider mb-2 block">Start Date</label>
                    <input
                      type="date"
                      value={exportStartDate}
                      onChange={(e) => setExportStartDate(e.target.value)}
                      className="w-full bg-[#18181B] border border-white/10 rounded-md px-3 py-2 text-sm"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-zinc-400 uppercase tracking-wider mb-2 block">End Date</label>
                    <input
                      type="date"
                      value={exportEndDate}
                      onChange={(e) => setExportEndDate(e.target.value)}
                      className="w-full bg-[#18181B] border border-white/10 rounded-md px-3 py-2 text-sm"
                    />
                  </div>
                </div>

                <Button
                  onClick={exportData}
                  disabled={exporting}
                  className="w-full bg-blue-600 hover:bg-blue-700 h-12"
                >
                  {exporting ? (
                    <>
                      <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                      Exporting...
                    </>
                  ) : (
                    <>
                      <FileDown className="w-5 h-5 mr-2" />
                      Download CSV
                    </>
                  )}
                </Button>

                <Card className="bg-[#18181B] border-blue-500/30 p-4">
                  <div className="flex items-start gap-3">
                    <AlertCircle className="w-5 h-5 text-blue-400 mt-0.5" />
                    <div className="text-xs space-y-1 text-zinc-400">
                      <p className="font-bold text-blue-400">Export Info</p>
                      <p>• Downloads data in standard CSV format</p>
                      <p>• Includes: Timestamp, Open, High, Low, Close, Volume</p>
                      <p>• Can be imported into any trading platform</p>
                    </div>
                  </div>
                </Card>
              </div>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
