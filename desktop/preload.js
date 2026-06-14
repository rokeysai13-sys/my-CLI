const { contextBridge, ipcRenderer } = require('electron');

// Securely expose APIs to React renderer process
contextBridge.exposeInMainWorld('electronAPI', {
  sendNotification: (title, body) => ipcRenderer.send('notify', { title, body }),
  getPlatform: () => process.platform
});
