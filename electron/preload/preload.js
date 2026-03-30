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

  // Knowledge base
  listKnowledge: (opts) => ipcRenderer.invoke('knowledge:list', opts),
  addKnowledge: (data) => ipcRenderer.invoke('knowledge:add', data),
  updateKnowledge: (data) => ipcRenderer.invoke('knowledge:update', data),
  deleteKnowledge: (data) => ipcRenderer.invoke('knowledge:delete', data),
  batchAddKnowledge: (data) => ipcRenderer.invoke('knowledge:batchAdd', data),
  generateFromImage: () => ipcRenderer.invoke('knowledge:generateFromImage'),
  generateFromChat: (data) => ipcRenderer.invoke('knowledge:generateFromChat', data),
  onKnowledgeGenerateResult: (cb) => ipcRenderer.on('bot:knowledge_generate_result', (_event, msg) => cb(msg)),
  onKnowledgeGenerateError: (cb) => ipcRenderer.on('bot:knowledge_generate_error', (_event, msg) => cb(msg)),
  // Clean up both knowledge event listeners (called in KnowledgeBase.vue onUnmounted)
  removeAllKnowledgeListeners: () => {
    ipcRenderer.removeAllListeners('bot:knowledge_generate_result')
    ipcRenderer.removeAllListeners('bot:knowledge_generate_error')
  },

  // Open URL in system browser
  openUrl: (url) => ipcRenderer.invoke('shell:open_url', url),
})
