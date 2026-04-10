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
  Download, Activity, AlertTriangle, RefreshCw, FileDown, Layers, Zap, Trash2,
  ShieldCheck, ShieldAlert, ShieldX, Binary, Info
} from 'lucide-react';
import { formatDate, formatDateRange, formatDateTime } from '@/lib/dateUtils';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
// Use V2 API endpoints (M1 SSOT Architecture)
const API_V2 = `${BACKEND_URL}/api/v2/data`;

const SYMBOLS = [
  { value: 'XAUUSD', label: 'XAU/USD (Gold)', enabled: true },
  { value: 'EURUSD', label: 'EUR/USD', enabled: true },
  { value: 'GBPUSD', label: 'GBP/USD', enabled: true },
  { value: 'USDJPY', label: 'USD/JPY', enabled: true },
  { value: 'NAS100', label: 'NAS100 (US100)', enabled: true },
];

// M1 SSOT: Only M1 is accepted for upload, other TFs are derived
const UPLOAD_INFO = {
  bi5: {
    name: 'BI5 Tick Data',
    description: 'Dukascopy tick data files (.bi5)',
    confidence: 'HIGH',
    accept: '.bi5'
  },
  csv: {
    name: 'M1 CSV Data',
    description: 'Only M1 (1-minute) CSV files accepted',
    confidence: 'HIGH',
    accept: '.csv'
  }
};

// Confidence colors
const CONFIDENCE_COLORS = {
  high: { bg: 'bg-emerald-500/20', border: 'border-emerald-500/40', text: 'text-emerald-400', icon: ShieldCheck },
  medium: { bg: 'bg-yellow-500/20', border: 'border-yellow-500/40', text: 'text-yellow-400', icon: ShieldAlert },
  low: { bg: 'bg-red-500/20', border: 'border-red-500/40', text: 'text-red-400', icon: ShieldX }
};

export default function MarketDataPage() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('upload');
  
  // Upload States
  const [uploadType, setUploadType] = useState('csv'); // 'bi5' or 'csv'
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [symbol, setSymbol] = useState('EURUSD');
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);
  
  // BI5 specific state
  const [bi5Hour, setBi5Hour] = useState('');
  
  // Coverage States (M1 SSOT)
  const [coverage, setCoverage] = useState(null);
  const [loadingCoverage, setLoadingCoverage] = useState(false);
  const [selectedCoverageSymbol, setSelectedCoverageSymbol] = useState('EURUSD');
  
  // Quality Report States
  const [qualityReport, setQualityReport] = useState(null);
  const [loadingQuality, setLoadingQuality] = useState(false);
  
  // Gap States
  const [gaps, setGaps] = useState([]);
  const [loadingGaps, setLoadingGaps] = useState(false);
  const [fixingGaps, setFixingGaps] = useState(false);
  
  // Delete States
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [pendingDeleteSymbol, setPendingDeleteSymbol] = useState(null);
  const [deletingSymbol, setDeletingSymbol] = useState(null);

  useEffect(() => {
    if (activeTab === 'coverage') {
      loadCoverage();
    }
  }, [activeTab, selectedCoverageSymbol]);

  // Load coverage from V2 API
  const loadCoverage = async () => {
    setLoadingCoverage(true);
    try {
      const response = await axios.get(`${API_V2}/coverage/${selectedCoverageSymbol}`);
      setCoverage(response.data);
      
      // Also load gaps
      await loadGaps();
      
    } catch (error) {
      if (error.response?.status === 404 || error.response?.data?.total_m1_candles === 0) {
        setCoverage({ symbol: selectedCoverageSymbol, total_m1_candles: 0 });
      } else {
        console.error('Failed to load coverage:', error);
        toast.error('Failed to load coverage data');
      }
    } finally {
      setLoadingCoverage(false);
    }
  };

  // Load gaps from V2 API
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

  // Fix gaps using V2 API (real data only)
  const fixGaps = async () => {
    setFixingGaps(true);
    try {
      const response = await axios.post(`${API_V2}/gaps/${selectedCoverageSymbol}/fix`);
      
      if (response.data.success) {
        toast.success(response.data.message);
        // Reload coverage and gaps
        await loadCoverage();
      } else {
        toast.warning(response.data.message || 'No gaps to fix');
      }
    } catch (error) {
      const errorMsg = error.response?.data?.detail || error.message;
      toast.error(`Gap fix failed: ${errorMsg}`);
    } finally {
      setFixingGaps(false);
    }
  };

  // Purge low confidence data
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

  // CSV Upload - M1 ONLY
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
    const expectedExt = uploadType === 'bi5' ? '.bi5' : '.csv';
    if (!file.name.toLowerCase().endsWith(expectedExt)) {
      toast.error(`Please select a ${expectedExt.toUpperCase()} file`);
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

  // Upload CSV via V2 API (M1 ONLY)
  const uploadCSV = async () => {
    if (!selectedFile) {
      toast.error('Please select a file');
      return;
    }

    setUploading(true);
    setUploadResult(null);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('symbol', symbol);
      // No timeframe selection - M1 is enforced by backend
      // No declared_timeframe - auto-detection will reject non-M1

      toast.info('Uploading CSV data (M1 only accepted)...');
      const response = await axios.post(`${API_V2}/upload/csv`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      if (response.data.success) {
        setUploadResult({
          success: true,
          ...response.data
        });
        toast.success(`✅ Uploaded ${response.data.candles_stored} M1 candles`);
        setSelectedFile(null);
      } else {
        // REJECTION - Higher TF detected
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

  // Upload BI5 via V2 API
  const uploadBI5 = async () => {
    if (!selectedFile) {
      toast.error('Please select a BI5 file');
      return;
    }

    if (!bi5Hour) {
      toast.error('Please specify the hour timestamp for this BI5 file');
      return;
    }

    setUploading(true);
    setUploadResult(null);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('symbol', symbol);
      formData.append('hour', bi5Hour);

      toast.info('Processing BI5 tick data...');
      const response = await axios.post(`${API_V2}/upload/bi5`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      if (response.data.success) {
        setUploadResult({
          success: true,
          ...response.data
        });
        toast.success(`✅ Converted ${response.data.candles_stored} M1 candles from tick data`);
        setSelectedFile(null);
        setBi5Hour('');
      }
    } catch (error) {
      const errorMsg = error.response?.data?.detail || error.message;
      toast.error(`BI5 upload failed: ${errorMsg}`);
      setUploadResult({ success: false, error: errorMsg });
    } finally {
      setUploading(false);
    }
  };

  // Delete all data for symbol
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
        toast.success(`Deleted ${response.data.deleted_count} candles for ${pendingDeleteSymbol}`);
        loadCoverage();
      }
    } catch (error) {
      const errorMsg = error.response?.data?.detail || error.message;
      toast.error(`Delete failed: ${errorMsg}`);
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
        {level.toUpperCase()}
      </Badge>
    );
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
                  Are you sure you want to delete ALL M1 data for{' '}
                  <span className="font-mono text-white font-bold">{pendingDeleteSymbol}</span>?
                </p>
                <p className="text-xs text-red-400 mb-4">
                  This action cannot be undone. All candle data will be permanently removed.
                </p>
                <div className="flex gap-3">
                  <Button
                    onClick={() => setShowDeleteConfirm(false)}
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
                  <h1 className="text-xl font-bold">Market Data (M1 SSOT)</h1>
                  <p className="text-xs text-zinc-500">Single Source of Truth Architecture</p>
                </div>
              </div>
            </div>
            <Badge variant="outline" className="border-emerald-500/40 text-emerald-400 bg-emerald-500/10">
              <Binary className="w-3 h-3 mr-1" />
              V2 API Active
            </Badge>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-8 overflow-y-auto">
        {/* M1 SSOT Info Banner */}
        <Card className="bg-blue-950/20 border-blue-500/30 p-4 mb-6">
          <div className="flex items-start gap-3">
            <Info className="w-5 h-5 text-blue-400 mt-0.5" />
            <div className="text-sm">
              <p className="font-bold text-blue-400 mb-1">M1 Single Source of Truth (SSOT) Architecture</p>
              <p className="text-zinc-400 text-xs">
                Only M1 (1-minute) candles are stored. All other timeframes (M5, H1, H4, D1) are derived on-demand via aggregation.
                This ensures data consistency and eliminates discrepancies.
              </p>
              <div className="flex gap-4 mt-2 text-xs">
                <div className="flex items-center gap-1">
                  <ShieldCheck className="w-3 h-3 text-emerald-400" />
                  <span className="text-emerald-400">HIGH = Production ready</span>
                </div>
                <div className="flex items-center gap-1">
                  <ShieldAlert className="w-3 h-3 text-yellow-400" />
                  <span className="text-yellow-400">MEDIUM = Research only</span>
                </div>
                <div className="flex items-center gap-1">
                  <ShieldX className="w-3 h-3 text-red-400" />
                  <span className="text-red-400">LOW = Never in backtest</span>
                </div>
              </div>
            </div>
          </div>
        </Card>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
          <TabsList className="bg-[#0F0F10] border border-white/10 p-1 sticky top-0 z-10">
            <TabsTrigger value="upload" className="data-[state=active]:bg-blue-600">
              <Upload className="w-4 h-4 mr-2" />
              Upload
            </TabsTrigger>
            <TabsTrigger value="coverage" className="data-[state=active]:bg-blue-600">
              <Layers className="w-4 h-4 mr-2" />
              Coverage & Quality
            </TabsTrigger>
          </TabsList>

          {/* Upload Tab - M1 SSOT Compliant */}
          <TabsContent value="upload" className="overflow-y-auto">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Upload Form */}
              <Card className="bg-[#0F0F10] border-white/10 p-6">
                <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
                  <Upload className="w-5 h-5 text-blue-400" />
                  Upload Data
                </h2>

                <div className="space-y-4">
                  {/* Upload Type Selection */}
                  <div>
                    <label className="text-xs text-zinc-400 uppercase tracking-wider mb-2 block">Data Type</label>
                    <div className="grid grid-cols-2 gap-3">
                      <button
                        onClick={() => { setUploadType('csv'); setSelectedFile(null); }}
                        className={`p-4 rounded-lg border-2 transition-all text-left ${
                          uploadType === 'csv' 
                            ? 'border-blue-500 bg-blue-500/10' 
                            : 'border-white/10 bg-[#18181B] hover:border-white/20'
                        }`}
                      >
                        <FileSpreadsheet className={`w-6 h-6 mb-2 ${uploadType === 'csv' ? 'text-blue-400' : 'text-zinc-500'}`} />
                        <p className="font-bold text-sm">CSV (M1 Only)</p>
                        <p className="text-xs text-zinc-500">1-minute OHLCV data</p>
                      </button>
                      <button
                        onClick={() => { setUploadType('bi5'); setSelectedFile(null); }}
                        className={`p-4 rounded-lg border-2 transition-all text-left ${
                          uploadType === 'bi5' 
                            ? 'border-blue-500 bg-blue-500/10' 
                            : 'border-white/10 bg-[#18181B] hover:border-white/20'
                        }`}
                      >
                        <Binary className={`w-6 h-6 mb-2 ${uploadType === 'bi5' ? 'text-blue-400' : 'text-zinc-500'}`} />
                        <p className="font-bold text-sm">BI5 Tick Data</p>
                        <p className="text-xs text-zinc-500">Dukascopy tick files</p>
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
                        placeholder="e.g., 2024-01-15T10:00"
                      />
                      <p className="text-xs text-zinc-500 mt-1">The hour this BI5 file represents</p>
                    </div>
                  )}

                  {/* File Drop Zone */}
                  <div
                    className={`border-2 border-dashed rounded-lg p-8 text-center transition-all ${
                      dragActive ? 'border-blue-500 bg-blue-500/10' : 'border-white/20 bg-[#18181B]'
                    }`}
                    onDragEnter={handleDrag}
                    onDragLeave={handleDrag}
                    onDragOver={handleDrag}
                    onDrop={handleDrop}
                  >
                    <input 
                      type="file" 
                      id="file-input" 
                      accept={uploadType === 'bi5' ? '.bi5' : '.csv'} 
                      onChange={handleFileInput} 
                      className="hidden" 
                    />
                    
                    {selectedFile ? (
                      <div className="space-y-3">
                        {uploadType === 'bi5' ? (
                          <Binary className="w-12 h-12 mx-auto text-emerald-400" />
                        ) : (
                          <FileSpreadsheet className="w-12 h-12 mx-auto text-emerald-400" />
                        )}
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
                          <p className="text-sm text-zinc-300 mb-1">
                            Drag & drop {uploadType === 'bi5' ? 'BI5' : 'CSV'} file here
                          </p>
                          <p className="text-xs text-zinc-500 mb-3">or</p>
                          <label htmlFor="file-input" className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-md cursor-pointer">
                            <FileText className="w-4 h-4" />
                            Browse Files
                          </label>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Upload Button */}
                  <Button 
                    onClick={uploadType === 'bi5' ? uploadBI5 : uploadCSV} 
                    disabled={!selectedFile || uploading || (uploadType === 'bi5' && !bi5Hour)} 
                    className="w-full bg-blue-600 hover:bg-blue-700"
                  >
                    {uploading ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Processing...
                      </>
                    ) : (
                      <>
                        <Upload className="w-4 h-4 mr-2" />
                        Upload {uploadType === 'bi5' ? 'BI5' : 'CSV'} Data
                      </>
                    )}
                  </Button>

                  {/* Upload Result */}
                  {uploadResult && (
                    <div className={`p-4 rounded-md border ${
                      uploadResult.success 
                        ? 'bg-emerald-500/10 border-emerald-500/30' 
                        : 'bg-red-500/10 border-red-500/30'
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
                              <p className="font-bold text-emerald-400 mb-2">Upload Successful!</p>
                              <div className="space-y-1 text-xs text-zinc-300">
                                <p>Symbol: <span className="font-mono text-white">{uploadResult.symbol}</span></p>
                                <p>Candles Stored: <span className="font-mono text-emerald-400">{uploadResult.candles_stored}</span></p>
                                <p>Confidence: <ConfidenceBadge level={uploadResult.confidence_assigned || 'high'} /></p>
                              </div>
                            </>
                          ) : (
                            <>
                              <p className="font-bold text-red-400 mb-1">Upload Rejected</p>
                              {uploadResult.detected_timeframe && uploadResult.detected_timeframe !== 'M1' && (
                                <div className="bg-red-900/30 rounded p-2 mb-2">
                                  <p className="text-xs text-red-300">
                                    <strong>Detected Timeframe:</strong> {uploadResult.detected_timeframe}
                                  </p>
                                  <p className="text-xs text-red-400 mt-1">
                                    ⚠️ Only M1 (1-minute) data is accepted. Higher timeframe data cannot be converted.
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

              {/* Upload Guidelines */}
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
                          <p className="text-zinc-400 mt-1">• BI5 tick data files (any symbol)</p>
                          <p className="text-zinc-400">• M1 (1-minute) CSV files</p>
                        </div>
                        
                        <div className="p-2 bg-red-500/10 border border-red-500/30 rounded">
                          <p className="font-bold text-red-400 flex items-center gap-1">
                            <XCircle className="w-3 h-3" /> REJECTED
                          </p>
                          <p className="text-zinc-400 mt-1">• M5, M15, M30 CSV files</p>
                          <p className="text-zinc-400">• H1, H4, D1, W1 CSV files</p>
                          <p className="text-zinc-400">• Any non-M1 timeframe data</p>
                        </div>
                      </div>
                      
                      <p className="text-zinc-500 text-xs">
                        Higher timeframes are derived automatically from M1 data.
                        This ensures consistency across all timeframes.
                      </p>
                    </div>
                  </div>
                </Card>

                <Card className="bg-[#0F0F10] border-white/10 p-6">
                  <h3 className="font-bold text-sm mb-3 flex items-center gap-2">
                    <ShieldCheck className="w-4 h-4 text-emerald-400" />
                    Confidence Levels
                  </h3>
                  <div className="space-y-2 text-xs">
                    <div className="flex items-center justify-between p-2 bg-[#18181B] rounded">
                      <div className="flex items-center gap-2">
                        <ShieldCheck className="w-4 h-4 text-emerald-400" />
                        <span>HIGH</span>
                      </div>
                      <span className="text-zinc-500">Production backtest, live trading</span>
                    </div>
                    <div className="flex items-center justify-between p-2 bg-[#18181B] rounded">
                      <div className="flex items-center gap-2">
                        <ShieldAlert className="w-4 h-4 text-yellow-400" />
                        <span>MEDIUM</span>
                      </div>
                      <span className="text-zinc-500">Research only</span>
                    </div>
                    <div className="flex items-center justify-between p-2 bg-[#18181B] rounded">
                      <div className="flex items-center gap-2">
                        <ShieldX className="w-4 h-4 text-red-400" />
                        <span>LOW</span>
                      </div>
                      <span className="text-zinc-500">Never used in backtest</span>
                    </div>
                  </div>
                </Card>
              </div>
            </div>
          </TabsContent>

          {/* Coverage Tab - M1 SSOT */}
          <TabsContent value="coverage" className="overflow-y-auto">
            <div className="space-y-4">
              <div className="flex items-center justify-between flex-wrap gap-3">
                <h2 className="text-lg font-bold flex items-center gap-2">
                  <Layers className="w-5 h-5 text-blue-400" />
                  M1 Data Coverage
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
                    <span className="ml-2">Refresh</span>
                  </Button>
                </div>
              </div>

              {loadingCoverage ? (
                <Card className="bg-[#0F0F10] border-white/10 p-12">
                  <div className="text-center">
                    <Loader2 className="w-8 h-8 animate-spin mx-auto text-blue-400 mb-3" />
                    <p className="text-sm text-zinc-500">Analyzing M1 data coverage...</p>
                  </div>
                </Card>
              ) : coverage && coverage.total_m1_candles > 0 ? (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {/* Coverage Stats */}
                  <Card className="bg-[#0F0F10] border-white/10 p-6">
                    <h3 className="font-bold text-sm mb-4 flex items-center gap-2">
                      <Database className="w-4 h-4 text-blue-400" />
                      {coverage.symbol} M1 Coverage
                    </h3>
                    
                    <div className="space-y-4">
                      <div className="grid grid-cols-2 gap-4">
                        <div className="bg-[#18181B] p-4 rounded-lg">
                          <p className="text-xs text-zinc-500 mb-1">Total M1 Candles</p>
                          <p className="text-2xl font-bold font-mono text-white">
                            {coverage.total_m1_candles?.toLocaleString()}
                          </p>
                        </div>
                        <div className="bg-[#18181B] p-4 rounded-lg">
                          <p className="text-xs text-zinc-500 mb-1">Coverage</p>
                          <p className="text-2xl font-bold font-mono text-emerald-400">
                            {coverage.coverage_percentage?.toFixed(1)}%
                          </p>
                        </div>
                      </div>

                      {/* Date Range */}
                      {coverage.first_timestamp && (
                        <div className="bg-[#18181B] p-3 rounded-lg">
                          <p className="text-xs text-zinc-500 mb-1">Date Range</p>
                          <p className="text-sm font-mono text-zinc-300">
                            {new Date(coverage.first_timestamp).toLocaleDateString()} → {new Date(coverage.last_timestamp).toLocaleDateString()}
                          </p>
                        </div>
                      )}

                      {/* Confidence Breakdown */}
                      <div>
                        <p className="text-xs text-zinc-500 mb-2">Confidence Distribution</p>
                        <div className="space-y-2">
                          <div className="flex items-center justify-between text-xs">
                            <div className="flex items-center gap-2">
                              <ShieldCheck className="w-3 h-3 text-emerald-400" />
                              <span>HIGH</span>
                            </div>
                            <span className="font-mono text-emerald-400">
                              {coverage.high_confidence_count?.toLocaleString() || 0}
                            </span>
                          </div>
                          <div className="flex items-center justify-between text-xs">
                            <div className="flex items-center gap-2">
                              <ShieldAlert className="w-3 h-3 text-yellow-400" />
                              <span>MEDIUM</span>
                            </div>
                            <span className="font-mono text-yellow-400">
                              {coverage.medium_confidence_count?.toLocaleString() || 0}
                            </span>
                          </div>
                          <div className="flex items-center justify-between text-xs">
                            <div className="flex items-center gap-2">
                              <ShieldX className="w-3 h-3 text-red-400" />
                              <span>LOW</span>
                            </div>
                            <span className="font-mono text-red-400">
                              {coverage.low_confidence_count?.toLocaleString() || 0}
                            </span>
                          </div>
                        </div>
                        
                        {/* Purge Low Confidence Button */}
                        {coverage.low_confidence_count > 0 && (
                          <Button
                            onClick={purgeLowConfidence}
                            size="sm"
                            className="w-full mt-3 bg-red-600 hover:bg-red-700"
                          >
                            <Trash2 className="w-3 h-3 mr-2" />
                            Purge {coverage.low_confidence_count} Low Confidence Candles
                          </Button>
                        )}
                      </div>

                      {/* Source Breakdown */}
                      {coverage.source_breakdown && Object.keys(coverage.source_breakdown).length > 0 && (
                        <div>
                          <p className="text-xs text-zinc-500 mb-2">Data Sources</p>
                          <div className="space-y-1">
                            {Object.entries(coverage.source_breakdown).map(([source, count]) => (
                              <div key={source} className="flex items-center justify-between text-xs bg-[#18181B] p-2 rounded">
                                <span className="text-zinc-400">{source}</span>
                                <span className="font-mono text-white">{count.toLocaleString()}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Delete All Button */}
                      <Button
                        onClick={() => confirmDeleteSymbol(coverage.symbol)}
                        disabled={deletingSymbol === coverage.symbol}
                        variant="outline"
                        className="w-full border-red-500/30 text-red-400 hover:bg-red-500/10"
                      >
                        {deletingSymbol === coverage.symbol ? (
                          <>
                            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                            Deleting...
                          </>
                        ) : (
                          <>
                            <Trash2 className="w-4 h-4 mr-2" />
                            Delete All {coverage.symbol} Data
                          </>
                        )}
                      </Button>
                    </div>
                  </Card>

                  {/* Gap Detection */}
                  <Card className="bg-[#0F0F10] border-white/10 p-6">
                    <h3 className="font-bold text-sm mb-4 flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4 text-yellow-400" />
                      Gap Detection
                    </h3>

                    {loadingGaps ? (
                      <div className="text-center py-8">
                        <Loader2 className="w-6 h-6 animate-spin mx-auto text-blue-400 mb-2" />
                        <p className="text-xs text-zinc-500">Detecting gaps...</p>
                      </div>
                    ) : gaps.length > 0 ? (
                      <div className="space-y-4">
                        <div className="bg-yellow-500/10 border border-yellow-500/30 p-3 rounded-lg">
                          <p className="text-sm text-yellow-400 font-bold mb-1">
                            {gaps.length} Gap{gaps.length > 1 ? 's' : ''} Detected
                          </p>
                          <p className="text-xs text-zinc-400">
                            Gaps can only be fixed with real Dukascopy data (no interpolation).
                          </p>
                        </div>

                        <div className="max-h-48 overflow-y-auto space-y-2">
                          {gaps.slice(0, 10).map((gap, idx) => (
                            <div key={idx} className="bg-[#18181B] p-2 rounded text-xs">
                              <div className="flex items-center justify-between">
                                <span className="font-mono text-yellow-400">
                                  {gap.missing_minutes} minutes
                                </span>
                                {gap.is_market_closed && (
                                  <Badge variant="outline" className="text-zinc-500 border-zinc-600">
                                    Weekend
                                  </Badge>
                                )}
                              </div>
                              <p className="text-zinc-500 mt-1">
                                {new Date(gap.start).toLocaleString()} → {new Date(gap.end).toLocaleString()}
                              </p>
                            </div>
                          ))}
                          {gaps.length > 10 && (
                            <p className="text-xs text-zinc-500 text-center">
                              +{gaps.length - 10} more gaps...
                            </p>
                          )}
                        </div>

                        <Button
                          onClick={fixGaps}
                          disabled={fixingGaps}
                          className="w-full bg-yellow-600 hover:bg-yellow-700 text-black font-bold"
                        >
                          {fixingGaps ? (
                            <>
                              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                              Fixing Gaps...
                            </>
                          ) : (
                            <>
                              <Zap className="w-4 h-4 mr-2" />
                              Fix Gaps (Real Data Only)
                            </>
                          )}
                        </Button>

                        <p className="text-[10px] text-zinc-500 text-center">
                          ⚠️ Gap fixing requires Dukascopy downloader. No synthetic data is generated.
                        </p>
                      </div>
                    ) : (
                      <div className="text-center py-8">
                        <CheckCircle2 className="w-12 h-12 mx-auto text-emerald-400 mb-3" />
                        <p className="text-sm text-emerald-400 font-bold">No Gaps Detected</p>
                        <p className="text-xs text-zinc-500 mt-1">Data is continuous</p>
                      </div>
                    )}
                  </Card>
                </div>
              ) : (
                <Card className="bg-[#0F0F10] border-white/10 p-12">
                  <div className="text-center">
                    <Database className="w-12 h-12 mx-auto text-zinc-600 mb-3" />
                    <p className="text-sm text-zinc-500 mb-1">No M1 data found for {selectedCoverageSymbol}</p>
                    <p className="text-xs text-zinc-600">Upload M1 CSV or BI5 tick data</p>
                  </div>
                </Card>
              )}
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
