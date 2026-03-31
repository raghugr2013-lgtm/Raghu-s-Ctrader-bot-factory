import { useState, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Card } from '@/components/ui/card';
import { toast } from 'sonner';
import {
  Upload, Database, CheckCircle2, XCircle, AlertCircle, TrendingUp,
  Calendar, FileText, ArrowLeft, Loader2, FileSpreadsheet, BarChart3
} from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const SYMBOLS = [
  { value: 'EURUSD', label: 'EUR/USD' },
  { value: 'XAUUSD', label: 'XAU/USD (Gold)' },
  { value: 'GBPUSD', label: 'GBP/USD' },
  { value: 'USDJPY', label: 'USD/JPY' },
  { value: 'BTCUSD', label: 'BTC/USD' },
];

const TIMEFRAMES = [
  { value: '1h', label: '1 Hour (H1)' },
  { value: '4h', label: '4 Hours (H4)' },
  { value: '1d', label: '1 Day (D1)' },
  { value: '15m', label: '15 Minutes (M15)' },
  { value: '30m', label: '30 Minutes (M30)' },
];

const CSV_FORMATS = [
  { value: 'mt4', label: 'MetaTrader 4 (MT4)' },
  { value: 'mt5', label: 'MetaTrader 5 (MT5)' },
  { value: 'ctrader', label: 'cTrader' },
  { value: 'custom', label: 'Dukascopy / Custom CSV' },
];

export default function MarketDataPage() {
  const navigate = useNavigate();
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [symbol, setSymbol] = useState('EURUSD');
  const [timeframe, setTimeframe] = useState('1h');
  const [csvFormat, setCsvFormat] = useState('custom');
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);
  const [availableData, setAvailableData] = useState([]);
  const [loadingData, setLoadingData] = useState(false);

  // Load available market data on mount
  useEffect(() => {
    loadAvailableData();
  }, []);

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
      // Read file content
      const fileContent = await selectedFile.text();

      // Prepare request
      const requestData = {
        symbol: symbol,
        timeframe: timeframe,
        format_type: csvFormat,
        data: fileContent,
        skip_validation: false
      };

      toast.info('Uploading CSV data...');

      // Upload to backend
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

        toast.success(`✅ Uploaded ${response.data.imported} candles for ${response.data.symbol} ${response.data.timeframe}`);
        
        // Refresh available data
        loadAvailableData();
        
        // Clear selected file
        setSelectedFile(null);
      } else {
        throw new Error('Upload failed');
      }
    } catch (error) {
      console.error('Upload error:', error);
      const errorMsg = error.response?.data?.detail || error.message || 'Upload failed';
      toast.error(`Upload failed: ${errorMsg}`);
      setUploadResult({
        success: false,
        error: errorMsg
      });
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
                  <p className="text-xs text-zinc-500">Upload Dukascopy CSV files for real backtesting</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          
          {/* Upload Section */}
          <div className="space-y-6">
            <Card className="bg-[#0F0F10] border-white/10 p-6">
              <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
                <Upload className="w-5 h-5 text-blue-400" />
                Upload CSV Data
              </h2>

              {/* File Selection */}
              <div className="space-y-4">
                {/* Symbol Selection */}
                <div>
                  <label className="text-xs text-zinc-400 uppercase tracking-wider mb-2 block">Symbol</label>
                  <Select value={symbol} onValueChange={setSymbol}>
                    <SelectTrigger className="bg-[#18181B] border-white/10" data-testid="symbol-select">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {SYMBOLS.map(s => (
                        <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* Timeframe Selection */}
                <div>
                  <label className="text-xs text-zinc-400 uppercase tracking-wider mb-2 block">Timeframe</label>
                  <Select value={timeframe} onValueChange={setTimeframe}>
                    <SelectTrigger className="bg-[#18181B] border-white/10" data-testid="timeframe-select">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {TIMEFRAMES.map(tf => (
                        <SelectItem key={tf.value} value={tf.value}>{tf.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* CSV Format Selection */}
                <div>
                  <label className="text-xs text-zinc-400 uppercase tracking-wider mb-2 block">CSV Format</label>
                  <Select value={csvFormat} onValueChange={setCsvFormat}>
                    <SelectTrigger className="bg-[#18181B] border-white/10" data-testid="format-select">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {CSV_FORMATS.map(fmt => (
                        <SelectItem key={fmt.value} value={fmt.value}>{fmt.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* Drag & Drop Zone */}
                <div
                  className={`border-2 border-dashed rounded-lg p-8 text-center transition-all ${
                    dragActive 
                      ? 'border-blue-500 bg-blue-500/10' 
                      : 'border-white/20 bg-[#18181B] hover:border-white/30'
                  }`}
                  onDragEnter={handleDrag}
                  onDragLeave={handleDrag}
                  onDragOver={handleDrag}
                  onDrop={handleDrop}
                  data-testid="csv-drop-zone"
                >
                  <input
                    type="file"
                    id="csv-file-input"
                    accept=".csv"
                    onChange={handleFileInput}
                    className="hidden"
                  />
                  
                  {selectedFile ? (
                    <div className="space-y-3">
                      <FileSpreadsheet className="w-12 h-12 mx-auto text-emerald-400" />
                      <div>
                        <p className="text-sm font-mono text-white">{selectedFile.name}</p>
                        <p className="text-xs text-zinc-500">{(selectedFile.size / 1024).toFixed(2)} KB</p>
                      </div>
                      <Button
                        onClick={() => setSelectedFile(null)}
                        variant="outline"
                        size="sm"
                        className="text-xs"
                      >
                        Remove
                      </Button>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      <Upload className="w-12 h-12 mx-auto text-zinc-500" />
                      <div>
                        <p className="text-sm text-zinc-300 mb-1">
                          Drag & drop CSV file here
                        </p>
                        <p className="text-xs text-zinc-500 mb-3">or</p>
                        <label
                          htmlFor="csv-file-input"
                          className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-md cursor-pointer transition-colors"
                        >
                          <FileText className="w-4 h-4" />
                          Browse Files
                        </label>
                      </div>
                    </div>
                  )}
                </div>

                {/* Upload Button */}
                <Button
                  onClick={uploadCSV}
                  disabled={!selectedFile || uploading}
                  className="w-full bg-blue-600 hover:bg-blue-700"
                  data-testid="upload-csv-button"
                >
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

                {/* Upload Result */}
                {uploadResult && (
                  <div className={`p-4 rounded-md border ${
                    uploadResult.success 
                      ? 'bg-emerald-500/10 border-emerald-500/30' 
                      : 'bg-red-500/10 border-red-500/30'
                  }`}>
                    <div className="flex items-start gap-3">
                      {uploadResult.success ? (
                        <CheckCircle2 className="w-5 h-5 text-emerald-400 mt-0.5" />
                      ) : (
                        <XCircle className="w-5 h-5 text-red-400 mt-0.5" />
                      )}
                      <div className="flex-1 text-sm">
                        {uploadResult.success ? (
                          <>
                            <p className="font-bold text-emerald-400 mb-2">Upload Successful!</p>
                            <div className="space-y-1 text-xs text-zinc-300">
                              <p>Symbol: <span className="font-mono text-white">{uploadResult.symbol}</span></p>
                              <p>Timeframe: <span className="font-mono text-white">{uploadResult.timeframe}</span></p>
                              <p>Candles Imported: <span className="font-mono text-emerald-400">{uploadResult.imported}</span></p>
                              {uploadResult.skipped > 0 && (
                                <p>Skipped (duplicates): <span className="font-mono text-yellow-400">{uploadResult.skipped}</span></p>
                              )}
                              <p>Total Processed: <span className="font-mono text-white">{uploadResult.total}</span></p>
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
            </Card>

            {/* Info Card */}
            <Card className="bg-[#0F0F10] border-blue-500/30 p-6">
              <div className="flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-blue-400 mt-0.5" />
                <div className="text-sm space-y-2">
                  <p className="font-bold text-blue-400">Dukascopy CSV Format</p>
                  <p className="text-zinc-400 text-xs">
                    Upload historical OHLCV data from Dukascopy or other sources.
                    Supported formats: MT4, MT5, cTrader, Dukascopy, and custom CSV.
                  </p>
                  <div className="pt-2 space-y-1 text-xs text-zinc-500">
                    <p>• File must be in CSV format</p>
                    <p>• Must contain: timestamp, open, high, low, close, volume</p>
                    <p>• Data will be validated before storage</p>
                    <p>• Backtests will use ONLY uploaded real data</p>
                  </div>
                </div>
              </div>
            </Card>
          </div>

          {/* Available Data Section */}
          <div className="space-y-6">
            <Card className="bg-[#0F0F10] border-white/10 p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-bold flex items-center gap-2">
                  <BarChart3 className="w-5 h-5 text-emerald-400" />
                  Available Market Data
                </h2>
                <Button
                  onClick={loadAvailableData}
                  variant="outline"
                  size="sm"
                  disabled={loadingData}
                  data-testid="refresh-data-button"
                >
                  {loadingData ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    'Refresh'
                  )}
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
                  <p className="text-sm text-zinc-500 mb-1">No market data uploaded yet</p>
                  <p className="text-xs text-zinc-600">Upload CSV files to enable real backtesting</p>
                </div>
              ) : (
                <div className="space-y-3">
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
                      
                      <div className="space-y-2">
                        {symbolData.timeframes && symbolData.timeframes.length > 0 ? (
                          <div>
                            <p className="text-xs text-zinc-500 mb-2">Available Timeframes:</p>
                            <div className="flex flex-wrap gap-2">
                              {symbolData.timeframes.map((tf, i) => (
                                <Badge key={i} variant="secondary" className="text-xs font-mono">
                                  {tf}
                                </Badge>
                              ))}
                            </div>
                          </div>
                        ) : (
                          <p className="text-xs text-zinc-500">No timeframe data</p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            {/* Stats Card */}
            <Card className="bg-[#0F0F10] border-white/10 p-6">
              <h3 className="text-sm font-bold mb-4 flex items-center gap-2">
                <Calendar className="w-4 h-4 text-zinc-400" />
                Data Statistics
              </h3>
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-[#18181B] p-3 rounded-md">
                  <p className="text-xs text-zinc-500 mb-1">Total Symbols</p>
                  <p className="text-2xl font-bold text-white">{availableData.length}</p>
                </div>
                <div className="bg-[#18181B] p-3 rounded-md">
                  <p className="text-xs text-zinc-500 mb-1">Total Timeframes</p>
                  <p className="text-2xl font-bold text-white">
                    {availableData.reduce((acc, s) => acc + (s.timeframes?.length || 0), 0)}
                  </p>
                </div>
              </div>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
