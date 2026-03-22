import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useBotStore = defineStore('bot', () => {
  const running = ref(false)
  const logs = ref([])
  const MAX_LOGS = 500

  function setRunning(val) {
    running.value = val
  }

  function addLog(entry) {
    logs.value.push({
      ...entry,
      id: Date.now() + Math.random(),
    })
    if (logs.value.length > MAX_LOGS) {
      logs.value.splice(0, logs.value.length - MAX_LOGS)
    }
  }

  function clearLogs() {
    logs.value = []
  }

  return { running, logs, setRunning, addLog, clearLogs }
})
