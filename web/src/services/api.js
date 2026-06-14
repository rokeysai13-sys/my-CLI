import axios from 'axios';

const API_URL = 'http://127.0.0.1:5000';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json'
  }
});

// Configure request interceptor to add API key if set in settings
api.interceptors.request.use((config) => {
  const apiKey = localStorage.getItem('kirannn_api_key');
  if (apiKey) {
    config.headers['X-API-Key'] = apiKey;
  }
  return config;
}, (error) => {
  return Promise.reject(error);
});

export const chatService = {
  async sendMessage(message, mode = 'master', stream = false, model = null, sessionId = 'default', onToken = null) {
    if (stream && onToken) {
      return new Promise((resolve, reject) => {
        // Expose WebSocket protocol mapping
        const wsUrl = `ws://127.0.0.1:5000/ws/chat`;
        const ws = new WebSocket(wsUrl);
        const apiKey = localStorage.getItem('kirannn_api_key');
        let fullText = '';

        ws.onopen = () => {
          ws.send(JSON.stringify({
            message,
            model,
            session_id: sessionId,
            api_key: apiKey
          }));
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.type === 'token') {
              fullText += data.text;
              onToken(data.text);
            } else if (data.type === 'done') {
              ws.close();
              resolve({ response: data.full || fullText });
            } else if (data.type === 'error') {
              ws.close();
              reject(new Error(data.text));
            }
          } catch (err) {
            console.error('WS stream message parse error:', err);
          }
        };

        ws.onerror = (err) => {
          console.error('WS stream error:', err);
          reject(err);
        };
      });
    }

    try {
      let endpoint = '/chat';
      if (mode === 'debate') endpoint = '/chat/debate';
      else if (mode === 'code') endpoint = '/chat/code';
      else if (mode === 'research') endpoint = '/chat/research';
      else if (mode === 'pipeline') endpoint = '/chat/pipeline';
      else if (mode === 'master') endpoint = '/chat/agent';

      const response = await api.post(endpoint, {
        message,
        session_id: sessionId,
        model,
        stream
      });
      return response.data;
    } catch (error) {
      console.error('Chat API error:', error);
      throw error;
    }
  },
  
  async getHistory() {
    try {
      const response = await api.get('/chat/history');
      return response.data;
    } catch (error) {
      console.error('Failed to fetch history:', error);
      return [];
    }
  }
};

export const memoryService = {
  async getStats() {
    try {
      const response = await api.get('/memory/stats');
      return response.data;
    } catch (error) {
      console.error('Memory stats error:', error);
      return null;
    }
  },
  
  async readMemory() {
    try {
      const response = await api.get('/memory');
      return response.data;
    } catch (error) {
      console.error('Memory read error:', error);
      return {};
    }
  },
  
  async addMemory(entry, section = 'Recent Context') {
    try {
      const response = await api.post('/memory', { entry, section });
      return response.data;
    } catch (error) {
      console.error('Add memory error:', error);
      throw error;
    }
  },
  
  async searchMemory(query, count = 5) {
    try {
      const response = await api.get('/memory/search', {
        params: { q: query, n: count }
      });
      return response.data;
    } catch (error) {
      console.error('Memory search error:', error);
      return [];
    }
  },

  async getEpisodicStats() {
    try {
      const response = await api.get('/memory/episodic/stats');
      return response.data;
    } catch (error) {
      console.error('Episodic stats error:', error);
      return null;
    }
  },

  async triggerEpisodicSummarize(sessionId = 'default', username = 'guest') {
    try {
      const response = await api.post(`/memory/episodic/summarize?session_id=${sessionId}&username=${username}`);
      return response.data;
    } catch (error) {
      console.error('Episodic summarize error:', error);
      throw error;
    }
  }
};

export const ragService = {
  async ingestPath(path) {
    try {
      const response = await api.post('/rag/ingest', { path });
      return response.data;
    } catch (error) {
      console.error('RAG Ingest path error:', error);
      throw error;
    }
  },

  async ingestUrl(url) {
    try {
      const response = await api.post('/rag/ingest', { url });
      return response.data;
    } catch (error) {
      console.error('RAG Ingest URL error:', error);
      throw error;
    }
  },

  async searchRAG(query, count = 5) {
    try {
      const response = await api.get('/rag/search', {
        params: { q: query, n: count }
      });
      return response.data;
    } catch (error) {
      console.error('RAG search error:', error);
      return [];
    }
  }
};

export const skillsService = {
  async getSkills() {
    try {
      const response = await api.get('/skills');
      return response.data;
    } catch (error) {
      console.error('Get skills error:', error);
      return { skills: [], count: 0 };
    }
  },

  async reloadSkills() {
    try {
      const response = await api.post('/skills/reload');
      return response.data;
    } catch (error) {
      console.error('Reload skills error:', error);
      throw error;
    }
  },

  async generateSkill(capability) {
    try {
      const response = await api.post(`/self-code?capability=${encodeURIComponent(capability)}`);
      return response.data;
    } catch (error) {
      console.error('Generate skill error:', error);
      throw error;
    }
  }
};

export const reportsService = {
  async getReports() {
    try {
      const response = await api.get('/reports');
      return response.data;
    } catch (error) {
      console.error('Get reports error:', error);
      return [];
    }
  },

  async getReportContent(name) {
    try {
      const response = await api.get(`/reports/${name}`);
      return response.data;
    } catch (error) {
      console.error(`Get report content for ${name} error:`, error);
      return { success: false, error: error.message };
    }
  }
};

export const senseService = {
  async captureScreen() {
    try {
      const response = await api.get('/screen/capture');
      return response.data;
    } catch (error) {
      console.error('Screen capture error:', error);
      throw error;
    }
  },

  async readScreen() {
    try {
      const response = await api.get('/screen/read');
      return response.data;
    } catch (error) {
      console.error('Screen read error:', error);
      throw error;
    }
  },

  async activeWindow() {
    try {
      const response = await api.get('/screen/active-window');
      return response.data;
    } catch (error) {
      console.error('Active window error:', error);
      return null;
    }
  },

  async speakText(text) {
    try {
      const response = await api.post(`/voice/speak?text=${encodeURIComponent(text)}`);
      return response.data;
    } catch (error) {
      console.error('Speak text error:', error);
      throw error;
    }
  }
};

export const systemService = {
  async getStatus() {
    try {
      const response = await api.get('/status');
      return response.data;
    } catch (error) {
      console.error('Failed to fetch status:', error);
      return { status: 'error', error: error.message };
    }
  },

  async getHealth() {
    try {
      const response = await api.get('/health');
      return response.data;
    } catch (error) {
      console.error('Failed to fetch health:', error);
      return { api: 'offline', ollama: 'offline', models: [], error: error.message };
    }
  }
};

