const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("electronAPI", {
  platform: process.platform,
  checkBackend: () => ipcRenderer.invoke("check-backend"),
  getVersion: () => ipcRenderer.invoke("get-version"),
  // 창 제어
  windowClose: () => ipcRenderer.invoke("window-close"),
  windowMinimize: () => ipcRenderer.invoke("window-minimize"),
  windowMaximize: () => ipcRenderer.invoke("window-maximize"),
});
