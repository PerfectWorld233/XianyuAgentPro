<template>
  <div class="page">
    <!-- 登录状态横幅 -->
    <div v-if="botStore.loginStatus === 'checking'" class="login-banner banner-checking">
      正在检测闲鱼登录状态…
    </div>
    <div v-else-if="botStore.loginStatus === 'logged_out'" class="login-banner banner-warn">
      未检测到闲鱼登录，请先扫码登录才能启动机器人。
      <button
        class="btn btn-login banner-login-btn"
        :disabled="loginState === 'pending'"
        @click="doLogin"
      >
        {{ loginState === 'pending' ? '登录中…' : '立即扫码登录' }}
      </button>
    </div>
    <div v-else-if="botStore.loginStatus === 'logged_in'" class="login-banner banner-ok">
      闲鱼已登录
    </div>
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
    if (msg.success) {
      loginState.value = 'success'
      // 登录成功后重新触发登录状态检查
      botStore.setLoginStatus('checking')
      window.electronAPI.checkLogin()
    } else {
      loginState.value = 'failed'
    }
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

.login-banner {
  padding: 10px 18px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 12px;
}

.banner-checking {
  background: #e2e8f0;
  color: #64748b;
}

.banner-warn {
  background: #fff7ed;
  color: #c2410c;
  border: 1px solid #fed7aa;
}

.banner-ok {
  background: #f0fdf4;
  color: #15803d;
  border: 1px solid #bbf7d0;
}

.banner-login-btn {
  padding: 5px 14px;
  font-size: 12px;
}
</style>
