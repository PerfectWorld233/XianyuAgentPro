const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electronAPI', {
  // Bot control
  botStart: () => ipcRenderer.invoke('bot:start'),
  botStop: () => ipcRenderer.invoke('bot:stop'),

  // Event listeners (push from main process)
  onBotStatus: (cb) => ipcRenderer.on('bot:status', (_event, msg) => cb(msg)),
  onBotLog: (cb) => ipcRenderer.on('bot:log', (_event, msg) => cb(msg)),
  onBotError: (cb) => ipcRenderer.on('bot:error', (_event, msg) => cb(msg)),

  // Remove all listeners for a channel
  removeAllListeners: (channel) => ipcRenderer.removeAllListeners(channel),

  // Config
  getConfig: () => ipcRenderer.invoke('config:get'),
  saveConfig: (data) => ipcRenderer.invoke('config:save', data),

  // Prompts
  getPrompts: () => ipcRenderer.invoke('prompts:get'),
  savePrompts: (data) => ipcRenderer.invoke('prompts:save', data),
  getDefaultPrompts: () => ipcRenderer.invoke('prompts:get_defaults'),

  // AI prompt generation
  generatePrompts: (chatLog) => ipcRenderer.invoke('prompts:generate', chatLog),
  onGeneratePromptsResult: (cb) => ipcRenderer.on('bot:generate_prompts_result', (_event, msg) => cb(msg)),

  // Open URL in system browser
  openUrl: (url) => ipcRenderer.invoke('shell:open_url', url),
})
