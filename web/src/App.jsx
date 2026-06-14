import React, { useState, useEffect, useRef } from 'react';
import { 
  Bot, Terminal, Shield, Zap, Settings, BookOpen, Send, User, 
  Moon, Sun, Camera, Mic, Volume2, RefreshCw, Search, PlusCircle, 
  Download, ExternalLink, FileText, Check, AlertCircle, Trash2, 
  List, Play, Sparkles, Cpu, Eye, Activity, Key, Globe
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { 
  chatService, memoryService, ragService, 
  skillsService, reportsService, senseService, systemService 
} from './services/api';
import './index.css';

// ── HEADER / TOP TOOLBAR ──────────────────────────────────────────────────────
const TopToolbar = ({ theme, toggleTheme, systemStatus, healthData }) => {
  const [apiKey, setApiKey] = useState(localStorage.getItem('kirannn_api_key') || '');
  const [showKeyInput, setShowKeyInput] = useState(false);

  const saveApiKey = () => {
    localStorage.setItem('kirannn_api_key', apiKey);
    setShowKeyInput(false);
    alert('API Key updated successfully.');
  };

  return (
    <header className="top-toolbar" style={{
      height: '60px',
      padding: '0 24px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      borderBottom: '1px solid var(--border-color)',
      background: 'var(--bg-card)',
      zIndex: 5,
      transition: 'background 0.3s ease, border-bottom 0.3s ease'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <div className={`status-dot ${systemStatus === 'online' ? 'active' : ''}`} />
        <span style={{ fontSize: '13px', fontWeight: '500', color: 'var(--text-secondary)' }}>
          {systemStatus === 'online' ? 'Connected' : 'Connecting to Server...'}
        </span>
        {healthData && healthData.ollama === 'ok' && (
          <span style={{ 
            fontSize: '11px', 
            padding: '2px 8px', 
            background: 'var(--accent-primary-dim)', 
            color: 'var(--accent-primary)', 
            borderRadius: '12px',
            marginLeft: '8px',
            fontWeight: '600'
          }}>
            Ollama Active
          </span>
        )}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        {/* API Key settings */}
        <div style={{ position: 'relative' }}>
          <button 
            onClick={() => setShowKeyInput(!showKeyInput)}
            style={{ color: 'var(--text-secondary)', padding: '6px' }}
            title="API Key Configuration"
          >
            <Key size={18} />
          </button>
          
          {showKeyInput && (
            <div className="glass-panel" style={{
              position: 'absolute',
              right: 0,
              top: '32px',
              padding: '16px',
              borderRadius: 'var(--radius-md)',
              width: '240px',
              zIndex: 100,
              boxShadow: 'var(--shadow-lg)'
            }}>
              <h4 style={{ fontSize: '12px', marginBottom: '8px' }}>X-API-KEY Configuration</h4>
              <input 
                type="password"
                placeholder="Enter password..."
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                className="apple-input"
                style={{ fontSize: '12px', padding: '6px 10px', marginBottom: '10px' }}
              />
              <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                <button 
                  onClick={() => { localStorage.removeItem('kirannn_api_key'); setApiKey(''); setShowKeyInput(false); }}
                  style={{ fontSize: '11px', color: 'var(--accent-danger)' }}
                >
                  Clear
                </button>
                <button 
                  onClick={saveApiKey}
                  className="apple-btn"
                  style={{ fontSize: '11px', padding: '4px 10px' }}
                >
                  Save
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Theme Toggle */}
        <button 
          onClick={toggleTheme} 
          style={{ color: 'var(--text-secondary)', padding: '6px' }}
          title={theme === 'light' ? 'Switch to Dark Mode' : 'Switch to Light Mode'}
        >
          {theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}
        </button>
      </div>
    </header>
  );
};

// ── SIDEBAR ──────────────────────────────────────────────────────────────────
const Sidebar = ({ currentView, setView }) => {
  return (
    <aside className="sidebar">
      <div className="sidebar-header" style={{ padding: '32px 24px 24px', borderBottom: '1px solid var(--border-color)' }}>
        <h2 style={{ display: 'flex', alignItems: 'center', gap: '10px', color: 'var(--text-primary)', fontSize: '20px', fontWeight: '700', letterSpacing: '-0.02em' }}>
          <span style={{
            background: 'linear-gradient(135deg, #0071e3, #5856d6)',
            width: '28px',
            height: '28px',
            borderRadius: '8px',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
            fontSize: '16px',
            fontWeight: 'bold',
            boxShadow: '0 2px 8px rgba(0,113,227,0.3)'
          }}>K</span>
          Kirannn <span style={{ fontWeight: '300', fontSize: '14px', color: 'var(--text-secondary)' }}>v4.0</span>
        </h2>
        <div style={{ marginTop: '8px', fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: '600' }}>
          Jarvis Agent Core
        </div>
      </div>
      
      <nav style={{ padding: '24px 16px', display: 'flex', flexDirection: 'column', gap: '4px', flex: 1 }}>
        {[
          { id: 'chat', label: 'Agent Workspace', icon: Terminal },
          { id: 'memory', label: 'Memory Core', icon: BookOpen },
          { id: 'agents', label: 'Swarm & Reports', icon: Shield },
          { id: 'skills', label: 'Skills Studio', icon: Zap },
          { id: 'settings', label: 'Settings', icon: Settings }
        ].map((item) => {
          const Icon = item.icon;
          const isActive = currentView === item.id;
          return (
            <button 
              key={item.id}
              onClick={() => setView(item.id)}
              style={{
                display: 'flex', alignItems: 'center', gap: '12px',
                padding: '10px 16px', borderRadius: 'var(--radius-sm)',
                color: isActive ? 'var(--accent-primary)' : 'var(--text-secondary)',
                background: isActive ? 'var(--accent-primary-dim)' : 'transparent',
                transition: 'all 0.2s ease',
                textAlign: 'left',
                fontWeight: isActive ? '600' : '500',
                width: '100%',
                fontSize: '13.5px'
              }}
            >
              <Icon size={16} />
              {item.label}
            </button>
          )
        })}
      </nav>

      <div style={{ padding: '20px 24px', borderTop: '1px solid var(--border-color)', fontSize: '11px', color: 'var(--text-muted)' }}>
        Local Intelligence Swarm
      </div>
    </aside>
  );
};

// ── VIEW 1: CHAT WORKSPACE ───────────────────────────────────────────────────
const ChatWorkspace = () => {
  const [messages, setMessages] = useState([
    { role: 'assistant', content: 'Welcome to the Agentic Workspace. I am ready to assist you. Choose an agent mode above to direct your request.' }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [mode, setMode] = useState('master'); // 'master', 'debate', 'code', 'research', 'pipeline'
  const [ttsActive, setTtsActive] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const handleSend = async (e) => {
    if (e) e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setIsLoading(true);

    if (mode === 'master') {
      try {
        // Append an empty assistant message that will be populated dynamically
        setMessages(prev => [...prev, { role: 'assistant', content: '', streaming: true }]);

        const response = await chatService.sendMessage(
          userMessage,
          mode,
          true, // stream: true
          null, // model
          'default', // session_id
          (token) => {
            setMessages(prev => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              if (last && last.role === 'assistant' && last.streaming) {
                last.content += token;
              }
              return updated;
            });
          }
        );

        // Finalize streaming state
        setMessages(prev => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last && last.role === 'assistant') {
            last.streaming = false;
            if (response.response) {
              last.content = response.response;
            }
          }
          return updated;
        });
      } catch (error) {
        setMessages(prev => {
          const updated = [...prev];
          if (updated[updated.length - 1] && updated[updated.length - 1].streaming) {
            updated.pop();
          }
          updated.push({
            role: 'assistant',
            content: `**Error:** Failed to stream from agent backend. ${error.message}`
          });
          return updated;
        });
      } finally {
        setIsLoading(false);
      }
    } else {
      try {
        const response = await chatService.sendMessage(userMessage, mode);
        setMessages(prev => [...prev, { 
          role: 'assistant', 
          content: response.response || response.plan || response.execution || JSON.stringify(response),
          metadata: response.metadata || { mode }
        }]);
      } catch (error) {
        setMessages(prev => [...prev, { 
          role: 'assistant', 
          content: `**Error:** Failed to communicate with agent backend. ${error.response?.data?.detail || error.message}` 
        }]);
      } finally {
        setIsLoading(false);
      }
    }
  };

  // Real-world sense: Capture Screenshot and describe it
  const handleCaptureScreen = async () => {
    setIsLoading(true);
    setMessages(prev => [...prev, { role: 'user', content: '📸 Taking screenshot and scanning details...' }]);
    try {
      const captureResult = await senseService.captureScreen();
      const ocrResult = await senseService.readScreen();
      const activeWindow = await senseService.activeWindow();
      
      let contextMsg = `I captured your screen at ${captureResult.screenshot_path || 'temporary buffer'}.\n\n`;
      if (activeWindow) {
        contextMsg += `**Active Window:** ${activeWindow.title || 'Unknown'} (Process: ${activeWindow.process || 'N/A'})\n`;
      }
      if (ocrResult && ocrResult.screen_text) {
        contextMsg += `\n**Recognized Text on Screen:**\n\`\`\`\n${ocrResult.screen_text.substring(0, 1000)}\n\`\`\``;
      } else {
        contextMsg += `\nNo text detected via screen OCR.`;
      }

      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: contextMsg
      }]);
    } catch (error) {
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: `**Error capturing screen:** ${error.message}` 
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  // Real-world sense: Voice speak synthesis of last assistant response
  const handleSpeakLastMessage = async () => {
    const lastAssistantMessage = [...messages].reverse().find(m => m.role === 'assistant');
    if (!lastAssistantMessage) return;

    setTtsActive(true);
    try {
      // Clean markdown tags out of message for cleaner speech
      const textToSpeak = lastAssistantMessage.content.replace(/[*_`#\-]/g, '');
      await senseService.speakText(textToSpeak.substring(0, 500));
    } catch (error) {
      alert('Voice synthesis error: ' + error.message);
    } finally {
      setTtsActive(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="chat-workspace animate-fade-in" style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: '32px', height: '100%', background: 'var(--bg-color)' }}>
      
      {/* Mode Selector - Apple Pill segmented style */}
      <div style={{ 
        display: 'inline-flex', 
        alignSelf: 'center',
        background: 'var(--bg-sidebar)', 
        padding: '4px', 
        borderRadius: '30px', 
        gap: '4px',
        marginBottom: '24px',
        boxShadow: 'var(--shadow-sm)',
        border: 'var(--glass-border)'
      }}>
        {[
          { id: 'master', label: 'Master Swarm', icon: Sparkles },
          { id: 'research', label: 'Deep Research', icon: Search },
          { id: 'debate', label: 'Debate Core', icon: User },
          { id: 'code', label: 'Coder Agent', icon: Cpu },
          { id: 'pipeline', label: 'Task Pipeline', icon: Activity }
        ].map((btn) => {
          const Icon = btn.icon;
          const isSelected = mode === btn.id;
          return (
            <button 
              key={btn.id}
              onClick={() => setMode(btn.id)}
              style={{
                padding: '8px 16px',
                borderRadius: '20px',
                fontSize: '12px',
                fontWeight: '600',
                background: isSelected ? 'var(--bg-card)' : 'transparent',
                color: isSelected ? 'var(--accent-primary)' : 'var(--text-secondary)',
                boxShadow: isSelected ? 'var(--shadow-sm)' : 'none',
                transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
                display: 'flex',
                alignItems: 'center',
                gap: '6px'
              }}
            >
              <Icon size={13} />
              {btn.label}
            </button>
          )
        })}
      </div>

      <div className="glass-panel" style={{ flex: 1, borderRadius: 'var(--radius-xl)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        
        {/* Messages Area */}
        <div style={{ flex: 1, padding: '32px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {messages.map((msg, idx) => (
            <div key={idx} style={{ display: 'flex', gap: '16px', flexDirection: msg.role === 'user' ? 'row-reverse' : 'row', alignItems: 'flex-start' }}>
              <div style={{ 
                width: '36px', height: '36px', minWidth: '36px', borderRadius: '50%', 
                background: msg.role === 'user' ? 'var(--accent-primary-dim)' : 'var(--bg-sidebar)', 
                display: 'flex', alignItems: 'center', justifyContent: 'center', 
                color: msg.role === 'user' ? 'var(--accent-primary)' : 'var(--accent-secondary)',
                border: 'var(--glass-border)',
                boxShadow: 'var(--shadow-sm)'
              }}>
                {msg.role === 'user' ? <User size={18} /> : <Bot size={18} />}
              </div>
              <div style={{ 
                background: msg.role === 'user' ? 'var(--accent-primary)' : 'var(--bg-card)', 
                padding: '16px 20px', 
                borderRadius: msg.role === 'user' ? '18px 18px 4px 18px' : '18px 18px 18px 4px', 
                border: 'var(--glass-border)', 
                maxWidth: '75%',
                color: msg.role === 'user' ? '#ffffff' : 'var(--text-primary)',
                boxShadow: 'var(--shadow-sm)',
                transition: 'background 0.3s ease, color 0.3s ease'
              }}>
                {msg.role === 'user' ? (
                  <p style={{ margin: 0, color: 'inherit', fontSize: '14.5px' }}>{msg.content}</p>
                ) : (
                  <div className="markdown-body">
                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                  </div>
                )}
                {msg.metadata && (
                  <div style={{ 
                    marginTop: '12px', 
                    fontSize: '11px', 
                    color: msg.role === 'user' ? 'rgba(255,255,255,0.7)' : 'var(--text-muted)', 
                    borderTop: msg.role === 'user' ? '1px solid rgba(255,255,255,0.2)' : '1px solid var(--border-color)', 
                    paddingTop: '8px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between'
                  }}>
                    <span>Mode: {msg.metadata.mode || 'standard'}</span>
                    {!msg.role === 'user' && (
                      <button onClick={handleSpeakLastMessage} style={{ background: 'transparent', border: 'none', color: 'inherit', display: 'flex', alignItems: 'center', gap: '4px', padding: 0 }}>
                        <Volume2 size={12} /> {ttsActive ? 'Speaking...' : 'Speak'}
                      </button>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}

          {isLoading && (
            <div style={{ display: 'flex', gap: '16px', alignItems: 'flex-start' }}>
              <div style={{ width: '36px', height: '36px', borderRadius: '50%', background: 'var(--bg-sidebar)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', border: 'var(--glass-border)' }}>
                <Bot size={18} />
              </div>
              <div style={{ background: 'var(--bg-card)', padding: '16px 20px', borderRadius: '18px 18px 18px 4px', border: 'var(--glass-border)', boxShadow: 'var(--shadow-sm)' }}>
                <div style={{ display: 'flex', gap: '6px', alignItems: 'center', height: '14px' }}>
                  <span className="status-dot active" style={{ width: '6px', height: '6px', background: 'var(--text-muted)', boxShadow: 'none' }}></span>
                  <span className="status-dot active" style={{ width: '6px', height: '6px', background: 'var(--text-muted)', boxShadow: 'none', animationDelay: '0.2s' }}></span>
                  <span className="status-dot active" style={{ width: '6px', height: '6px', background: 'var(--text-muted)', boxShadow: 'none', animationDelay: '0.4s' }}></span>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div style={{ padding: '24px 32px', borderTop: '1px solid var(--border-color)', background: 'var(--bg-card)', transition: 'background 0.3s ease' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            
            {/* Quick Senses Toolbar */}
            <div style={{ display: 'flex', gap: '8px' }}>
              <button 
                onClick={handleCaptureScreen}
                style={{ 
                  width: '40px', height: '40px', borderRadius: '50%', 
                  background: 'var(--bg-sidebar)', color: 'var(--text-secondary)',
                  border: 'var(--glass-border)'
                }}
                title="Scan Current Screen"
              >
                <Camera size={18} />
              </button>
              <button 
                onClick={handleSpeakLastMessage}
                style={{ 
                  width: '40px', height: '40px', borderRadius: '50%', 
                  background: 'var(--bg-sidebar)', color: 'var(--text-secondary)',
                  border: 'var(--glass-border)'
                }}
                title="Read Last Response Aloud"
              >
                <Volume2 size={18} />
              </button>
            </div>

            <form onSubmit={handleSend} style={{ flex: 1, display: 'flex', gap: '12px', background: 'var(--bg-sidebar)', borderRadius: '24px', padding: '6px 6px 6px 20px', border: 'var(--glass-border)', alignItems: 'center' }}>
              <input 
                type="text" 
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={`Ask ${mode === 'master' ? 'Kirannn Master Agent' : 'the ' + mode + ' pipeline'}...`} 
                style={{ flex: 1, background: 'transparent', border: 'none', color: 'var(--text-primary)', outline: 'none', fontFamily: 'var(--font-sans)', fontSize: '14px' }}
                disabled={isLoading}
              />
              <button 
                type="submit"
                disabled={!input.trim() || isLoading}
                style={{ 
                  background: input.trim() && !isLoading ? 'var(--accent-primary)' : 'transparent', 
                  color: input.trim() && !isLoading ? '#ffffff' : 'var(--text-muted)', 
                  padding: '10px', 
                  borderRadius: '50%', 
                  width: '36px',
                  height: '36px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  transition: 'all 0.2s ease',
                  cursor: input.trim() && !isLoading ? 'pointer' : 'default'
                }}
              >
                <Send size={16} />
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
};

// ── VIEW 2: MEMORY CORE ──────────────────────────────────────────────────────
const MemoryCore = () => {
  const [stats, setStats] = useState(null);
  const [episodicStats, setEpisodicStats] = useState(null);
  const [memories, setMemories] = useState({});
  const [newEntry, setNewEntry] = useState('');
  const [newSection, setNewSection] = useState('Recent Context');
  const [ingestPath, setIngestPath] = useState('');
  const [ingestUrl, setIngestUrl] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [isIngesting, setIsIngesting] = useState(false);
  const [isSearching, setIsSearching] = useState(false);

  const loadMemoryData = async () => {
    const statsData = await memoryService.getStats();
    setStats(statsData);
    const epStats = await memoryService.getEpisodicStats();
    setEpisodicStats(epStats);
    const items = await memoryService.readMemory();
    setMemories(items || {});
  };

  useEffect(() => {
    loadMemoryData();
  }, []);

  const handleAddMemory = async (e) => {
    e.preventDefault();
    if (!newEntry.trim()) return;
    try {
      await memoryService.addMemory(newEntry, newSection);
      setNewEntry('');
      loadMemoryData();
      alert('Memory logged successfully.');
    } catch (err) {
      alert('Error writing memory: ' + err.message);
    }
  };

  const handleIngestFile = async (e) => {
    e.preventDefault();
    if (!ingestPath.trim()) return;
    setIsIngesting(true);
    try {
      await ragService.ingestPath(ingestPath);
      setIngestPath('');
      loadMemoryData();
      alert('Document successfully chunked and loaded into local vector space.');
    } catch (err) {
      alert('Ingestion failed: ' + err.response?.data?.detail || err.message);
    } finally {
      setIsIngesting(false);
    }
  };

  const handleIngestUrl = async (e) => {
    e.preventDefault();
    if (!ingestUrl.trim()) return;
    setIsIngesting(true);
    try {
      await ragService.ingestUrl(ingestUrl);
      setIngestUrl('');
      loadMemoryData();
      alert('Web page successfully scraped, chunked, and indexed.');
    } catch (err) {
      alert('URL ingestion failed: ' + err.message);
    } finally {
      setIsIngesting(false);
    }
  };

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    setIsSearching(true);
    try {
      const results = await memoryService.searchMemory(searchQuery, 4);
      setSearchResults(results);
    } catch (err) {
      alert('Search failed: ' + err.message);
    } finally {
      setIsSearching(false);
    }
  };

  const triggerSummarization = async () => {
    try {
      await memoryService.triggerEpisodicSummarize();
      alert('Episodic consolidation complete.');
      loadMemoryData();
    } catch (err) {
      alert('Consolidation failed: ' + err.message);
    }
  };

  return (
    <div className="animate-fade-in" style={{ flex: 1, padding: '32px', overflowY: 'auto', background: 'var(--bg-color)', display: 'flex', flexDirection: 'column', gap: '32px' }}>
      
      {/* Title & Header */}
      <div>
        <h1 style={{ fontSize: '28px', letterSpacing: '-0.025em', marginBottom: '8px' }}>Memory Core</h1>
        <p>Manage episodic memories, key-value storage, and local RAG document ingestion.</p>
      </div>

      {/* Grid of stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '24px' }}>
        <div className="apple-card">
          <h3 style={{ fontSize: '16px', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <Activity size={18} color="var(--accent-primary)" />
            ChromaDB Vector Store
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Status:</span>
              <span style={{ fontWeight: '600', color: 'var(--accent-success)' }}>Active</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Embedding Model:</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '12px' }}>nomic-embed-text</span>
            </div>
            {stats && (
              <>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Stored Memories:</span>
                  <span style={{ fontWeight: '600' }}>{stats.count || 0} entries</span>
                </div>
              </>
            )}
          </div>
        </div>

        <div className="apple-card">
          <h3 style={{ fontSize: '16px', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <Sparkles size={18} color="var(--accent-secondary)" />
            Episodic Summary Control
          </h3>
          <p style={{ fontSize: '13px', marginBottom: '16px' }}>Consolidate chat history and cache recent queries to build dynamic agent context.</p>
          <button onClick={triggerSummarization} className="apple-btn" style={{ width: '100%', gap: '8px' }}>
            <RefreshCw size={14} /> Consolidate Memories
          </button>
        </div>
      </div>

      {/* Document RAG Ingestion */}
      <div className="apple-card">
        <h3 style={{ fontSize: '16px', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
          <Globe size={18} color="var(--accent-primary)" />
          RAG Document Ingestion
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
          <form onSubmit={handleIngestFile}>
            <h4 style={{ fontSize: '13px', marginBottom: '8px', color: 'var(--text-secondary)' }}>Local File Path (PDF, TXT, MD)</h4>
            <div style={{ display: 'flex', gap: '8px' }}>
              <input 
                type="text" 
                placeholder="C:\docs\report.pdf" 
                value={ingestPath} 
                onChange={(e) => setIngestPath(e.target.value)} 
                className="apple-input"
              />
              <button type="submit" disabled={isIngesting} className="apple-btn-secondary">
                {isIngesting ? 'Loading...' : 'Ingest'}
              </button>
            </div>
          </form>
          <form onSubmit={handleIngestUrl}>
            <h4 style={{ fontSize: '13px', marginBottom: '8px', color: 'var(--text-secondary)' }}>Web URL Scraper</h4>
            <div style={{ display: 'flex', gap: '8px' }}>
              <input 
                type="text" 
                placeholder="https://example.com/docs" 
                value={ingestUrl} 
                onChange={(e) => setIngestUrl(e.target.value)} 
                className="apple-input"
              />
              <button type="submit" disabled={isIngesting} className="apple-btn-secondary">
                {isIngesting ? 'Loading...' : 'Scrape'}
              </button>
            </div>
          </form>
        </div>
      </div>

      {/* Memory Search & Results */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', alignItems: 'start' }}>
        {/* Search */}
        <div className="apple-card">
          <h3 style={{ fontSize: '16px', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <Search size={18} color="var(--accent-primary)" />
            Search Memory
          </h3>
          <form onSubmit={handleSearch} style={{ display: 'flex', gap: '8px', marginBottom: '20px' }}>
            <input 
              type="text" 
              placeholder="Query semantic database..." 
              value={searchQuery} 
              onChange={(e) => setSearchQuery(e.target.value)} 
              className="apple-input"
            />
            <button type="submit" className="apple-btn">
              {isSearching ? <RefreshCw size={14} className="animate-spin" /> : 'Query'}
            </button>
          </form>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {searchResults.length > 0 ? (
              searchResults.map((res, idx) => (
                <div key={idx} style={{ padding: '12px', background: 'var(--bg-sidebar)', borderRadius: 'var(--radius-sm)', border: 'var(--glass-border)' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '4px', display: 'flex', justifyContent: 'space-between' }}>
                    <span>Candidate #{idx+1}</span>
                    <span>Distance: {res.distance ? res.distance.toFixed(4) : 'N/A'}</span>
                  </div>
                  <p style={{ fontSize: '13px', margin: 0, color: 'var(--text-primary)' }}>{res.text || JSON.stringify(res)}</p>
                </div>
              ))
            ) : (
              <div style={{ color: 'var(--text-muted)', fontSize: '13px', textAlign: 'center', padding: '20px' }}>
                Enter a query to run semantic search.
              </div>
            )}
          </div>
        </div>

        {/* Log Custom Memory */}
        <div className="apple-card">
          <h3 style={{ fontSize: '16px', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <PlusCircle size={18} color="var(--accent-success)" />
            Log Custom Context
          </h3>
          <form onSubmit={handleAddMemory} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div>
              <label style={{ fontSize: '12px', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>Section Header</label>
              <input 
                type="text" 
                value={newSection} 
                onChange={(e) => setNewSection(e.target.value)} 
                className="apple-input" 
              />
            </div>
            <div>
              <label style={{ fontSize: '12px', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>Entry Content</label>
              <textarea 
                rows="3"
                value={newEntry} 
                onChange={(e) => setNewEntry(e.target.value)} 
                className="apple-input"
                placeholder="Write a fact or detail..."
                style={{ resize: 'none' }}
              />
            </div>
            <button type="submit" className="apple-btn">Add Entry</button>
          </form>
        </div>
      </div>
    </div>
  );
};

// ── VIEW 3: AGENT SWARM & REPORTS ─────────────────────────────────────────────
const AgentSwarm = () => {
  const [reports, setReports] = useState([]);
  const [activeReport, setActiveReport] = useState(null);
  const [reportContent, setReportContent] = useState('');
  const [loadingReport, setLoadingReport] = useState(false);

  const fetchReports = async () => {
    const data = await reportsService.getReports();
    setReports(data || []);
  };

  useEffect(() => {
    fetchReports();
  }, []);

  const handleReadReport = async (name) => {
    setActiveReport(name);
    setLoadingReport(true);
    setReportContent('');
    try {
      const content = await reportsService.getReportContent(name);
      setReportContent(content.content || JSON.stringify(content));
    } catch (err) {
      setReportContent('Failed to fetch report content: ' + err.message);
    } finally {
      setLoadingReport(false);
    }
  };

  return (
    <div className="animate-fade-in" style={{ flex: 1, padding: '32px', overflowY: 'auto', background: 'var(--bg-color)', display: 'flex', gap: '32px', height: '100%' }}>
      {/* Left Pane - Swarm listing & Reports */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '32px', maxWidth: '45%' }}>
        <div>
          <h1 style={{ fontSize: '28px', letterSpacing: '-0.025em', marginBottom: '8px' }}>Swarm Intelligence</h1>
          <p>Inspect active agents, coordination flow, and output documents.</p>
        </div>

        {/* Roles List */}
        <div className="apple-card">
          <h3 style={{ fontSize: '15px', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Cpu size={16} color="var(--accent-primary)" />
            Active Swarm Components
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {[
              { role: 'Planner Agent', desc: 'Breaks large, multi-stage goals into task checklists.' },
              { role: 'Critic Agent', desc: 'Validates code execution outputs, correcting syntax & logical bugs.' },
              { role: 'Researcher Agent', desc: 'Synthesizes web-scraped findings and factual sources.' },
              { role: 'Coder Agent', desc: 'Constructs software, script edits, and updates configurations.' },
              { role: 'Security Agent', desc: 'Audits inputs/outputs to prevent dangerous executions.' }
            ].map((r, idx) => (
              <div key={idx} style={{ display: 'flex', alignItems: 'flex-start', gap: '12px', borderBottom: '1px solid var(--border-color)', paddingBottom: '10px' }}>
                <span className="status-dot active" style={{ marginTop: '6px' }} />
                <div>
                  <h4 style={{ fontSize: '13px', fontWeight: '600' }}>{r.role}</h4>
                  <p style={{ fontSize: '12px', color: 'var(--text-secondary)', margin: 0 }}>{r.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Reports Directory */}
        <div className="apple-card" style={{ flex: 1 }}>
          <h3 style={{ fontSize: '15px', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FileText size={16} color="var(--accent-secondary)" />
            Generated Reports
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '300px', overflowY: 'auto' }}>
            {reports.length > 0 ? (
              reports.map((rep, idx) => (
                <button 
                  key={idx}
                  onClick={() => handleReadReport(rep)}
                  style={{
                    padding: '12px 16px',
                    borderRadius: 'var(--radius-sm)',
                    border: '1px solid var(--border-color)',
                    background: activeReport === rep ? 'var(--accent-primary-dim)' : 'var(--bg-card)',
                    color: activeReport === rep ? 'var(--accent-primary)' : 'var(--text-primary)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    width: '100%',
                    textAlign: 'left'
                  }}
                >
                  <span style={{ fontSize: '13px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <FileText size={14} />
                    {rep}
                  </span>
                  <ExternalLink size={12} />
                </button>
              ))
            ) : (
              <div style={{ textAlign: 'center', padding: '32px', color: 'var(--text-muted)', fontSize: '13px' }}>
                No reports found in /reports directory.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Right Pane - Report Reader */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-lg)', padding: '24px', overflowY: 'auto' }}>
        {activeReport ? (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-color)', paddingBottom: '12px', marginBottom: '16px' }}>
              <h3 style={{ fontSize: '16px' }}>Document: {activeReport}</h3>
              <button onClick={() => handleReadReport(activeReport)} style={{ color: 'var(--text-muted)' }}>
                <RefreshCw size={14} className={loadingReport ? 'animate-spin' : ''} />
              </button>
            </div>
            
            {loadingReport ? (
              <div style={{ textAlign: 'center', padding: '48px', color: 'var(--text-muted)' }}>Loading file content...</div>
            ) : (
              <div className="markdown-body">
                <ReactMarkdown>{reportContent}</ReactMarkdown>
              </div>
            )}
          </div>
        ) : (
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', flexDirection: 'column', gap: '12px' }}>
            <FileText size={36} style={{ strokeWidth: '1.5' }} />
            <span style={{ fontSize: '13px' }}>Select a report to view contents here</span>
          </div>
        )}
      </div>
    </div>
  );
};

// ── VIEW 4: SKILLS STUDIO ─────────────────────────────────────────────────────
const SkillsStudio = () => {
  const [skills, setSkills] = useState([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isReloading, setIsReloading] = useState(false);
  const [capability, setCapability] = useState('');

  const loadSkills = async () => {
    const res = await skillsService.getSkills();
    setSkills(res.skills || []);
  };

  useEffect(() => {
    loadSkills();
  }, []);

  const handleGenerate = async (e) => {
    e.preventDefault();
    if (!capability.trim()) return;
    setIsGenerating(true);
    try {
      const res = await skillsService.generateSkill(capability);
      setCapability('');
      await loadSkills();
      alert(`Skill generated and written to ${res.skill_path || 'skills_hub'}. Run reload below to compile it.`);
    } catch (err) {
      alert('Generation error: ' + err.message);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleReload = async () => {
    setIsReloading(true);
    try {
      await skillsService.reloadSkills();
      alert('Skills hot-loaded into active agent swarm.');
      await loadSkills();
    } catch (err) {
      alert('Hot-reload error: ' + err.message);
    } finally {
      setIsReloading(false);
    }
  };

  return (
    <div className="animate-fade-in" style={{ flex: 1, padding: '32px', overflowY: 'auto', background: 'var(--bg-color)', display: 'flex', flexDirection: 'column', gap: '32px' }}>
      <div>
        <h1 style={{ fontSize: '28px', letterSpacing: '-0.025em', marginBottom: '8px' }}>Skills Studio</h1>
        <p>Command the self-coding agent to build, test, and hot-load new Python skills.</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', alignItems: 'start' }}>
        {/* Generator */}
        <div className="apple-card">
          <h3 style={{ fontSize: '16px', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <Sparkles size={18} color="var(--accent-primary)" />
            Self-Code Generator
          </h3>
          <p style={{ fontSize: '13px', marginBottom: '16px' }}>
            Describe a function or integration. The coder agent will generate the Python code, run tests, and save the module locally.
          </p>
          <form onSubmit={handleGenerate} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <textarea 
              rows="4"
              value={capability}
              onChange={(e) => setCapability(e.target.value)}
              className="apple-input"
              placeholder="e.g. Write a skill to scrape a weather API for Hyderabad and calculate average humidity..."
              style={{ resize: 'none' }}
              disabled={isGenerating}
            />
            <button type="submit" className="apple-btn" disabled={isGenerating}>
              {isGenerating ? <RefreshCw size={14} className="animate-spin" /> : 'Synthesize Skill'}
            </button>
          </form>
        </div>

        {/* Loader/Reload */}
        <div className="apple-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h3 style={{ fontSize: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Zap size={18} color="var(--accent-warning)" />
              Swarm Skill Hub
            </h3>
            <button 
              onClick={handleReload} 
              disabled={isReloading} 
              className="apple-btn-secondary"
              style={{ padding: '6px 12px', fontSize: '12px' }}
            >
              {isReloading ? 'Reloading...' : 'Hot Reload'}
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '300px', overflowY: 'auto' }}>
            {skills.length > 0 ? (
              skills.map((sk, idx) => (
                <div key={idx} style={{ 
                  padding: '12px', 
                  background: 'var(--bg-sidebar)', 
                  borderRadius: 'var(--radius-sm)', 
                  border: 'var(--glass-border)',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center'
                }}>
                  <div>
                    <h4 style={{ fontSize: '13px', fontWeight: '600' }}>{sk.name}</h4>
                    <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Size: {(sk.size/1024).toFixed(2)} KB</span>
                  </div>
                  <span style={{ fontSize: '10px', padding: '2px 6px', background: 'var(--bg-card)', border: 'var(--glass-border)', borderRadius: '4px', color: 'var(--text-secondary)' }}>
                    Active
                  </span>
                </div>
              ))
            ) : (
              <div style={{ textAlign: 'center', padding: '32px', color: 'var(--text-muted)', fontSize: '13px' }}>
                No self-generated skills found. Inject a task to synthesize one!
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

// ── VIEW 5: SETTINGS & HEALTH ─────────────────────────────────────────────────
const SettingsView = ({ healthData, refreshHealth }) => {
  const [apiKeyVal, setApiKeyVal] = useState(localStorage.getItem('kirannn_api_key') || '');
  
  const saveKey = () => {
    localStorage.setItem('kirannn_api_key', apiKeyVal);
    alert('Settings Saved');
  };

  return (
    <div className="animate-fade-in" style={{ flex: 1, padding: '32px', overflowY: 'auto', background: 'var(--bg-color)', display: 'flex', flexDirection: 'column', gap: '32px' }}>
      <div>
        <h1 style={{ fontSize: '28px', letterSpacing: '-0.025em', marginBottom: '8px' }}>System Settings</h1>
        <p>Monitor local service health, Ollama status, and security keys.</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', alignItems: 'start' }}>
        {/* API Credentials */}
        <div className="apple-card">
          <h3 style={{ fontSize: '16px', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <Key size={18} color="var(--accent-primary)" />
            Security & Authentication
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div>
              <label style={{ fontSize: '12px', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>X-API-KEY</label>
              <input 
                type="password" 
                value={apiKeyVal} 
                onChange={(e) => setApiKeyVal(e.target.value)} 
                className="apple-input" 
                placeholder="Set backend authorization code..."
              />
            </div>
            <button onClick={saveKey} className="apple-btn">Save Configurations</button>
          </div>
        </div>

        {/* Diagnostics Info */}
        <div className="apple-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h3 style={{ fontSize: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Activity size={18} color="var(--accent-secondary)" />
              Diagnostics Dashboard
            </h3>
            <button onClick={refreshHealth} className="apple-btn-secondary" style={{ padding: '4px 8px', fontSize: '11px' }}>
              Refresh
            </button>
          </div>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-secondary)' }}>FastAPI Port:</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '13px' }}>8000</span>
            </div>
            {healthData ? (
              <>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Ollama Backend:</span>
                  <span style={{ fontWeight: '600', color: healthData.ollama === 'ok' ? 'var(--accent-success)' : 'var(--accent-danger)' }}>
                    {healthData.ollama === 'ok' ? 'Online' : 'Offline'}
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Vector Collections:</span>
                  <span style={{ fontWeight: '600' }}>{healthData.memory ? 'Chroma Vector DB Linked' : 'Failed'}</span>
                </div>
                {healthData.models && healthData.models.length > 0 && (
                  <div style={{ marginTop: '12px' }}>
                    <label style={{ fontSize: '12px', color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>Available Ollama Models:</label>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                      {healthData.models.map((m, idx) => (
                        <span key={idx} style={{ 
                          fontSize: '11px', 
                          padding: '2px 8px', 
                          background: 'var(--bg-sidebar)', 
                          border: 'var(--glass-border)', 
                          borderRadius: '6px',
                          fontFamily: 'var(--font-mono)'
                        }}>
                          {m}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div style={{ color: 'var(--text-muted)', fontSize: '12px' }}>Connection to diagnosticians failed.</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

// ── MAIN APPLICATION WRAPPER ─────────────────────────────────────────────────
function App() {
  const [currentView, setView] = useState('chat');
  const [systemStatus, setSystemStatus] = useState('connecting');
  const [theme, setTheme] = useState(localStorage.getItem('kirannn_theme') || 'light');
  const [healthData, setHealthData] = useState(null);

  // Toggle Theme between Light & Dark Modes
  const toggleTheme = () => {
    const nextTheme = theme === 'light' ? 'dark' : 'light';
    setTheme(nextTheme);
    localStorage.setItem('kirannn_theme', nextTheme);
  };

  // Sync class on document element
  useEffect(() => {
    if (theme === 'dark') {
      document.body.classList.add('dark-theme');
    } else {
      document.body.classList.remove('dark-theme');
    }
  }, [theme]);

  const fetchHealth = async () => {
    const res = await systemService.getHealth();
    setHealthData(res);
    if (res && res.api === 'ok') {
      setSystemStatus('online');
    } else {
      // If status check endpoint is ok but full health failed, try to fallback to ping status
      const ping = await systemService.getStatus();
      if (ping && ping.status === 'ok') {
        setSystemStatus('online');
      } else {
        setSystemStatus('offline');
      }
    }
  };

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 15000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="app-container">
      <Sidebar currentView={currentView} setView={setView} />
      <main className="main-content">
        <TopToolbar 
          theme={theme} 
          toggleTheme={toggleTheme} 
          systemStatus={systemStatus} 
          healthData={healthData} 
        />
        <div style={{ flex: 1, overflow: 'hidden' }}>
          {currentView === 'chat' && <ChatWorkspace />}
          {currentView === 'memory' && <MemoryCore />}
          {currentView === 'agents' && <AgentSwarm />}
          {currentView === 'skills' && <SkillsStudio />}
          {currentView === 'settings' && <SettingsView healthData={healthData} refreshHealth={fetchHealth} />}
        </div>
      </main>
    </div>
  );
}

export default App;
