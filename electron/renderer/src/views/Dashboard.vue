<template>
  <div class="page">
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">控制台</h1>
        <StatusBadge :running="botStore.running" />
      </div>
      <div class="header-actions">
        <button class="btn btn-danger" :disabled="!botStore.running" @click="stopBot">
          停止
        </button>
        <button class="btn btn-primary" :disabled="botStore.running" @click="startBot">
          启动
        </button>
        <button
          class="btn btn-quick-start"
          :disabled="botStore.running"
          @click="quickStart"
        >
          一键启动
        </button>
        <button class="btn btn-secondary" @click="botStore.clearLogs">
          清空日志
        </button>
      </div>
    </div>

    <div class="log-area">
      <LogViewer :logs="botStore.logs" />
    </div>
  </div>
</template>

<script setup>
import { useBotStore } from '../stores/botStore'
import StatusBadge from '../components/StatusBadge.vue'
import LogViewer from '../components/LogViewer.vue'

const botStore = useBotStore()

const XIANYU_IM_URL = 'https://www.goofish.com/im'

async function startBot() {
  await window.electronAPI.botStart()
}

async function stopBot() {
  await window.electronAPI.botStop()
}

async function quickStart() {
  window.electronAPI.openUrl(XIANYU_IM_URL)
  await window.electronAPI.botStart()
}
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 20px;
  gap: 16px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  color: #1e2030;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.btn {
  padding: 8px 18px;
  font-size: 13px;
  border-radius: 6px;
  font-weight: 500;
}

.btn-primary {
  background: #4a9eff;
  color: #fff;
}

.btn-primary:not(:disabled):hover {
  background: #3a8eef;
}

.btn-danger {
  background: #f38ba8;
  color: #fff;
}

.btn-danger:not(:disabled):hover {
  background: #e07090;
}

.btn-secondary {
  background: #e2e8f0;
  color: #475569;
}

.btn-secondary:hover {
  background: #cbd5e1;
}

.btn-quick-start {
  background: #f9a825;
  color: #fff;
  font-weight: 600;
}

.btn-quick-start:not(:disabled):hover {
  background: #e69500;
}

.btn-quick-start:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.log-area {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
</style>
