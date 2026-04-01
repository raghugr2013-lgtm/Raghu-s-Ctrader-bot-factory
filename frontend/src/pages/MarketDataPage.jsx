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
  Download, Activity, AlertTriangle, RefreshCw, FileDown, Layers
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
  { value: 'M1', label: '1 Minute (M1)' },
  { value: 'M5', label: '5 Minutes (M5)' },
  { value: 'M15', label: '15 Minutes (M15)' },
  { value: 'H1', label: '1 Hour (H1)' },
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
  
  // Export States
  const [exportSymbol, setExportSymbol] = useState('EURUSD');
  const [exportTimeframe, setExportTimeframe] = useState('H1');
  const [exportStartDate, setExportStartDate] = useState('2024-01-01');
  const [exportEndDate, setExportEndDate] = useState('2024-01-31');
  const [exporting, setExporting] = useState(false);

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

  const loadCoverage = async () => {
    setLoadingCoverage(true);
    try {
      const response = await axios.get(`${API}/marketdata/coverage`);
      if (response.data.success) {
        setCoverage(response.data);
      }
    } catch (error) {
      console.error('Failed to load coverage:', error);
      toast.error('Failed to load coverage data');
    } finally {
      setLoadingCoverage(false);
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

    // Use the first missing range
    const range = missingRanges[0];
    
    setSelectedSymbols([symbol]);
    setDukaTimeframe(timeframe);
    setStartDate(range.start);
    setEndDate(range.end);
    setActiveTab('download');
    
    toast.info(`Ready to download missing data for ${symbol} ${timeframe} from ${range.start} to ${range.end}`);
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
                        <SelectItem value="1h">1 Hour (H1)</SelectItem>
                        <SelectItem value="4h">4 Hours (H4)</SelectItem>
                        <SelectItem value="1d">1 Day (D1)</SelectItem>
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
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-bold flex items-center gap-2">
                  <Layers className="w-5 h-5 text-blue-400" />
                  Data Coverage Overview
                </h2>
                <Button onClick={loadCoverage} disabled={loadingCoverage} variant="outline" size="sm">
                  {loadingCoverage ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                  <span className="ml-2">Refresh</span>
                </Button>
              </div>

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
                      <div className="flex items-center gap-3 mb-4">
                        <TrendingUp className="w-5 h-5 text-emerald-400" />
                        <h3 className="text-lg font-bold font-mono">{symbolData.symbol}</h3>
                        <Badge variant="outline" className="text-xs">
                          {symbolData.timeframes?.length || 0} Timeframes
                        </Badge>
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
