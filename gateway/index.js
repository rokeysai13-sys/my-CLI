const express = require('express');
const cors = require('cors');
const { createProxyMiddleware } = require('http-proxy-middleware');
const http = require('http');
const WebSocket = require('ws');

const app = express();
const PORT = process.env.PORT || 5000;
const PYTHON_BACKEND = 'http://127.0.0.1:8000';

app.use(cors());
app.use(express.json());

// 1. WebSocket Chat Handler (proxies SSE to WebSocket client)
const server = http.createServer(app);
const wss = new WebSocket.Server({ server, path: '/ws/chat' });

wss.on('connection', (ws) => {
  console.log('[GATEWAY] WebSocket client connected.');

  ws.on('message', async (data) => {
    try {
      const payload = JSON.parse(data.toString());
      const { message, model, session_id } = payload;
      
      console.log(`[GATEWAY] Initiating chat stream for: "${message}"`);
      
      // Make HTTP request to python SSE stream
      const requestData = JSON.stringify({
        message,
        model: model || null,
        session_id: session_id || 'default',
        stream: true
      });

      const options = {
        hostname: '127.0.0.1',
        port: 8000,
        path: '/chat/agent',
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(requestData)
        }
      };

      // Add API Key header if provided in request
      const apiKey = payload.api_key || process.env.KIRANNN_API_KEY;
      if (apiKey) {
        options.headers['X-API-Key'] = apiKey;
      }

      const req = http.request(options, (res) => {
        let buffer = '';

        res.on('data', (chunk) => {
          buffer += chunk.toString();
          
          // Process Server-Sent Events from chunk
          const lines = buffer.split('\n');
          // Keep the last incomplete line in buffer
          buffer = lines.pop();

          for (const line of lines) {
            const cleanLine = line.trim();
            if (cleanLine.startsWith('data:')) {
              try {
                const sseData = JSON.parse(cleanLine.substring(5).trim());
                // Forward JSON payload directly to WebSocket
                if (ws.readyState === WebSocket.OPEN) {
                  ws.send(JSON.stringify(sseData));
                }
              } catch (err) {
                // Ignore parse errors on ping/meta lines
              }
            }
          }
        });

        res.on('end', () => {
          // Send remaining buffer if any
          if (buffer.trim().startsWith('data:')) {
            try {
              const sseData = JSON.parse(buffer.trim().substring(5).trim());
              if (ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify(sseData));
              }
            } catch (err) {}
          }
          console.log('[GATEWAY] Stream finished.');
        });
      });

      req.on('error', (e) => {
        console.error(`[GATEWAY] Backend connection error: ${e.message}`);
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'error', text: `Backend connection error: ${e.message}` }));
        }
      });

      req.write(requestData);
      req.end();

    } catch (err) {
      console.error('[GATEWAY] Failed to parse socket message:', err);
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'error', text: 'Invalid request payload.' }));
      }
    }
  });

  ws.on('close', () => {
    console.log('[GATEWAY] Client disconnected.');
  });
});

// 2. HTTP Proxy Router for normal REST endpoints
app.use(
  '/',
  createProxyMiddleware({
    target: PYTHON_BACKEND,
    changeOrigin: true,
    ws: false, // Handle websockets separately via Express HTTP Server + ws module
    onError: (err, req, res) => {
      console.error('[GATEWAY] Proxy Error:', err);
      res.status(500).json({ error: 'Gateway failed to communicate with backend core.' });
    }
  })
);

server.listen(PORT, () => {
  console.log(`[GATEWAY] Node.js Gateway running on http://localhost:${PORT}`);
});
