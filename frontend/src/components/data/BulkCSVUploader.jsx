import { useState, useRef, useCallback } from 'react';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { toast } from 'sonner';
import {
  Upload, FileSpreadsheet, CheckCircle2, XCircle, AlertCircle,
  Database, Calendar, BarChart3, Loader2, RefreshCw, Trash2, FolderUp
} from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const SYMBOL_PATTERNS = [
  { pattern: /XAUUSD/i, symbol: 'XAUUSD' },
  { pattern: /EURUSD/i, symbol: 'EURUSD' },
  { pattern: /GBPUSD/i, symbol: 'GBPUSD' },
  { pattern: /USDJPY/i, symbol: 'USDJPY' },
  { pattern: /USDCHF/i, symbol: 'USDCHF' },
  { pattern: /AUDUSD/i, symbol: 'AUDUSD' },
  { pattern: /NZDUSD/i, symbol: 'NZDUSD' },
  { pattern: /USDCAD/i, symbol: 'USDCAD' },
  { pattern: /BTCUSD/i, symbol: 'BTCUSD' },
  { pattern: /ETHUSD/i, symbol: 'ETHUSD' },
];

const TIMEFRAME_PATTERNS = [
  { pattern: /H1|1H|_60|hourly/i, timeframe: '1h' },
  { pattern: /H4|4H|_240/i, timeframe: '4h' },
  { pattern: /D1|1D|daily/i, timeframe: '1d' },
  { pattern: /M1|1M|_1[^0-9]/i, timeframe: '1m' },
  { pattern: /M5|5M|_5[^0-9]/i, timeframe: '5m' },
  { pattern: /M15|15M|_15/i, timeframe: '15m' },
  { pattern: /M30|30M|_30/i, timeframe: '30m' },
];

function detectSymbol(filename) {
  for (const { pattern, symbol } of SYMBOL_PATTERNS) {
    if (pattern.test(filename)) return symbol;
  }
  return null;
}

function detectTimeframe(filename) {
  for (const { pattern, timeframe } of TIMEFRAME_PATTERNS) {
    if (pattern.test(filename)) return timeframe;
  }
  return '1h'; // Default to H1
}

export default function BulkCSVUploader({ onDataLoaded }) {
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [results, setResults] = useState([]);
  const [availableData, setAvailableData] = useState([]);
  const [loadingData, setLoadingData] = useState(false);
  const fileInputRef = useRef(null);

  const loadAvailableData = useCallback(async () => {
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
  }, []);

  const handleFileSelect = (e) => {
    const selectedFiles = Array.from(e.target.files).filter(f => f.name.endsWith('.csv'));
    
    if (selectedFiles.length === 0) {
      toast.error('Please select CSV files');
      return;
    }

    const processedFiles = selectedFiles.map(file => ({
      file,
      name: file.name,
      size: file.size,
      symbol: detectSymbol(file.name) || 'UNKNOWN',
      timeframe: detectTimeframe(file.name),
      status: 'pending',
      result: null
    }));

    setFiles(processedFiles);
    setResults([]);
  };

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    const droppedFiles = Array.from(e.dataTransfer.files).filter(f => f.name.endsWith('.csv'));
    
    if (droppedFiles.length === 0) {
      toast.error('Please drop CSV files');
      return;
    }

    const processedFiles = droppedFiles.map(file => ({
      file,
      name: file.name,
      size: file.size,
      symbol: detectSymbol(file.name) || 'UNKNOWN',
      timeframe: detectTimeframe(file.name),
      status: 'pending',
      result: null
    }));

    setFiles(processedFiles);
    setResults([]);
  }, []);

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
  }, []);

  const updateFileSymbol = (index, symbol) => {
    setFiles(prev => prev.map((f, i) => i === index ? { ...f, symbol } : f));
  };

  const updateFileTimeframe = (index, timeframe) => {
    setFiles(prev => prev.map((f, i) => i === index ? { ...f, timeframe } : f));
  };

  const handleBulkUpload = async () => {
    if (files.length === 0) {
      toast.error('Please select files first');
      return;
    }

    const invalidFiles = files.filter(f => f.symbol === 'UNKNOWN');
    if (invalidFiles.length > 0) {
      toast.error('Please set symbol for all files');
      return;
    }

    setUploading(true);
    setUploadProgress(0);
    const uploadResults = [];

    for (let i = 0; i < files.length; i++) {
      const fileData = files[i];
      setFiles(prev => prev.map((f, idx) => idx === i ? { ...f, status: 'uploading' } : f));

      try {
        const content = await fileData.file.text();
        
        const response = await axios.post(`${API}/marketdata/import/csv`, {
          data: content,
          symbol: fileData.symbol,
          timeframe: fileData.timeframe,
          format_type: 'dukascopy',
          skip_validation: false
        });

        const result = {
          fileName: fileData.name,
          symbol: response.data.symbol,
          timeframe: response.data.timeframe,
          success: true,
          imported: response.data.imported,
          dateRange: response.data.date_range,
          quality: 'OK'
        };

        uploadResults.push(result);
        setFiles(prev => prev.map((f, idx) => idx === i ? { ...f, status: 'success', result } : f));

      } catch (error) {
        const result = {
          fileName: fileData.name,
          symbol: fileData.symbol,
          success: false,
          error: error.response?.data?.detail || error.message
        };

        uploadResults.push(result);
        setFiles(prev => prev.map((f, idx) => idx === i ? { ...f, status: 'error', result } : f));
      }

      setUploadProgress(((i + 1) / files.length) * 100);
    }

    setResults(uploadResults);
    setUploading(false);

    const successCount = uploadResults.filter(r => r.success).length;
    const totalRows = uploadResults.filter(r => r.success).reduce((sum, r) => sum + r.imported, 0);

    if (successCount === files.length) {
      toast.success(`All ${successCount} files uploaded! Total: ${totalRows.toLocaleString()} candles`);
    } else {
      toast.warning(`${successCount}/${files.length} files uploaded. ${totalRows.toLocaleString()} candles total.`);
    }

    loadAvailableData();
    if (onDataLoaded) {
      onDataLoaded(uploadResults);
    }
  };

  const clearFiles = () => {
    setFiles([]);
    setResults([]);
    setUploadProgress(0);
  };

  return (
    <div className="bg-[#0A0A0B] border border-white/10 rounded-lg p-4" data-testid="bulk-csv-uploader">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <FolderUp className="w-4 h-4 text-amber-400" />
          <h3 className="text-sm font-semibold text-white">Bulk Data Import</h3>
        </div>
        <div className="flex gap-2">
          {files.length > 0 && (
            <Button variant="ghost" size="sm" onClick={clearFiles} className="h-7 px-2 text-xs text-zinc-400">
              <Trash2 className="w-3 h-3 mr-1" /> Clear
            </Button>
          )}
          <Button variant="ghost" size="sm" onClick={loadAvailableData} disabled={loadingData} className="h-7 px-2 text-xs">
            <RefreshCw className={`w-3 h-3 mr-1 ${loadingData ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Drop Zone */}
      <div
        onClick={() => fileInputRef.current?.click()}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        className="border-2 border-dashed border-white/20 rounded-lg p-6 text-center cursor-pointer hover:border-amber-500/50 transition-colors mb-4"
        data-testid="drop-zone"
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv"
          multiple
          onChange={handleFileSelect}
          className="hidden"
          data-testid="bulk-file-input"
        />
        <Upload className="w-8 h-8 mx-auto text-zinc-500 mb-2" />
        <p className="text-sm text-zinc-400">Drop multiple CSV files here</p>
        <p className="text-xs text-zinc-600 mt-1">Auto-detects symbol & timeframe from filename</p>
        <p className="text-[10px] text-zinc-700 mt-1">e.g., EURUSD_H1.csv, XAUUSD_60.csv</p>
      </div>

      {/* File List */}
      {files.length > 0 && (
        <div className="space-y-2 mb-4 max-h-60 overflow-y-auto">
          <div className="text-xs text-zinc-500 mb-2">{files.length} file(s) selected</div>
          {files.map((fileData, idx) => (
            <div
              key={idx}
              className={`flex items-center justify-between p-2 rounded bg-[#0F0F10] ${
                fileData.status === 'success' ? 'border border-emerald-500/30' :
                fileData.status === 'error' ? 'border border-red-500/30' :
                fileData.status === 'uploading' ? 'border border-amber-500/30' : ''
              }`}
              data-testid={`file-item-${idx}`}
            >
              <div className="flex items-center gap-2 flex-1 min-w-0">
                {fileData.status === 'success' && <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />}
                {fileData.status === 'error' && <XCircle className="w-4 h-4 text-red-400 flex-shrink-0" />}
                {fileData.status === 'uploading' && <Loader2 className="w-4 h-4 text-amber-400 animate-spin flex-shrink-0" />}
                {fileData.status === 'pending' && <FileSpreadsheet className="w-4 h-4 text-zinc-500 flex-shrink-0" />}
                
                <span className="text-xs text-zinc-300 truncate">{fileData.name}</span>
                <span className="text-[10px] text-zinc-600">({(fileData.size / 1024).toFixed(0)} KB)</span>
              </div>

              <div className="flex items-center gap-2 flex-shrink-0">
                <select
                  value={fileData.symbol}
                  onChange={(e) => updateFileSymbol(idx, e.target.value)}
                  className="h-6 text-[10px] bg-[#18181B] border border-white/10 rounded px-1 text-white"
                  disabled={uploading}
                >
                  <option value="UNKNOWN">Select Symbol</option>
                  {SYMBOL_PATTERNS.map(s => (
                    <option key={s.symbol} value={s.symbol}>{s.symbol}</option>
                  ))}
                </select>

                <select
                  value={fileData.timeframe}
                  onChange={(e) => updateFileTimeframe(idx, e.target.value)}
                  className="h-6 text-[10px] bg-[#18181B] border border-white/10 rounded px-1 text-white"
                  disabled={uploading}
                >
                  {TIMEFRAME_PATTERNS.map(t => (
                    <option key={t.timeframe} value={t.timeframe}>{t.timeframe.toUpperCase()}</option>
                  ))}
                </select>

                {fileData.result?.imported && (
                  <Badge variant="outline" className="text-[9px] px-1 py-0 h-4 border-emerald-500/40 text-emerald-400">
                    {fileData.result.imported.toLocaleString()}
                  </Badge>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Progress Bar */}
      {uploading && (
        <div className="mb-4">
          <Progress value={uploadProgress} className="h-2" />
          <p className="text-[10px] text-zinc-500 mt-1 text-center">{Math.round(uploadProgress)}% complete</p>
        </div>
      )}

      {/* Upload Button */}
      {files.length > 0 && (
        <Button
          onClick={handleBulkUpload}
          disabled={uploading || files.some(f => f.symbol === 'UNKNOWN')}
          className="w-full h-9 bg-amber-600 hover:bg-amber-500 text-black font-semibold mb-4"
          data-testid="bulk-upload-btn"
        >
          {uploading ? (
            <>
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              Uploading {files.filter(f => f.status === 'success').length}/{files.length}...
            </>
          ) : (
            <>
              <Upload className="w-4 h-4 mr-2" />
              Upload All ({files.length} files)
            </>
          )}
        </Button>
      )}

      {/* Results Summary */}
      {results.length > 0 && (
        <div className="bg-[#0F0F10] rounded-lg p-3 mb-4" data-testid="upload-summary">
          <h4 className="text-xs font-medium text-zinc-400 mb-2 flex items-center gap-1.5">
            <BarChart3 className="w-3 h-3" /> Upload Summary
          </h4>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="flex justify-between">
              <span className="text-zinc-500">Total Files:</span>
              <span className="text-white">{results.length}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Successful:</span>
              <span className="text-emerald-400">{results.filter(r => r.success).length}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Total Candles:</span>
              <span className="text-amber-400">{results.filter(r => r.success).reduce((s, r) => s + r.imported, 0).toLocaleString()}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Failed:</span>
              <span className="text-red-400">{results.filter(r => !r.success).length}</span>
            </div>
          </div>
          
          {/* Per-file details */}
          <div className="mt-3 space-y-1.5 max-h-32 overflow-y-auto">
            {results.filter(r => r.success).map((r, idx) => (
              <div key={idx} className="flex items-center justify-between text-[10px]">
                <span className="text-zinc-400">{r.symbol} {r.timeframe?.toUpperCase()}</span>
                <span className="text-zinc-300">
                  {r.imported.toLocaleString()} candles • {r.dateRange?.days || 0} days
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Available Data */}
      <div className="border-t border-white/10 pt-3">
        <h4 className="text-xs font-medium text-zinc-400 mb-2 flex items-center gap-1.5">
          <Database className="w-3 h-3" /> Loaded Market Data
        </h4>
        
        {loadingData ? (
          <div className="flex items-center justify-center py-4">
            <Loader2 className="w-4 h-4 animate-spin text-zinc-500" />
          </div>
        ) : availableData.length === 0 ? (
          <div className="text-center py-4 text-xs text-zinc-600">
            No data loaded. Upload CSV files to get started.
          </div>
        ) : (
          <div className="space-y-1.5">
            {availableData.map((item, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between bg-[#0F0F10] rounded px-2 py-1.5"
                data-testid={`available-data-${item.symbol}`}
              >
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-4 border-amber-500/40 text-amber-400">
                    {item.symbol}
                  </Badge>
                  <span className="text-xs text-zinc-500">
                    {item.timeframes?.join(', ').toUpperCase() || 'No data'}
                  </span>
                </div>
                {item.total_candles && (
                  <span className="text-[10px] text-zinc-600">{item.total_candles?.toLocaleString()} candles</span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
