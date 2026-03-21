const { spawn } = require('child_process')
const path = require('path')
const readline = require('readline')

let proc = null
let mainWindow = null
const listeners = { log: [], status: [], error: [], login_result: [], login_status: [] }

function getPythonExe() {
  if (process.env.VITE_DEV_SERVER_URL) {
    // Development: run bridge.py directly with Python
    return {
      cmd: 'python',
      args: [path.join(__dirname, '../../python/bridge.py')],
    }
  }
  // Production: use bundled executable
  return {
    cmd: path.join(process.resourcesPath, 'python-dist', 'bridge', 'bridge.exe'),
    args: [],
  }
}

function initPythonManager(win) {
  mainWindow = win
}

function startPython() {
  if (proc) return

  const { cmd, args } = getPythonExe()

  proc = spawn(cmd, args, {
    env: {
      ...process.env,
      PYTHONUNBUFFERED: '1',
      BRIDGE_MODE: '1',
    },
    stdio: ['pipe', 'pipe', 'pipe'],
  })

  const rl = readline.createInterface({ input: proc.stdout })
  rl.on('line', (line) => {
    line = line.trim()
    if (!line) return
    try {
      const msg = JSON.parse(line)
      dispatch(msg)
    } catch {
      // non-JSON stdout: treat as plain log
      dispatch({ type: 'log', level: 'debug', message: line, time: new Date().toISOString() })
    }
  })

  proc.stderr.on('data', (data) => {
    const text = data.toString().trim()
    if (text) {
      dispatch({ type: 'log', level: 'debug', message: `[stderr] ${text}`, time: new Date().toISOString() })
    }
  })

  proc.on('exit', (code) => {
    proc = null
    dispatch({ type: 'status', running: false })
    dispatch({ type: 'log', level: 'info', message: `Python 进程退出，代码: ${code}`, time: new Date().toISOString() })
  })

  proc.on('error', (err) => {
    proc = null
    dispatch({ type: 'error', code: 'SPAWN_ERROR', message: err.message })
  })
}

function stopPython() {
  if (proc) {
    proc.kill('SIGTERM')
    proc = null
  }
}

function sendCommand(cmd) {
  if (!proc) {
    startPython()
    // Give a small delay for Python to initialize before sending command
    setTimeout(() => {
      if (proc && proc.stdin.writable) {
        proc.stdin.write(JSON.stringify(cmd) + '\n')
      }
    }, 1500)
    return
  }
  if (proc.stdin.writable) {
    proc.stdin.write(JSON.stringify(cmd) + '\n')
  }
}

function dispatch(msg) {
  const type = msg.type
  if (listeners[type]) {
    listeners[type].forEach((cb) => cb(msg))
  }
  // Push to renderer via IPC
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send(`bot:${type}`, msg)
  }
}

function onLog(cb) { listeners.log.push(cb) }
function onStatus(cb) { listeners.status.push(cb) }
function onError(cb) { listeners.error.push(cb) }

module.exports = { initPythonManager, startPython, stopPython, sendCommand, onLog, onStatus, onError }
