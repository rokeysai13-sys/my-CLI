const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');

let mainWindow;
let pythonProcess;
let gatewayProcess;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    title: "kirannn - Desktop Jarvis OS",
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  // Load React Vite dev server
  mainWindow.loadURL('http://localhost:5173');

  // Open devtools if running in dev mode
  if (process.env.NODE_ENV === 'development') {
    mainWindow.webContents.openDevTools();
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

function startServices() {
  console.log('[ELECTRON] Starting Python Backend...');
  
  // Resolve path to python virtualenv interpreter on Windows or Unix
  const rootDir = path.join(__dirname, '..');
  let pythonPath = 'python';
  const venvWin = path.join(rootDir, '.venv', 'Scripts', 'python.exe');
  const venvUnix = path.join(rootDir, '.venv', 'bin', 'python');

  if (fs.existsSync(venvWin)) {
    pythonPath = venvWin;
  } else if (fs.existsSync(venvUnix)) {
    pythonPath = venvUnix;
  }

  // Spawn Python FastAPI Server
  pythonProcess = spawn(pythonPath, ['main.py'], { cwd: rootDir });
  
  pythonProcess.stdout.on('data', (data) => {
    console.log(`[PYTHON] ${data.toString().trim()}`);
  });

  pythonProcess.stderr.on('data', (data) => {
    console.warn(`[PYTHON-WARN] ${data.toString().trim()}`);
  });

  pythonProcess.on('close', (code) => {
    console.log(`[PYTHON] Process exited with code ${code}`);
  });

  // Spawn Node.js Gateway Server
  console.log('[ELECTRON] Starting Node.js Gateway...');
  const gatewayDir = path.join(rootDir, 'gateway');
  gatewayProcess = spawn('node', ['index.js'], { cwd: gatewayDir });

  gatewayProcess.stdout.on('data', (data) => {
    console.log(`[GATEWAY] ${data.toString().trim()}`);
  });

  gatewayProcess.stderr.on('data', (data) => {
    console.warn(`[GATEWAY-WARN] ${data.toString().trim()}`);
  });

  gatewayProcess.on('close', (code) => {
    console.log(`[GATEWAY] Process exited with code ${code}`);
  });
}

function cleanUp() {
  console.log('[ELECTRON] Cleaning up child processes...');
  if (pythonProcess) {
    pythonProcess.kill();
  }
  if (gatewayProcess) {
    gatewayProcess.kill();
  }
}

app.whenReady().then(() => {
  startServices();
  
  // Wait a short delay to let services start before loading window
  setTimeout(createWindow, 2500);

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('will-quit', () => {
  cleanUp();
});

// IPC Handler
ipcMain.on('notify', (event, { title, body }) => {
  console.log(`[NOTIFICATION] ${title}: ${body}`);
});
