import { useState, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Card } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { toast } from 'sonner';
import {
  Upload, Database, CheckCircle2, XCircle, AlertCircle, TrendingUp,
  Calendar, FileText, ArrowLeft, Loader2, FileSpreadsheet, BarChart3,
  Download, Activity, AlertTriangle
} from 'lucide-react';

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
  const [startDate, setStartDate] = useState('2024-01-01');
  const [endDate, setEndDate] = useState('2024-01-31');
  const [downloading, setDownloading] = useState(false);
  const [downloadTaskId, setDownloadTaskId] = useState(null);
  const [downloadProgress, setDownloadProgress] = useState(0);
  const [downloadMessage, setDownloadMessage] = useState('');
  const [downloadResults, setDownloadResults] = useState(null);
  
  // Available Data
  const [availableData, setAvailableData] = useState([]);
  const [loadingData, setLoadingData] = useState(false);

  useEffect(() => {
    loadAvailableData();
  }, []);

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
              loadAvailableData();
              clearInterval(interval);
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
  }, [downloadTaskId, downloading]);

  const loadAvailableData = async () => {
    setLoadingData(true);
    try {
      const response = await axios.get(`${API}/marketdata/available`);
      if (response.data.success) {
        setAvailableData(response.data.symbols || []);
      }
    } catch (error) {
      console.error('Failed to load available data:', error);
    } finally {
      setLoadingData(false);
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

  // CSV Upload functions (keeping existing ones)
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
        loadAvailableData();
        setSelectedFile(null);
      }
    } catch (error) {
      const errorMsg = error.response?.data?.detail || error.message;
      toast.error(`Upload failed: ${errorMsg}`);
      setUploadResult({ success: false, error: errorMsg });
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0A0A0B] text-white">
      {/* Header */}
      <div className="border-b border-white/10 bg-[#0F0F10]/50 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button
                onClick={() => navigate('/')}
                variant="ghost"
                size="sm"
                className="text-zinc-400 hover:text-white"
              >
                <ArrowLeft className="w-4 h-4 mr-2" />
                Back to Dashboard
              </Button>
              <div className="w-px h-6 bg-white/10" />
              <div className="flex items-center gap-3">
                <Database className="w-6 h-6 text-blue-400" />
                <div>
                  <h1 className="text-xl font-bold">Market Data Management</h1>
                  <p className="text-xs text-zinc-500">Dukascopy data download & CSV upload</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-8">
        {/* Dukascopy Download Section */}
        <div className="mb-8">
          <Card className="bg-[#0F0F10] border-white/10 p-6">
            <h2 className="text-lg font-bold mb-6 flex items-center gap-2">
              <Download className="w-5 h-5 text-blue-400" />
              Dukascopy Data Download
            </h2>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Left: Configuration */}
              <div className="space-y-4">
                {/* Symbol Selection */}
                <div>
                  <label className="text-xs text-zinc-400 uppercase tracking-wider mb-3 block">
                    Select Symbols (Multi-select)
                  </label>
                  <div className="space-y-2">
                    {SYMBOLS.map(sym => (
                      <div key={sym.value} className="flex items-center gap-3 p-3 bg-[#18181B] rounded-md border border-white/5 hover:border-white/10 transition-colors">
                        <Checkbox
                          checked={selectedSymbols.includes(sym.value)}
                          onCheckedChange={() => toggleSymbol(sym.value)}
                          disabled={!sym.enabled}
                          data-testid={`symbol-checkbox-${sym.value}`}
                        />
                        <label className="text-sm cursor-pointer flex-1">
                          {sym.label}
                        </label>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Date Range */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-zinc-400 uppercase tracking-wider mb-2 block">
                      Start Date
                    </label>
                    <input
                      type="date"
                      value={startDate}
                      onChange={(e) => setStartDate(e.target.value)}
                      className="w-full bg-[#18181B] border border-white/10 rounded-md px-3 py-2 text-sm"
                      data-testid="start-date-input"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-zinc-400 uppercase tracking-wider mb-2 block">
                      End Date
                    </label>
                    <input
                      type="date"
                      value={endDate}
                      onChange={(e) => setEndDate(e.target.value)}
                      className="w-full bg-[#18181B] border border-white/10 rounded-md px-3 py-2 text-sm"
                      data-testid="end-date-input"
                    />
                  </div>
                </div>

                {/* Timeframe */}
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

                {/* Download Button */}
                <Button
                  onClick={startDukascopyDownload}
                  disabled={downloading || selectedSymbols.length === 0}
                  className="w-full bg-blue-600 hover:bg-blue-700 h-12 text-base font-bold"
                  data-testid="download-prepare-button"
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
                    <div className="flex items-start gap-3">
                      <Activity className="w-5 h-5 text-blue-400 mt-0.5 animate-pulse" />
                      <div className="flex-1">
                        <p className="text-sm font-mono text-blue-400 mb-2">{downloadMessage}</p>
                        <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-blue-500 transition-all duration-300"
                            style={{ width: `${downloadProgress}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Right: Results */}
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
                        
                        {result.error ? (
                          <p className="text-xs text-red-400">{result.error}</p>
                        ) : (
                          <div className="space-y-2 text-xs">
                            <div className="flex justify-between">
                              <span className="text-zinc-500">Total Candles:</span>
                              <span className="text-white font-mono">{result.total_candles}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-zinc-500">Original:</span>
                              <span className="text-emerald-400 font-mono">{result.original_candles}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-zinc-500">Filled:</span>
                              <span className="text-yellow-400 font-mono">{result.filled_candles}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-zinc-500">Large Gaps:</span>
                              <span className={`font-mono ${result.large_gaps > 0 ? 'text-red-400' : 'text-emerald-400'}`}>
                                {result.large_gaps}
                              </span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-zinc-500">Quality Score:</span>
                              <span className="text-blue-400 font-mono">{result.data_quality_score}/100</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-zinc-500">Date Range:</span>
                              <span className="text-zinc-400 font-mono text-[10px]">
                                {result.date_range_start?.split('T')[0]} to {result.date_range_end?.split('T')[0]}
                              </span>
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
        </div>

        {/* Available Data Section */}
        <div className="mb-8">
          <Card className="bg-[#0F0F10] border-white/10 p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold flex items-center gap-2">
                <BarChart3 className="w-5 h-5 text-emerald-400" />
                Available Market Data
              </h2>
              <Button onClick={loadAvailableData} variant="outline" size="sm" disabled={loadingData}>
                {loadingData ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Refresh'}
              </Button>
            </div>

            {loadingData ? (
              <div className="text-center py-12">
                <Loader2 className="w-8 h-8 animate-spin mx-auto text-blue-400 mb-3" />
                <p className="text-sm text-zinc-500">Loading data...</p>
              </div>
            ) : availableData.length === 0 ? (
              <div className="text-center py-12 border-2 border-dashed border-white/10 rounded-lg">
                <Database className="w-12 h-12 mx-auto text-zinc-600 mb-3" />
                <p className="text-sm text-zinc-500">No market data uploaded yet</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {availableData.map((symbolData, idx) => (
                  <div key={idx} className="bg-[#18181B] border border-white/10 rounded-lg p-4">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <TrendingUp className="w-4 h-4 text-emerald-400" />
                        <span className="font-mono text-white font-bold">{symbolData.symbol}</span>
                      </div>
                      <Badge variant="outline" className="text-xs border-emerald-500/40 text-emerald-400">
                        Active
                      </Badge>
                    </div>
                    
                    {symbolData.timeframes && symbolData.timeframes.length > 0 && (
                      <div>
                        <p className="text-xs text-zinc-500 mb-2">Timeframes:</p>
                        <div className="flex flex-wrap gap-1">
                          {symbolData.timeframes.map((tf, i) => (
                            <Badge key={i} variant="secondary" className="text-xs font-mono">
                              {tf}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
