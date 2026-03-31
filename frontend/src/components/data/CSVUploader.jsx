import { useState, useRef } from 'react';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { toast } from 'sonner';
import {
  Upload, FileSpreadsheet, CheckCircle2, XCircle, AlertCircle,
  Database, Calendar, BarChart3, Loader2, RefreshCw, Trash2
} from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const SYMBOLS = [
  { value: 'EURUSD', label: 'EUR/USD' },
  { value: 'GBPUSD', label: 'GBP/USD' },
  { value: 'USDJPY', label: 'USD/JPY' },
  { value: 'XAUUSD', label: 'XAU/USD (Gold)' },
  { value: 'USDCHF', label: 'USD/CHF' },
  { value: 'AUDUSD', label: 'AUD/USD' },
  { value: 'NZDUSD', label: 'NZD/USD' },
  { value: 'USDCAD', label: 'USD/CAD' },
];

const TIMEFRAMES = [
  { value: '1m', label: '1 Minute' },
  { value: '5m', label: '5 Minutes' },
  { value: '15m', label: '15 Minutes' },
  { value: '30m', label: '30 Minutes' },
  { value: '1h', label: '1 Hour' },
  { value: '4h', label: '4 Hours' },
  { value: '1d', label: 'Daily' },
];

const CSV_FORMATS = [
  { value: 'dukascopy', label: 'Dukascopy' },
  { value: 'mt4', label: 'MetaTrader 4' },
  { value: 'mt5', label: 'MetaTrader 5' },
  { value: 'ctrader', label: 'cTrader' },
  { value: 'custom', label: 'Custom (OHLCV)' },
];

export default function CSVUploader({ onDataLoaded }) {
  const [file, setFile] = useState(null);
  const [symbol, setSymbol] = useState('EURUSD');
  const [timeframe, setTimeframe] = useState('1h');
  const [format, setFormat] = useState('dukascopy');
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);
  const [availableData, setAvailableData] = useState([]);
  const [loadingData, setLoadingData] = useState(false);
  const fileInputRef = useRef(null);

  // Load available data on mount
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

  const handleFileSelect = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      if (!selectedFile.name.endsWith('.csv')) {
        toast.error('Please select a CSV file');
        return;
      }
      setFile(selectedFile);
      setUploadResult(null);
      
      // Try to auto-detect symbol from filename
      const filename = selectedFile.name.toUpperCase();
      for (const sym of SYMBOLS) {
        if (filename.includes(sym.value)) {
          setSymbol(sym.value);
          break;
        }
      }
    }
  };

  const handleUpload = async () => {
    if (!file) {
      toast.error('Please select a CSV file first');
      return;
    }

    setUploading(true);
    setUploadResult(null);

    try {
      const fileContent = await file.text();
      
      const response = await axios.post(`${API}/marketdata/import/csv`, {
        data: fileContent,
        symbol: symbol,
        timeframe: timeframe,
        format_type: format,
        skip_validation: false
      });

      if (response.data.success) {
        const result = {
          success: true,
          fileName: file.name,
          symbol: response.data.symbol,
          timeframe: response.data.timeframe,
          rowsLoaded: response.data.imported,
          skipped: response.data.skipped,
          updated: response.data.updated,
          totalProcessed: response.data.total_processed,
        };
        
        setUploadResult(result);
        toast.success(`Loaded ${result.rowsLoaded} candles for ${symbol} ${timeframe}`);
        
        // Refresh available data
        loadAvailableData();
        
        // Notify parent
        if (onDataLoaded) {
          onDataLoaded(result);
        }
      }
    } catch (error) {
      const errorMsg = error.response?.data?.detail || error.message;
      setUploadResult({
        success: false,
        error: errorMsg
      });
      toast.error(`Upload failed: ${errorMsg}`);
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteData = async (sym, tf) => {
    try {
      await axios.delete(`${API}/marketdata/${sym}?timeframe=${tf}`);
      toast.success(`Deleted ${sym} ${tf} data`);
      loadAvailableData();
    } catch (error) {
      toast.error('Failed to delete data');
    }
  };

  return (
    <div className="bg-[#0A0A0B] border border-white/10 rounded-lg p-4" data-testid="csv-uploader">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Database className="w-4 h-4 text-amber-400" />
          <h3 className="text-sm font-semibold text-white">Market Data</h3>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={loadAvailableData}
          disabled={loadingData}
          className="h-7 px-2 text-xs"
        >
          <RefreshCw className={`w-3 h-3 mr-1 ${loadingData ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {/* Upload Section */}
      <div className="space-y-3 mb-4">
        {/* File Input */}
        <div
          onClick={() => fileInputRef.current?.click()}
          className="border border-dashed border-white/20 rounded-lg p-4 text-center cursor-pointer hover:border-amber-500/50 transition-colors"
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv"
            onChange={handleFileSelect}
            className="hidden"
            data-testid="csv-file-input"
          />
          {file ? (
            <div className="flex items-center justify-center gap-2">
              <FileSpreadsheet className="w-5 h-5 text-amber-400" />
              <span className="text-sm text-white">{file.name}</span>
              <span className="text-xs text-zinc-500">({(file.size / 1024).toFixed(1)} KB)</span>
            </div>
          ) : (
            <div className="space-y-1">
              <Upload className="w-6 h-6 mx-auto text-zinc-500" />
              <p className="text-xs text-zinc-500">Click to upload CSV file</p>
              <p className="text-[10px] text-zinc-600">Supports Dukascopy, MT4, MT5, cTrader formats</p>
            </div>
          )}
        </div>

        {/* Config Row */}
        <div className="grid grid-cols-3 gap-2">
          <Select value={symbol} onValueChange={setSymbol}>
            <SelectTrigger className="h-8 text-xs bg-[#0F0F10] border-white/10" data-testid="symbol-select">
              <SelectValue placeholder="Symbol" />
            </SelectTrigger>
            <SelectContent>
              {SYMBOLS.map(s => (
                <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={timeframe} onValueChange={setTimeframe}>
            <SelectTrigger className="h-8 text-xs bg-[#0F0F10] border-white/10" data-testid="timeframe-select">
              <SelectValue placeholder="Timeframe" />
            </SelectTrigger>
            <SelectContent>
              {TIMEFRAMES.map(t => (
                <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={format} onValueChange={setFormat}>
            <SelectTrigger className="h-8 text-xs bg-[#0F0F10] border-white/10" data-testid="format-select">
              <SelectValue placeholder="Format" />
            </SelectTrigger>
            <SelectContent>
              {CSV_FORMATS.map(f => (
                <SelectItem key={f.value} value={f.value}>{f.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Upload Button */}
        <Button
          onClick={handleUpload}
          disabled={!file || uploading}
          className="w-full h-9 bg-amber-600 hover:bg-amber-500 text-black font-semibold"
          data-testid="upload-btn"
        >
          {uploading ? (
            <>
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              Uploading...
            </>
          ) : (
            <>
              <Upload className="w-4 h-4 mr-2" />
              Upload & Validate Data
            </>
          )}
        </Button>
      </div>

      {/* Upload Result */}
      {uploadResult && (
        <div
          className={`p-3 rounded-lg mb-4 ${
            uploadResult.success
              ? 'bg-emerald-500/10 border border-emerald-500/30'
              : 'bg-red-500/10 border border-red-500/30'
          }`}
          data-testid="upload-result"
        >
          {uploadResult.success ? (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                <span className="text-sm font-medium text-emerald-400">Upload Successful</span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="flex items-center gap-1.5">
                  <FileSpreadsheet className="w-3 h-3 text-zinc-500" />
                  <span className="text-zinc-400">{uploadResult.fileName}</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <BarChart3 className="w-3 h-3 text-zinc-500" />
                  <span className="text-zinc-400">{uploadResult.rowsLoaded.toLocaleString()} candles</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <Database className="w-3 h-3 text-zinc-500" />
                  <span className="text-zinc-400">{uploadResult.symbol} / {uploadResult.timeframe}</span>
                </div>
                {uploadResult.skipped > 0 && (
                  <div className="flex items-center gap-1.5">
                    <AlertCircle className="w-3 h-3 text-amber-500" />
                    <span className="text-amber-400">{uploadResult.skipped} skipped</span>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <XCircle className="w-4 h-4 text-red-400" />
              <span className="text-sm text-red-400">{uploadResult.error}</span>
            </div>
          )}
        </div>
      )}

      {/* Available Data */}
      <div className="border-t border-white/10 pt-3">
        <h4 className="text-xs font-medium text-zinc-400 mb-2 flex items-center gap-1.5">
          <Database className="w-3 h-3" />
          Available Market Data
        </h4>
        
        {loadingData ? (
          <div className="flex items-center justify-center py-4">
            <Loader2 className="w-4 h-4 animate-spin text-zinc-500" />
          </div>
        ) : availableData.length === 0 ? (
          <div className="text-center py-4 text-xs text-zinc-600">
            No data loaded. Upload CSV to get started.
          </div>
        ) : (
          <div className="space-y-1.5 max-h-40 overflow-y-auto">
            {availableData.map((item, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between bg-[#0F0F10] rounded px-2 py-1.5 group"
                data-testid={`data-item-${item.symbol}`}
              >
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-4 border-amber-500/40 text-amber-400">
                    {item.symbol}
                  </Badge>
                  <span className="text-xs text-zinc-500">
                    {item.timeframes?.join(', ') || 'No data'}
                  </span>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleDeleteData(item.symbol, item.timeframes?.[0])}
                  className="h-5 w-5 p-0 opacity-0 group-hover:opacity-100 text-red-400 hover:text-red-300"
                >
                  <Trash2 className="w-3 h-3" />
                </Button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
