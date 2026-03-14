const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("electronAPI", {
  platform: process.platform,

  send: (channel, data) => {
    const allowed = [
      "ollama-retry",
      "ollama-skip",
      "ollama-download",
      "ollama-close",
      "window-close",
      "window-minimize",
      "window-maximize",
      "check-backend",
      "get-version",
    ];
    if (allowed.includes(channel)) ipcRenderer.send(channel, data);
  },

  on: (channel, callback) => {
    const allowed = ["ollama-still-missing"];
    if (allowed.includes(channel))
      ipcRenderer.on(channel, (_event, ...args) => callback(...args));
  },

  checkBackend: () => ipcRenderer.invoke("check-backend"),
  getVersion: () => ipcRenderer.invoke("get-version"),
  windowClose: () => ipcRenderer.invoke("window-close"),
  windowMinimize: () => ipcRenderer.invoke("window-minimize"),
  windowMaximize: () => ipcRenderer.invoke("window-maximize"),
});
