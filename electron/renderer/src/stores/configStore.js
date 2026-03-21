import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useConfigStore = defineStore('config', () => {
  const config = ref({})
  const prompts = ref({})

  async function loadConfig() {
    config.value = await window.electronAPI.getConfig()
  }

  async function saveConfig(data) {
    await window.electronAPI.saveConfig(data)
    config.value = { ...config.value, ...data }
  }

  async function loadPrompts() {
    prompts.value = await window.electronAPI.getPrompts()
  }

  async function savePrompts(data) {
    await window.electronAPI.savePrompts(data)
    prompts.value = { ...prompts.value, ...data }
  }

  return { config, prompts, loadConfig, saveConfig, loadPrompts, savePrompts }
})
