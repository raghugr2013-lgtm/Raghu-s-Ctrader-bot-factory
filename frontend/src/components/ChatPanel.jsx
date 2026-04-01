import { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { ScrollArea } from '@/components/ui/scroll-area';
import { toast } from 'sonner';
import { 
  Send, 
  Paperclip, 
  Image as ImageIcon, 
  FileCode, 
  FileText, 
  Loader2,
  Bot,
  User,
  X,
  CheckCircle
} from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function ChatPanel({ currentCode, onCodeUpdate, sessionId }) {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [selectedModel, setSelectedModel] = useState('openai');
  const [isSending, setIsSending] = useState(false);
  const [uploadedFile, setUploadedFile] = useState(null);
  const [filePreview, setFilePreview] = useState(null);
  const fileInputRef = useRef(null);
  const messagesEndRef = useRef(null);

  // Load chat history on mount
  useEffect(() => {
    if (sessionId) {
      loadChatHistory();
    }
  }, [sessionId]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const loadChatHistory = async () => {
    try {
      const response = await axios.get(`${API}/chat/history/${sessionId}`);
      if (response.data.success) {
        setMessages(response.data.messages);
      }
    } catch (error) {
      console.error('Failed to load chat history:', error);
    }
  };

  const handleSendMessage = async () => {
    if (!inputMessage.trim() && !uploadedFile) {
      toast.error('Please enter a message or upload a file');
      return;
    }

    setIsSending(true);

    try {
      if (uploadedFile) {
        // Send with file attachment
        const formData = new FormData();
        formData.append('file', uploadedFile);
        formData.append('session_id', sessionId);
        formData.append('ai_model', selectedModel);
        formData.append('message', inputMessage || 'Please analyze this file');

        const response = await axios.post(`${API}/chat/upload/file`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        });

        if (response.data.success) {
          // Add messages to UI
          setMessages(prev => [
            ...prev,
            {
              role: 'user',
              content: inputMessage || 'Uploaded file',
              file_attachment: { filename: uploadedFile.name },
              timestamp: new Date().toISOString()
            },
            {
              role: 'assistant',
              content: response.data.message,
              timestamp: new Date().toISOString()
            }
          ]);

          toast.success('File analyzed successfully');
        }
      } else {
        // Send regular message
        const response = await axios.post(`${API}/chat/send`, {
          message: inputMessage,
          ai_model: selectedModel,
          session_id: sessionId,
          context: currentCode !== '// Your generated cBot code will appear here...' ? currentCode : null
        });

        if (response.data.success) {
          setMessages(prev => [
            ...prev,
            {
              role: 'user',
              content: inputMessage,
              timestamp: new Date().toISOString()
            },
            {
              role: 'assistant',
              content: response.data.message,
              timestamp: new Date().toISOString()
            }
          ]);

          // Check if response contains code that should update editor
          if (response.data.message.includes('```csharp') || response.data.message.includes('```cs')) {
            const codeMatch = response.data.message.match(/```(?:csharp|cs)\n([\s\S]*?)```/);
            if (codeMatch && codeMatch[1]) {
              toast.success('Code suggestion available - check message');
            }
          }
        }
      }

      // Clear input and file
      setInputMessage('');
      setUploadedFile(null);
      setFilePreview(null);
      
    } catch (error) {
      console.error('Chat error:', error);
      toast.error('Failed to send message');
    } finally {
      setIsSending(false);
    }
  };

  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    // Check file size (10MB max)
    if (file.size > 10 * 1024 * 1024) {
      toast.error('File size must be less than 10MB');
      return;
    }

    // Check file type
    const allowedTypes = [
      'text/plain', 'text/csv', 'application/json',
      'application/pdf', 'image/png', 'image/jpeg', 'image/webp'
    ];
    const allowedExtensions = ['.cs', '.algo', '.csbots', '.txt', '.csv', '.json', '.pdf', '.png', '.jpg', '.jpeg', '.webp'];
    
    const fileExt = '.' + file.name.split('.').pop().toLowerCase();
    if (!allowedTypes.includes(file.type) && !allowedExtensions.includes(fileExt)) {
      toast.error('File type not supported');
      return;
    }

    setUploadedFile(file);

    // Create preview
    if (file.type.startsWith('image/')) {
      const reader = new FileReader();
      reader.onload = (e) => setFilePreview(e.target.result);
      reader.readAsDataURL(file);
    } else {
      setFilePreview(null);
    }

    toast.success(`File selected: ${file.name}`);
  };

  const handleApplyCode = (code) => {
    if (onCodeUpdate) {
      onCodeUpdate(code);
      toast.success('Code applied to editor');
    }
  };

  const extractCodeFromMessage = (content) => {
    const codeMatch = content.match(/```(?:csharp|cs)\n([\s\S]*?)```/);
    return codeMatch ? codeMatch[1] : null;
  };

  const formatTimestamp = (timestamp) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString();
  };

  const renderMessageContent = (message) => {
    const code = extractCodeFromMessage(message.content);
    
    if (code) {
      return (
        <div>
          {message.content.split('```')[0] && (
            <p className=\"text-sm text-zinc-300 mb-2 whitespace-pre-wrap\">{message.content.split('```')[0]}</p>
          )}
          <div className=\"bg-black border border-white/10 rounded-sm p-2 my-2\">
            <div className=\"flex items-center justify-between mb-1\">
              <span className=\"text-[10px] text-zinc-500 uppercase font-mono\">C# Code</span>
              <Button
                size=\"sm\"
                onClick={() => handleApplyCode(code)}
                className=\"h-6 px-2 text-[10px] bg-blue-600 hover:bg-blue-500\"
              >
                <CheckCircle className=\"w-3 h-3 mr-1\" />
                Apply to Editor
              </Button>
            </div>
            <pre className=\"text-xs text-emerald-400 font-mono overflow-x-auto max-h-64\">{code}</pre>
          </div>
          {message.content.split('```').slice(2).join('```') && (
            <p className=\"text-sm text-zinc-300 mt-2 whitespace-pre-wrap\">
              {message.content.split('```').slice(2).join('```')}
            </p>
          )}
        </div>
      );
    }

    return <p className=\"text-sm text-zinc-300 whitespace-pre-wrap\">{message.content}</p>;
  };

  return (
    <div className=\"flex flex-col h-full bg-[#0A0A0A] border border-white/5\">
      {/* Header */}
      <div className=\"border-b border-white/5 px-3 py-2 bg-[#18181B]\">
        <h2 className=\"text-sm font-bold uppercase tracking-wider text-zinc-200\" style={{ fontFamily: 'Barlow Condensed, sans-serif' }}>
          AI Trading Chat
        </h2>
        <div className=\"mt-2\">
          <Select value={selectedModel} onValueChange={setSelectedModel}>
            <SelectTrigger className=\"bg-black border-white/10 text-xs text-zinc-300 h-7\" data-testid=\"chat-model-selector\">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className=\"bg-[#0F0F10] border-white/10\">
              <SelectItem value=\"openai\" className=\"text-xs\">GPT-5.2</SelectItem>
              <SelectItem value=\"claude\" className=\"text-xs\">Claude Sonnet</SelectItem>
              <SelectItem value=\"deepseek\" className=\"text-xs\">DeepSeek</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Messages */}
      <ScrollArea className=\"flex-1 p-3 space-y-3\">
        {messages.length === 0 ? (
          <div className=\"flex flex-col items-center justify-center h-full text-center\">
            <Bot className=\"w-12 h-12 text-zinc-700 mb-3\" />
            <p className=\"text-sm text-zinc-500 font-mono\">Start a conversation</p>
            <p className=\"text-xs text-zinc-600 mt-1\">Ask about code, upload files, or get trading advice</p>
          </div>
        ) : (
          messages.map((msg, idx) => (
            <div key={idx} className={`flex gap-2 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              {msg.role === 'assistant' && (
                <div className=\"flex-shrink-0 w-6 h-6 rounded-full bg-blue-600 flex items-center justify-center\">
                  <Bot className=\"w-4 h-4 text-white\" />
                </div>
              )}
              <div className={`max-w-[85%] ${msg.role === 'user' ? 'bg-blue-900/30 border-blue-800/50' : 'bg-[#0F0F10] border-white/10'} border rounded-sm p-2`}>
                {msg.file_attachment && (
                  <div className=\"flex items-center gap-1 mb-1 text-xs text-zinc-400\">
                    <FileCode className=\"w-3 h-3\" />
                    <span>{msg.file_attachment.filename}</span>
                  </div>
                )}
                {renderMessageContent(msg)}
                <span className=\"text-[9px] text-zinc-600 mt-1 block font-mono\">
                  {formatTimestamp(msg.timestamp)}
                </span>
              </div>
              {msg.role === 'user' && (
                <div className=\"flex-shrink-0 w-6 h-6 rounded-full bg-zinc-700 flex items-center justify-center\">
                  <User className=\"w-4 h-4 text-white\" />
                </div>
              )}
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </ScrollArea>

      {/* File Preview */}
      {uploadedFile && (
        <div className=\"px-3 py-2 border-t border-white/5 bg-[#0F0F10]\">
          <div className=\"flex items-center justify-between\">
            <div className=\"flex items-center gap-2\">
              {filePreview ? (
                <img src={filePreview} alt=\"Preview\" className=\"w-12 h-12 object-cover rounded-sm border border-white/10\" />
              ) : (
                <FileText className=\"w-8 h-8 text-blue-400\" />
              )}
              <div>
                <p className=\"text-xs text-zinc-300\">{uploadedFile.name}</p>
                <p className=\"text-[10px] text-zinc-500\">{(uploadedFile.size / 1024).toFixed(1)} KB</p>
              </div>
            </div>
            <Button
              size=\"sm\"
              variant=\"ghost\"
              onClick={() => {
                setUploadedFile(null);
                setFilePreview(null);
              }}
              className=\"h-6 w-6 p-0\"
            >
              <X className=\"w-4 h-4\" />
            </Button>
          </div>
        </div>
      )}

      {/* Input Area */}
      <div className=\"p-3 border-t border-white/5 bg-[#18181B]\">
        <div className=\"flex gap-2\">
          <input
            ref={fileInputRef}
            type=\"file\"
            className=\"hidden\"
            onChange={handleFileSelect}
            accept=\".cs,.algo,.csbots,.txt,.csv,.json,.pdf,.png,.jpg,.jpeg,.webp\"
          />
          <Button
            size=\"sm\"
            variant=\"ghost\"
            onClick={() => fileInputRef.current?.click()}
            className=\"h-8 w-8 p-0 border border-white/10\"
            data-testid=\"attach-file-button\"
          >
            <Paperclip className=\"w-4 h-4\" />
          </Button>
          <Textarea
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSendMessage();
              }
            }}
            placeholder=\"Ask about your bot, upload files, or request improvements...\"
            className=\"flex-1 bg-black border-white/10 text-sm text-white placeholder:text-zinc-600 min-h-[60px] max-h-[120px] font-mono resize-none\"
            data-testid=\"chat-input\"
          />
          <Button
            onClick={handleSendMessage}
            disabled={isSending || (!inputMessage.trim() && !uploadedFile)}
            className=\"h-full bg-blue-600 hover:bg-blue-500 px-3\"
            data-testid=\"send-message-button\"
          >
            {isSending ? (
              <Loader2 className=\"w-4 h-4 animate-spin\" />
            ) : (
              <Send className=\"w-4 h-4\" />
            )}
          </Button>
        </div>
        <p className=\"text-[9px] text-zinc-600 mt-1 font-mono\">
          Press Enter to send, Shift+Enter for new line. Max 10MB files.
        </p>
      </div>
    </div>
  );
}
