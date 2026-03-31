<template>
  <div class="app-layout">
    <!-- Sidebar navigation -->
    <nav class="sidebar">
      <div class="sidebar-logo">
        <span class="logo-icon">🐟</span>
        <span class="logo-text">闲鱼助手</span>
      </div>
      <ul class="nav-links">
        <li>
          <router-link to="/" class="nav-item" active-class="active" exact>
            <span class="nav-icon">📊</span>
            <span>控制台</span>
          </router-link>
        </li>
        <li>
          <router-link to="/settings" class="nav-item" active-class="active">
            <span class="nav-icon">⚙️</span>
            <span>设置</span>
          </router-link>
        </li>
        <li>
          <router-link to="/prompts" class="nav-item" active-class="active">
            <span class="nav-icon">📝</span>
            <span>提示词</span>
          </router-link>
        </li>
        <li>
          <router-link to="/knowledge" class="nav-item" active-class="active">
            <span class="nav-icon">📚</span>
            <span>知识库</span>
          </router-link>
        </li>
      </ul>
    </nav>

    <!-- Main content area -->
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted } from 'vue'
import { useBotStore } from './stores/botStore'

const botStore = useBotStore()

onMounted(() => {
  window.electronAPI.onBotStatus((msg) => {
    botStore.setRunning(msg.running)
  })
  window.electronAPI.onBotLog((msg) => {
    botStore.addLog(msg)
  })
  window.electronAPI.onBotError((msg) => {
    botStore.addLog({ ...msg, level: 'error' })
  })
})

onUnmounted(() => {
  window.electronAPI.removeAllListeners('bot:status')
  window.electronAPI.removeAllListeners('bot:log')
  window.electronAPI.removeAllListeners('bot:error')
})
</script>

<style scoped>
.app-layout {
  display: flex;
  height: 100vh;
  width: 100%;
}

.sidebar {
  width: 200px;
  min-width: 200px;
  background: #1e2030;
  color: #cdd6f4;
  display: flex;
  flex-direction: column;
  padding: 16px 0;
}

.sidebar-logo {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 20px 20px;
  border-bottom: 1px solid #313244;
}

.logo-icon {
  font-size: 22px;
}

.logo-text {
  font-size: 16px;
  font-weight: 600;
  color: #cdd6f4;
}

.nav-links {
  list-style: none;
  padding: 12px 0;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 20px;
  color: #a6adc8;
  border-radius: 0;
  transition: background 0.15s, color 0.15s;
  font-size: 14px;
}

.nav-item:hover {
  background: #313244;
  color: #cdd6f4;
}

.nav-item.active {
  background: #45475a;
  color: #89b4fa;
  border-left: 3px solid #89b4fa;
}

.nav-icon {
  font-size: 16px;
  width: 20px;
  text-align: center;
}

.main-content {
  flex: 1;
  overflow: hidden;
  background: #f5f5f5;
}
</style>
