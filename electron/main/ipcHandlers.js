const { getConfig, saveConfig, getPrompts, savePrompts } = require('./dbManager')
const { sendCommand, startPython } = require('./pythonManager')

function registerIpcHandlers(ipcMain, mainWindow) {
  // Bot control
  ipcMain.handle('bot:start', () => {
    sendCommand({ cmd: 'start' })
  })

  ipcMain.handle('bot:stop', () => {
    sendCommand({ cmd: 'stop' })
  })

  ipcMain.handle('bot:login', () => {
    sendCommand({ cmd: 'login' })
  })

  // Config
  ipcMain.handle('config:get', () => {
    return getConfig()
  })

  ipcMain.handle('config:save', (_event, data) => {
    saveConfig(data)
    sendCommand({ cmd: 'reload_config' })
    return { ok: true }
  })

  // Prompts
  ipcMain.handle('prompts:get', () => {
    return getPrompts()
  })

  ipcMain.handle('prompts:save', (_event, data) => {
    savePrompts(data)
    sendCommand({ cmd: 'reload_config' })
    return { ok: true }
  })

  // Ensure Python process is running when app starts
  startPython()
}

module.exports = { registerIpcHandlers }
