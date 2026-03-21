const { getConfig, saveConfig, getPrompts, savePrompts } = require('./dbManager')
const { sendCommand } = require('./pythonManager')

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

  ipcMain.handle('bot:check_login', () => {
    sendCommand({ cmd: 'check_login' })
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
}

module.exports = { registerIpcHandlers }
