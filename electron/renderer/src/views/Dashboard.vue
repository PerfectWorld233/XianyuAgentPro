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
          class="btn btn-login"
          :disabled="loginState === 'pending'"
          @click="doLogin"
        >
          {{ loginState === 'pending' ? '登录中…' : '扫码登录' }}
        </button>
        <span v-if="loginState === 'success'" class="login-ok">✓ 登录成功</span>
        <span v-if="loginState === 'failed'" class="login-err">✗ 登录失败，请重试</span>
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
import { ref, onMounted } from 'vue'
import { useBotStore } from '../stores/botStore'
import StatusBadge from '../components/StatusBadge.vue'
import LogViewer from '../components/LogViewer.vue'

const botStore = useBotStore()
const loginState = ref('idle') // 'idle' | 'pending' | 'success' | 'failed'

async function startBot() {
  await window.electronAPI.botStart()
}

async function stopBot() {
  await window.electronAPI.botStop()
}

async function doLogin() {
  loginState.value = 'pending'
  await window.electronAPI.botLogin()
}

onMounted(() => {
  window.electronAPI.onLoginResult((msg) => {
    loginState.value = msg.success ? 'success' : 'failed'
    setTimeout(() => {
      loginState.value = 'idle'
    }, 3000)
  })
})
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

.btn-login {
  background: #a6e3a1;
  color: #1e2030;
}

.btn-login:not(:disabled):hover {
  background: #8fd68a;
}

.btn-login:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.login-ok {
  font-size: 13px;
  color: #40a02b;
  font-weight: 500;
}

.login-err {
  font-size: 13px;
  color: #d20f39;
  font-weight: 500;
}

.log-area {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
</style>
