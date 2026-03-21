const { app, BrowserWindow, ipcMain, nativeTheme } = require('electron')
const path = require('path')

const { initPythonManager } = require('./pythonManager')
const { registerIpcHandlers } = require('./ipcHandlers')
const { initDbManager } = require('./dbManager')

let mainWindow

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1100,
    height: 700,
    minWidth: 800,
    minHeight: 600,
    title: 'XianyuAutoAgent',
    webPreferences: {
      preload: path.join(__dirname, '../preload/preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  if (process.env.VITE_DEV_SERVER_URL) {
    mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL)
    mainWindow.webContents.openDevTools()
  } else {
    mainWindow.loadFile(path.join(__dirname, '../renderer/dist/index.html'))
  }
}

app.whenReady().then(() => {
  // Override userData path so Python and Electron share the same APPDATA dir
  const dataDir = path.join(app.getPath('appData'), 'XianyuAutoAgent')
  app.setPath('userData', dataDir)

  initDbManager(dataDir)
  initPythonManager(mainWindow)
  registerIpcHandlers(ipcMain, mainWindow)

  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

// Export mainWindow getter for other modules
module.exports = { getMainWindow: () => mainWindow }
