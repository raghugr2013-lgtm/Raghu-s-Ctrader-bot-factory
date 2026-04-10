import { useState, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Card } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Progress } from '@/components/ui/progress';
import { toast } from 'sonner';
import {
  Upload, Database, CheckCircle2, XCircle, AlertCircle,
  FileText, ArrowLeft, Loader2, FileSpreadsheet,
  Download, AlertTriangle, RefreshCw, Layers, Zap, Trash2,
  ShieldCheck, ShieldAlert, ShieldX, Binary, Info, Archive,
  FileDown, Calendar
} from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API_V2 = `${BACKEND_URL}/api/v2/data`;

const SYMBOLS = [
  { value: 'XAUUSD', label: 'XAU/USD (Gold)' },
  { value: 'EURUSD', label: 'EUR/USD' },
  { value: 'GBPUSD', label: 'GBP/USD' },
  { value: 'USDJPY', label: 'USD/JPY' },
  { value: 'NAS100', label: 'NAS100 (US100)' },
];

const TIMEFRAMES = [
  { value: 'M1', label: 'M1 (1 minute)' },
  { value: 'M5', label: 'M5 (5 minutes)' },
  { value: 'M15', label: 'M15 (15 minutes)' },
  { value: 'M30', label: 'M30 (30 minutes)' },
  { value: 'H1', label: 'H1 (1 hour)' },
  { value: 'H4', label: 'H4 (4 hours)' },
  { value: 'D1', label: 'D1 (Daily)' },
];

const CONFIDENCE_COLORS = {
  high: { bg: 'bg-emerald-500/20', border: 'border-emerald-500/40', text: 'text-emerald-400', icon: ShieldCheck },
  medium: { bg: 'bg-yellow-500/20', border: 'border-yellow-500/40', text: 'text-yellow-400', icon: ShieldAlert },
  low: { bg: 'bg-red-500/20', border: 'border-red-500/40', text: 'text-red-400', icon: ShieldX }
};

export default function MarketDataPage() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('upload');
  
  // Upload States
  const [uploadType, setUploadType] = useState('csv'); // 'csv', 'bi5', 'bi5-zip'
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [symbol, setSymbol] = useState('EURUSD');
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadResult, setUploadResult] = useState(null);
  
  // BI5 specific state
  const [bi5Hour, setBi5Hour] = useState('');
  
  // Coverage States
  const [coverage, setCoverage] = useState(null);
  const [loadingCoverage, setLoadingCoverage] = useState(false);
  const [selectedCoverageSymbol, setSelectedCoverageSymbol] = useState('EURUSD');
  
  // Gap States
  const [gaps, setGaps] = useState([]);
  const [loadingGaps, setLoadingGaps] = useState(false);
  const [fixingGaps, setFixingGaps] = useState(false);
  
  // Export States
  const [exportSymbol, setExportSymbol] = useState('EURUSD');
  const [exportTimeframe, setExportTimeframe] = useState('M1');
  const [exportStartDate, setExportStartDate] = useState('');
  const [exportEndDate, setExportEndDate] = useState('');
  const [exporting, setExporting] = useState(false);
  
  // Delete States
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [pendingDeleteSymbol, setPendingDeleteSymbol] = useState(null);
  const [deletingSymbol, setDeletingSymbol] = useState(null);

  useEffect(() => {
    if (activeTab === 'coverage') {
      loadCoverage();
    }
  }, [activeTab, selectedCoverageSymbol]);

  // Load coverage
  const loadCoverage = async () => {
    setLoadingCoverage(true);
    try {
      const response = await axios.get(`${API_V2}/coverage/${selectedCoverageSymbol}`);
      setCoverage(response.data);
      await loadGaps();
    } catch (error) {
      if (error.response?.status === 404) {
        setCoverage({ symbol: selectedCoverageSymbol, total_m1_candles: 0 });
      } else {
        console.error('Failed to load coverage:', error);
        toast.error('Failed to load coverage data');
      }
    } finally {
      setLoadingCoverage(false);
    }
  };

  // Load gaps
  const loadGaps = async () => {
    setLoadingGaps(true);
    try {
      const response = await axios.get(`${API_V2}/gaps/${selectedCoverageSymbol}/detect`);
      setGaps(response.data.gaps || []);
    } catch (error) {
      console.error('Failed to load gaps:', error);
      setGaps([]);
    } finally {
      setLoadingGaps(false);
    }
  };

  // Fix gaps
  const fixGaps = async () => {
    setFixingGaps(true);
    try {
      const response = await axios.post(`${API_V2}/gaps/${selectedCoverageSymbol}/fix`);
      if (response.data.success) {
        toast.success(response.data.message);
        await loadCoverage();
      } else {
        toast.warning(response.data.message || 'No gaps to fix');
      }
    } catch (error) {
      toast.error(`Gap fix failed: ${error.response?.data?.detail || error.message}`);
    } finally {
      setFixingGaps(false);
    }
  };

  // Purge low confidence
  const purgeLowConfidence = async () => {
    try {
      const response = await axios.delete(`${API_V2}/purge/${selectedCoverageSymbol}/low-confidence`);
      if (response.data.success) {
        toast.success(`Purged ${response.data.deleted_count} low confidence candles`);
        loadCoverage();
      }
    } catch (error) {
      toast.error('Failed to purge low confidence data');
    }
  };

  // File handling
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
  }, [uploadType]);

  const handleFileSelect = (file) => {
    let expectedExt;
    if (uploadType === 'bi5') expectedExt = '.bi5';
    else if (uploadType === 'bi5-zip') expectedExt = '.zip';
    else expectedExt = '.csv';
    
    if (!file.name.toLowerCase().endsWith(expectedExt)) {
      toast.error(`Please select a ${expectedExt.toUpperCase()} file`);
      return;
    }
    setSelectedFile(file);
    setUploadResult(null);
    setUploadProgress(0);
  };

  const handleFileInput = (e) => {
    const files = e.target.files;
    if (files && files[0]) {
      handleFileSelect(files[0]);
    }
  };

  // CSV Upload
  const uploadCSV = async () => {
    if (!selectedFile) {
      toast.error('Please select a file');
      return;
    }

    setUploading(true);
    setUploadResult(null);
    setUploadProgress(10);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('symbol', symbol);

      toast.info('Uploading CSV data (M1 only accepted)...');
      setUploadProgress(30);
      
      const response = await axios.post(`${API_V2}/upload/csv`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (progressEvent) => {
          const percent = Math.round((progressEvent.loaded * 50) / progressEvent.total) + 30;
          setUploadProgress(Math.min(percent, 80));
        }
      });

      setUploadProgress(100);

      if (response.data.success) {
        setUploadResult({ success: true, ...response.data });
        toast.success(`✅ Uploaded ${response.data.candles_stored} M1 candles`);
        setSelectedFile(null);
      } else {
        setUploadResult({
          success: false,
          detected_timeframe: response.data.detected_timeframe,
          errors: response.data.errors,
          message: response.data.message
        });
        toast.error(response.data.message || 'Upload rejected');
      }
    } catch (error) {
      const errorMsg = error.response?.data?.detail || error.response?.data?.errors?.[0] || error.message;
      toast.error(`Upload failed: ${errorMsg}`);
      setUploadResult({ 
        success: false, 
        error: errorMsg,
        detected_timeframe: error.response?.data?.detected_timeframe
      });
    } finally {
      setUploading(false);
    }
  };

  // BI5 Single Upload
  const uploadBI5 = async () => {
    if (!selectedFile) {
      toast.error('Please select a BI5 file');
      return;
    }
    if (!bi5Hour) {
      toast.error('Please specify the hour timestamp');
      return;
    }

    setUploading(true);
    setUploadResult(null);
    setUploadProgress(10);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('symbol', symbol);
      formData.append('hour', bi5Hour);

      toast.info('Processing BI5 tick data...');
      setUploadProgress(50);
      
      const response = await axios.post(`${API_V2}/upload/bi5`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      setUploadProgress(100);

      if (response.data.success) {
        setUploadResult({ success: true, ...response.data });
        toast.success(`✅ Converted ${response.data.candles_stored} M1 candles`);
        setSelectedFile(null);
        setBi5Hour('');
      } else {
        setUploadResult({ success: false, ...response.data });
        toast.error(response.data.message || 'Processing failed');
      }
    } catch (error) {
      const errorMsg = error.response?.data?.detail || error.message;
      toast.error(`BI5 upload failed: ${errorMsg}`);
      setUploadResult({ success: false, error: errorMsg });
    } finally {
      setUploading(false);
    }
  };

  // BI5 ZIP Bulk Upload
  const uploadBI5Zip = async () => {
    if (!selectedFile) {
      toast.error('Please select a ZIP file');
      return;
    }

    setUploading(true);
    setUploadResult(null);
    setUploadProgress(5);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('symbol', symbol);

      toast.info('Processing BI5 ZIP file (bulk upload)...');
      
      const response = await axios.post(`${API_V2}/upload/bi5-zip`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (progressEvent) => {
          const percent = Math.round((progressEvent.loaded * 30) / progressEvent.total) + 5;
          setUploadProgress(Math.min(percent, 35));
        }
      });

      setUploadProgress(100);

      const data = response.data;
      setUploadResult({
        success: data.success,
        isBulk: true,
        ...data
      });

      if (data.success) {
        toast.success(`✅ ${data.message}`);
        setSelectedFile(null);
      } else {
        toast.error(data.message || 'Bulk upload failed');
      }
    } catch (error) {
      const errorMsg = error.response?.data?.detail || error.message;
      toast.error(`ZIP upload failed: ${errorMsg}`);
      setUploadResult({ success: false, error: errorMsg });
    } finally {
      setUploading(false);
    }
  };

  // Export data
  const exportData = async () => {
    if (!exportStartDate || !exportEndDate) {
      toast.error('Please select date range');
      return;
    }

    setExporting(true);
    try {
      const endpoint = exportTimeframe === 'M1' 
        ? `${API_V2}/export/m1/${exportSymbol}?start_date=${exportStartDate}&end_date=${exportEndDate}`
        : `${API_V2}/export/${exportTimeframe}/${exportSymbol}?start_date=${exportStartDate}&end_date=${exportEndDate}`;
      
      toast.info(`Exporting ${exportTimeframe} data...`);
      
      const response = await axios.get(endpoint, { responseType: 'blob' });
      
      // Create download link
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `${exportSymbol}_${exportTimeframe}_${exportStartDate}_${exportEndDate}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      
      toast.success('Export complete!');
    } catch (error) {
      toast.error(`Export failed: ${error.response?.data?.detail || error.message}`);
    } finally {
      setExporting(false);
    }
  };

  // Delete symbol data
  const confirmDeleteSymbol = (sym) => {
    setPendingDeleteSymbol(sym);
    setShowDeleteConfirm(true);
  };

  const executeDelete = async () => {
    if (!pendingDeleteSymbol) return;
    
    setDeletingSymbol(pendingDeleteSymbol);
    setShowDeleteConfirm(false);
    
    try {
      const response = await axios.delete(`${API_V2}/delete/${pendingDeleteSymbol}?confirm=true`);
      if (response.data.success) {
        toast.success(`Deleted ${response.data.deleted_count} candles`);
        loadCoverage();
      }
    } catch (error) {
      toast.error(`Delete failed: ${error.response?.data?.detail || error.message}`);
    } finally {
      setDeletingSymbol(null);
      setPendingDeleteSymbol(null);
    }
  };

  const ConfidenceBadge = ({ level }) => {
    const config = CONFIDENCE_COLORS[level] || CONFIDENCE_COLORS.low;
    const Icon = config.icon;
    return (
      <Badge variant="outline" className={`${config.border} ${config.text} ${config.bg}`}>
        <Icon className="w-3 h-3 mr-1" />
        {level?.toUpperCase()}
      </Badge>
    );
  };

  const getFileAccept = () => {
    if (uploadType === 'bi5') return '.bi5';
    if (uploadType === 'bi5-zip') return '.zip';
    return '.csv';
  };

  return (
    <div className="min-h-screen bg-[#0A0A0B] text-white overflow-y-auto">
      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && pendingDeleteSymbol && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#18181B] border border-red-500/30 rounded-xl p-6 max-w-md w-full shadow-2xl">
            <div className="flex items-start gap-4">
              <div className="p-3 bg-red-500/20 rounded-full">
                <AlertTriangle className="w-6 h-6 text-red-500" />
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-bold text-white mb-2">Delete All Data?</h3>
                <p className="text-sm text-zinc-400 mb-4">
                  Delete ALL M1 data for <span className="font-mono text-white font-bold">{pendingDeleteSymbol}</span>?
                </p>
                <p className="text-xs text-red-400 mb-4">This action cannot be undone.</p>
                <div className="flex gap-3">
                  <Button onClick={() => setShowDeleteConfirm(false)} variant="outline" className="flex-1 border-zinc-600">
                    Cancel
                  </Button>
                  <Button onClick={executeDelete} className="flex-1 bg-red-600 hover:bg-red-700 text-white">
                    <Trash2 className="w-4 h-4 mr-2" />Delete
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
              <Button onClick={() => navigate('/')} variant="ghost" size="sm" className="text-zinc-400 hover:text-white">
                <ArrowLeft className="w-4 h-4 mr-2" />Back
              </Button>
              <div className="w-px h-6 bg-white/10" />
              <div className="flex items-center gap-3">
                <Database className="w-6 h-6 text-blue-400" />
                <div>
                  <h1 className="text-xl font-bold">Market Data (M1 SSOT)</h1>
                  <p className="text-xs text-zinc-500">Single Source of Truth Architecture</p>
                </div>
              </div>
            </div>
            <Badge variant="outline" className="border-emerald-500/40 text-emerald-400 bg-emerald-500/10">
              <Binary className="w-3 h-3 mr-1" />V2 API
            </Badge>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-8">
        {/* Info Banner */}
        <Card className="bg-blue-950/20 border-blue-500/30 p-4 mb-6">
          <div className="flex items-start gap-3">
            <Info className="w-5 h-5 text-blue-400 mt-0.5" />
            <div className="text-sm">
              <p className="font-bold text-blue-400 mb-1">M1 Single Source of Truth (SSOT)</p>
              <p className="text-zinc-400 text-xs">
                Only M1 candles are stored. All other timeframes derived on-demand via aggregation.
              </p>
              <div className="flex gap-4 mt-2 text-xs">
                <div className="flex items-center gap-1">
                  <ShieldCheck className="w-3 h-3 text-emerald-400" />
                  <span className="text-emerald-400">HIGH = Production</span>
                </div>
                <div className="flex items-center gap-1">
                  <ShieldAlert className="w-3 h-3 text-yellow-400" />
                  <span className="text-yellow-400">MEDIUM = Research</span>
                </div>
                <div className="flex items-center gap-1">
                  <ShieldX className="w-3 h-3 text-red-400" />
                  <span className="text-red-400">LOW = Never backtest</span>
                </div>
              </div>
            </div>
          </div>
        </Card>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
          <TabsList className="bg-[#0F0F10] border border-white/10 p-1">
            <TabsTrigger value="upload" className="data-[state=active]:bg-blue-600">
              <Upload className="w-4 h-4 mr-2" />Upload
            </TabsTrigger>
            <TabsTrigger value="coverage" className="data-[state=active]:bg-blue-600">
              <Layers className="w-4 h-4 mr-2" />Coverage
            </TabsTrigger>
            <TabsTrigger value="export" className="data-[state=active]:bg-blue-600">
              <Download className="w-4 h-4 mr-2" />Export
            </TabsTrigger>
          </TabsList>

          {/* Upload Tab */}
          <TabsContent value="upload">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card className="bg-[#0F0F10] border-white/10 p-6">
                <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
                  <Upload className="w-5 h-5 text-blue-400" />Upload Data
                </h2>

                <div className="space-y-4">
                  {/* Upload Type Selection */}
                  <div>
                    <label className="text-xs text-zinc-400 uppercase tracking-wider mb-2 block">Data Type</label>
                    <div className="grid grid-cols-3 gap-2">
                      <button
                        onClick={() => { setUploadType('csv'); setSelectedFile(null); }}
                        className={`p-3 rounded-lg border-2 transition-all text-left ${
                          uploadType === 'csv' ? 'border-blue-500 bg-blue-500/10' : 'border-white/10 bg-[#18181B] hover:border-white/20'
                        }`}
                      >
                        <FileSpreadsheet className={`w-5 h-5 mb-1 ${uploadType === 'csv' ? 'text-blue-400' : 'text-zinc-500'}`} />
                        <p className="font-bold text-xs">CSV (M1)</p>
                      </button>
                      <button
                        onClick={() => { setUploadType('bi5'); setSelectedFile(null); }}
                        className={`p-3 rounded-lg border-2 transition-all text-left ${
                          uploadType === 'bi5' ? 'border-blue-500 bg-blue-500/10' : 'border-white/10 bg-[#18181B] hover:border-white/20'
                        }`}
                      >
                        <Binary className={`w-5 h-5 mb-1 ${uploadType === 'bi5' ? 'text-blue-400' : 'text-zinc-500'}`} />
                        <p className="font-bold text-xs">BI5 Single</p>
                      </button>
                      <button
                        onClick={() => { setUploadType('bi5-zip'); setSelectedFile(null); }}
                        className={`p-3 rounded-lg border-2 transition-all text-left ${
                          uploadType === 'bi5-zip' ? 'border-purple-500 bg-purple-500/10' : 'border-white/10 bg-[#18181B] hover:border-white/20'
                        }`}
                      >
                        <Archive className={`w-5 h-5 mb-1 ${uploadType === 'bi5-zip' ? 'text-purple-400' : 'text-zinc-500'}`} />
                        <p className="font-bold text-xs">BI5 ZIP Bulk</p>
                      </button>
                    </div>
                  </div>

                  {/* Symbol Selection */}
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

                  {/* BI5 Hour Selection */}
                  {uploadType === 'bi5' && (
                    <div>
                      <label className="text-xs text-zinc-400 uppercase tracking-wider mb-2 block">Hour Timestamp (UTC)</label>
                      <input
                        type="datetime-local"
                        value={bi5Hour}
                        onChange={(e) => setBi5Hour(e.target.value)}
                        className="w-full bg-[#18181B] border border-white/10 rounded-md px-3 py-2 text-sm"
                      />
                      <p className="text-xs text-zinc-500 mt-1">The hour this BI5 file represents</p>
                    </div>
                  )}

                  {/* ZIP Info */}
                  {uploadType === 'bi5-zip' && (
                    <div className="bg-purple-500/10 border border-purple-500/30 p-3 rounded-lg">
                      <p className="text-xs text-purple-300 font-bold mb-1">📦 Bulk Upload</p>
                      <p className="text-xs text-zinc-400">
                        ZIP containing multiple .bi5 files. Date/hour is extracted from filenames.
                        Files are processed sequentially.
                      </p>
                    </div>
                  )}

                  {/* File Drop Zone */}
                  <div
                    className={`border-2 border-dashed rounded-lg p-6 text-center transition-all ${
                      dragActive ? 'border-blue-500 bg-blue-500/10' : 'border-white/20 bg-[#18181B]'
                    }`}
                    onDragEnter={handleDrag}
                    onDragLeave={handleDrag}
                    onDragOver={handleDrag}
                    onDrop={handleDrop}
                  >
                    <input type="file" id="file-input" accept={getFileAccept()} onChange={handleFileInput} className="hidden" />
                    
                    {selectedFile ? (
                      <div className="space-y-2">
                        {uploadType === 'bi5-zip' ? (
                          <Archive className="w-10 h-10 mx-auto text-purple-400" />
                        ) : uploadType === 'bi5' ? (
                          <Binary className="w-10 h-10 mx-auto text-emerald-400" />
                        ) : (
                          <FileSpreadsheet className="w-10 h-10 mx-auto text-emerald-400" />
                        )}
                        <p className="text-sm font-mono text-white">{selectedFile.name}</p>
                        <p className="text-xs text-zinc-500">{(selectedFile.size / 1024).toFixed(2)} KB</p>
                        <Button onClick={() => setSelectedFile(null)} variant="outline" size="sm">Remove</Button>
                      </div>
                    ) : (
                      <div className="space-y-2">
                        <Upload className="w-10 h-10 mx-auto text-zinc-500" />
                        <p className="text-sm text-zinc-300">
                          Drag & drop {uploadType === 'bi5-zip' ? 'ZIP' : uploadType === 'bi5' ? 'BI5' : 'CSV'} file
                        </p>
                        <label htmlFor="file-input" className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-md cursor-pointer">
                          <FileText className="w-4 h-4" />Browse
                        </label>
                      </div>
                    )}
                  </div>

                  {/* Progress Bar */}
                  {uploading && (
                    <div className="space-y-2">
                      <Progress value={uploadProgress} className="h-2" />
                      <p className="text-xs text-zinc-500 text-center">{uploadProgress}% - Processing...</p>
                    </div>
                  )}

                  {/* Upload Button */}
                  <Button 
                    onClick={uploadType === 'bi5-zip' ? uploadBI5Zip : uploadType === 'bi5' ? uploadBI5 : uploadCSV} 
                    disabled={!selectedFile || uploading || (uploadType === 'bi5' && !bi5Hour)} 
                    className={`w-full ${uploadType === 'bi5-zip' ? 'bg-purple-600 hover:bg-purple-700' : 'bg-blue-600 hover:bg-blue-700'}`}
                  >
                    {uploading ? (
                      <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Processing...</>
                    ) : (
                      <><Upload className="w-4 h-4 mr-2" />Upload {uploadType === 'bi5-zip' ? 'ZIP' : uploadType === 'bi5' ? 'BI5' : 'CSV'}</>
                    )}
                  </Button>

                  {/* Upload Result */}
                  {uploadResult && (
                    <div className={`p-4 rounded-md border ${
                      uploadResult.success ? 'bg-emerald-500/10 border-emerald-500/30' : 'bg-red-500/10 border-red-500/30'
                    }`}>
                      <div className="flex items-start gap-3">
                        {uploadResult.success ? (
                          <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                        ) : (
                          <XCircle className="w-5 h-5 text-red-400" />
                        )}
                        <div className="flex-1 text-sm">
                          {uploadResult.success ? (
                            <>
                              <p className="font-bold text-emerald-400 mb-2">
                                {uploadResult.isBulk ? 'Bulk Upload Complete!' : 'Upload Successful!'}
                              </p>
                              <div className="space-y-1 text-xs text-zinc-300">
                                {uploadResult.isBulk ? (
                                  <>
                                    <p>Files: <span className="text-emerald-400">{uploadResult.files_successful}/{uploadResult.files_processed}</span></p>
                                    <p>Total Candles: <span className="font-mono text-emerald-400">{uploadResult.total_candles_stored}</span></p>
                                  </>
                                ) : (
                                  <>
                                    <p>Candles Stored: <span className="font-mono text-emerald-400">{uploadResult.candles_stored}</span></p>
                                    <p>Confidence: <ConfidenceBadge level={uploadResult.confidence_assigned || 'high'} /></p>
                                  </>
                                )}
                              </div>
                            </>
                          ) : (
                            <>
                              <p className="font-bold text-red-400 mb-1">Upload Failed</p>
                              {uploadResult.detected_timeframe && uploadResult.detected_timeframe !== 'M1' && (
                                <div className="bg-red-900/30 rounded p-2 mb-2">
                                  <p className="text-xs text-red-300">
                                    <strong>Detected:</strong> {uploadResult.detected_timeframe}
                                  </p>
                                  <p className="text-xs text-red-400 mt-1">
                                    ⚠️ Only M1 data accepted. Higher TF cannot be converted.
                                  </p>
                                </div>
                              )}
                              <p className="text-xs text-zinc-300">{uploadResult.error || uploadResult.errors?.[0]}</p>
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </Card>

              {/* Guidelines */}
              <div className="space-y-4">
                <Card className="bg-[#0F0F10] border-blue-500/30 p-6">
                  <div className="flex items-start gap-3">
                    <AlertCircle className="w-5 h-5 text-blue-400 mt-0.5" />
                    <div className="text-sm space-y-3">
                      <p className="font-bold text-blue-400">M1 SSOT Upload Rules</p>
                      <div className="space-y-2 text-xs">
                        <div className="p-2 bg-emerald-500/10 border border-emerald-500/30 rounded">
                          <p className="font-bold text-emerald-400 flex items-center gap-1">
                            <CheckCircle2 className="w-3 h-3" /> ACCEPTED
                          </p>
                          <p className="text-zinc-400 mt-1">• BI5 tick data (single or ZIP bulk)</p>
                          <p className="text-zinc-400">• M1 (1-minute) CSV files</p>
                        </div>
                        <div className="p-2 bg-red-500/10 border border-red-500/30 rounded">
                          <p className="font-bold text-red-400 flex items-center gap-1">
                            <XCircle className="w-3 h-3" /> REJECTED
                          </p>
                          <p className="text-zinc-400 mt-1">• M5, M15, M30 CSV files</p>
                          <p className="text-zinc-400">• H1, H4, D1, W1 CSV files</p>
                        </div>
                      </div>
                    </div>
                  </div>
                </Card>
              </div>
            </div>
          </TabsContent>

          {/* Coverage Tab */}
          <TabsContent value="coverage">
            <div className="space-y-4">
              <div className="flex items-center justify-between flex-wrap gap-3">
                <h2 className="text-lg font-bold flex items-center gap-2">
                  <Layers className="w-5 h-5 text-blue-400" />M1 Coverage
                </h2>
                <div className="flex items-center gap-3">
                  <Select value={selectedCoverageSymbol} onValueChange={setSelectedCoverageSymbol}>
                    <SelectTrigger className="bg-[#18181B] border-white/10 w-40">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {SYMBOLS.map(s => (
                        <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Button onClick={loadCoverage} disabled={loadingCoverage} variant="outline" size="sm">
                    {loadingCoverage ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                  </Button>
                </div>
              </div>

              {loadingCoverage ? (
                <Card className="bg-[#0F0F10] border-white/10 p-12">
                  <div className="text-center">
                    <Loader2 className="w-8 h-8 animate-spin mx-auto text-blue-400 mb-3" />
                    <p className="text-sm text-zinc-500">Loading coverage...</p>
                  </div>
                </Card>
              ) : coverage && coverage.total_m1_candles > 0 ? (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {/* Coverage Stats */}
                  <Card className="bg-[#0F0F10] border-white/10 p-6">
                    <h3 className="font-bold text-sm mb-4">{coverage.symbol} M1 Coverage</h3>
                    <div className="space-y-4">
                      <div className="grid grid-cols-2 gap-4">
                        <div className="bg-[#18181B] p-4 rounded-lg">
                          <p className="text-xs text-zinc-500 mb-1">Total M1 Candles</p>
                          <p className="text-2xl font-bold font-mono">{coverage.total_m1_candles?.toLocaleString()}</p>
                        </div>
                        <div className="bg-[#18181B] p-4 rounded-lg">
                          <p className="text-xs text-zinc-500 mb-1">Coverage</p>
                          <p className="text-2xl font-bold font-mono text-emerald-400">{coverage.coverage_percentage?.toFixed(1)}%</p>
                        </div>
                      </div>

                      {coverage.first_timestamp && (
                        <div className="bg-[#18181B] p-3 rounded-lg">
                          <p className="text-xs text-zinc-500 mb-1">Date Range</p>
                          <p className="text-sm font-mono text-zinc-300">
                            {new Date(coverage.first_timestamp).toLocaleDateString()} → {new Date(coverage.last_timestamp).toLocaleDateString()}
                          </p>
                        </div>
                      )}

                      {/* Confidence */}
                      <div>
                        <p className="text-xs text-zinc-500 mb-2">Confidence Distribution</p>
                        <div className="space-y-2">
                          <div className="flex items-center justify-between text-xs">
                            <span className="flex items-center gap-2"><ShieldCheck className="w-3 h-3 text-emerald-400" />HIGH</span>
                            <span className="font-mono text-emerald-400">{coverage.high_confidence_count?.toLocaleString() || 0}</span>
                          </div>
                          <div className="flex items-center justify-between text-xs">
                            <span className="flex items-center gap-2"><ShieldAlert className="w-3 h-3 text-yellow-400" />MEDIUM</span>
                            <span className="font-mono text-yellow-400">{coverage.medium_confidence_count?.toLocaleString() || 0}</span>
                          </div>
                          <div className="flex items-center justify-between text-xs">
                            <span className="flex items-center gap-2"><ShieldX className="w-3 h-3 text-red-400" />LOW</span>
                            <span className="font-mono text-red-400">{coverage.low_confidence_count?.toLocaleString() || 0}</span>
                          </div>
                        </div>
                        
                        {coverage.low_confidence_count > 0 && (
                          <Button onClick={purgeLowConfidence} size="sm" className="w-full mt-3 bg-red-600 hover:bg-red-700">
                            <Trash2 className="w-3 h-3 mr-2" />Purge {coverage.low_confidence_count} Low Confidence
                          </Button>
                        )}
                      </div>

                      <Button
                        onClick={() => confirmDeleteSymbol(coverage.symbol)}
                        disabled={deletingSymbol === coverage.symbol}
                        variant="outline"
                        className="w-full border-red-500/30 text-red-400 hover:bg-red-500/10"
                      >
                        <Trash2 className="w-4 h-4 mr-2" />Delete All {coverage.symbol} Data
                      </Button>
                    </div>
                  </Card>

                  {/* Gap Detection */}
                  <Card className="bg-[#0F0F10] border-white/10 p-6">
                    <h3 className="font-bold text-sm mb-4 flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4 text-yellow-400" />Gap Detection
                    </h3>

                    {loadingGaps ? (
                      <div className="text-center py-8">
                        <Loader2 className="w-6 h-6 animate-spin mx-auto text-blue-400" />
                      </div>
                    ) : gaps.length > 0 ? (
                      <div className="space-y-4">
                        <div className="bg-yellow-500/10 border border-yellow-500/30 p-3 rounded-lg">
                          <p className="text-sm text-yellow-400 font-bold">{gaps.length} Gap{gaps.length > 1 ? 's' : ''} Detected</p>
                          <p className="text-xs text-zinc-400">Only fixable with real Dukascopy data.</p>
                        </div>

                        <div className="max-h-40 overflow-y-auto space-y-2">
                          {gaps.slice(0, 5).map((gap, idx) => (
                            <div key={idx} className="bg-[#18181B] p-2 rounded text-xs">
                              <div className="flex items-center justify-between">
                                <span className="font-mono text-yellow-400">{gap.missing_minutes} min</span>
                                {gap.is_market_closed && <Badge variant="outline" className="text-zinc-500 border-zinc-600 text-[10px]">Weekend</Badge>}
                              </div>
                            </div>
                          ))}
                        </div>

                        <Button onClick={fixGaps} disabled={fixingGaps} className="w-full bg-yellow-600 hover:bg-yellow-700 text-black font-bold">
                          {fixingGaps ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Fixing...</> : <><Zap className="w-4 h-4 mr-2" />Fix Gaps</>}
                        </Button>
                      </div>
                    ) : (
                      <div className="text-center py-8">
                        <CheckCircle2 className="w-10 h-10 mx-auto text-emerald-400 mb-2" />
                        <p className="text-sm text-emerald-400 font-bold">No Gaps</p>
                      </div>
                    )}
                  </Card>
                </div>
              ) : (
                <Card className="bg-[#0F0F10] border-white/10 p-12">
                  <div className="text-center">
                    <Database className="w-12 h-12 mx-auto text-zinc-600 mb-3" />
                    <p className="text-sm text-zinc-500">No data for {selectedCoverageSymbol}</p>
                  </div>
                </Card>
              )}
            </div>
          </TabsContent>

          {/* Export Tab */}
          <TabsContent value="export">
            <Card className="bg-[#0F0F10] border-white/10 p-6 max-w-xl">
              <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
                <Download className="w-5 h-5 text-blue-400" />Export Data
              </h2>
              <p className="text-xs text-zinc-500 mb-4">
                Export data as CSV. All timeframes are derived from M1 (SSOT).
              </p>

              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
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
                </div>

                <div className="grid grid-cols-2 gap-4">
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

                <div className="bg-[#18181B] p-3 rounded-lg text-xs text-zinc-400">
                  <p className="flex items-center gap-2">
                    <Info className="w-3 h-3" />
                    {exportTimeframe === 'M1' 
                      ? 'Exporting raw M1 data (SSOT)' 
                      : `${exportTimeframe} will be aggregated from M1 on-demand`}
                  </p>
                </div>

                <Button 
                  onClick={exportData} 
                  disabled={exporting || !exportStartDate || !exportEndDate} 
                  className="w-full bg-blue-600 hover:bg-blue-700"
                >
                  {exporting ? (
                    <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Exporting...</>
                  ) : (
                    <><FileDown className="w-4 h-4 mr-2" />Download {exportTimeframe} CSV</>
                  )}
                </Button>
              </div>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
