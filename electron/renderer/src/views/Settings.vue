<template>
  <div class="page">
    <div class="page-header">
      <h1 class="page-title">设置</h1>
    </div>

    <div class="settings-body" v-if="loaded">
      <form @submit.prevent="save">
        <!-- Required -->
        <section class="settings-section">
          <h2 class="section-title">必填配置</h2>

          <div class="form-group">
            <label>API Key</label>
            <div class="input-group">
              <input
                :type="showApiKey ? 'text' : 'password'"
                v-model="form.API_KEY"
                placeholder="填入阿里云百炼 API Key"
              />
              <button type="button" class="toggle-btn" @click="showApiKey = !showApiKey">
                {{ showApiKey ? '隐藏' : '显示' }}
              </button>
            </div>
          </div>

          <div class="form-group">
            <label>Cookie 字符串 (COOKIES_STR)</label>
            <textarea
              v-model="form.COOKIES_STR"
              rows="4"
              placeholder="从浏览器开发者工具复制完整 Cookie"
            />
          </div>
        </section>

        <!-- Model -->
        <section class="settings-section">
          <h2 class="section-title">模型配置</h2>

          <div class="form-group">
            <label>API Base URL</label>
            <input v-model="form.MODEL_BASE_URL" placeholder="https://dashscope.aliyuncs.com/compatible-mode/v1" />
          </div>

          <div class="form-group">
            <label>模型名称</label>
            <input
              v-model="form.MODEL_NAME"
              list="model-suggestions"
              placeholder="qwen-max"
            />
            <datalist id="model-suggestions">
              <option value="qwen-max" />
              <option value="qwen-plus" />
              <option value="qwen-turbo" />
              <option value="qwen-long" />
            </datalist>
          </div>
        </section>

        <!-- Behavior -->
        <section class="settings-section">
          <h2 class="section-title">行为配置</h2>

          <div class="form-group">
            <label>人工接管关键词 (TOGGLE_KEYWORDS)</label>
            <input v-model="form.TOGGLE_KEYWORDS" placeholder="。" />
            <p class="hint">卖家发送此关键词可切换人工/自动模式</p>
          </div>

          <div class="form-group toggle-group">
            <label>模拟人工输入延迟</label>
            <label class="switch">
              <input type="checkbox" v-model="simulateHumanTyping" />
              <span class="slider"></span>
            </label>
          </div>
        </section>

        <!-- Advanced -->
        <section class="settings-section">
          <h2
            class="section-title expandable"
            @click="showAdvanced = !showAdvanced"
          >
            高级配置
            <span class="chevron">{{ showAdvanced ? '▲' : '▼' }}</span>
          </h2>

          <div v-if="showAdvanced" class="advanced-grid">
            <div class="form-group" v-for="field in advancedFields" :key="field.key">
              <label>{{ field.label }}</label>
              <input type="number" v-model.number="form[field.key]" :min="field.min" />
              <p class="hint">{{ field.hint }}</p>
            </div>
          </div>
        </section>

        <div class="form-actions">
          <button type="submit" class="btn btn-primary" :disabled="saving">
            {{ saving ? '保存中...' : '保存配置' }}
          </button>
          <span v-if="saved" class="save-ok">✓ 已保存，机器人将自动重载配置</span>
        </div>
      </form>
    </div>

    <div v-else class="loading">加载中...</div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'

const form = ref({})
const loaded = ref(false)
const saving = ref(false)
const saved = ref(false)
const showApiKey = ref(false)
const showAdvanced = ref(false)

const simulateHumanTyping = computed({
  get: () => form.value.SIMULATE_HUMAN_TYPING === 'True',
  set: (v) => { form.value.SIMULATE_HUMAN_TYPING = v ? 'True' : 'False' },
})

const advancedFields = [
  { key: 'HEARTBEAT_INTERVAL',    label: '心跳间隔 (秒)',        hint: '默认 15',  min: 5 },
  { key: 'HEARTBEAT_TIMEOUT',     label: '心跳超时 (秒)',        hint: '默认 5',   min: 1 },
  { key: 'TOKEN_REFRESH_INTERVAL', label: 'Token 刷新间隔 (秒)', hint: '默认 3600', min: 60 },
  { key: 'TOKEN_RETRY_INTERVAL',  label: 'Token 重试间隔 (秒)',  hint: '默认 300',  min: 30 },
  { key: 'MANUAL_MODE_TIMEOUT',   label: '人工接管超时 (秒)',    hint: '默认 3600', min: 60 },
  { key: 'MESSAGE_EXPIRE_TIME',   label: '消息过期时间 (毫秒)',  hint: '默认 300000', min: 1000 },
]

onMounted(async () => {
  form.value = await window.electronAPI.getConfig()
  loaded.value = true
})

async function save() {
  saving.value = true
  saved.value = false
  try {
    await window.electronAPI.saveConfig(form.value)
    saved.value = true
    setTimeout(() => { saved.value = false }, 3000)
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 20px;
  overflow: hidden;
}

.page-header {
  margin-bottom: 16px;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  color: #1e2030;
}

.settings-body {
  flex: 1;
  overflow-y: auto;
  padding-right: 8px;
}

.settings-section {
  background: #fff;
  border-radius: 10px;
  padding: 20px;
  margin-bottom: 16px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #475569;
  margin-bottom: 16px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.section-title.expandable {
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.chevron {
  font-size: 11px;
}

.input-group {
  display: flex;
  gap: 8px;
}

.toggle-btn {
  padding: 8px 12px;
  background: #e2e8f0;
  color: #475569;
  font-size: 12px;
  border-radius: 6px;
  flex-shrink: 0;
}

.hint {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 4px;
}

.toggle-group {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.toggle-group label:first-child {
  margin-bottom: 0;
}

.switch {
  position: relative;
  display: inline-block;
  width: 42px;
  height: 22px;
}

.switch input { opacity: 0; width: 0; height: 0; }

.slider {
  position: absolute;
  inset: 0;
  background: #cbd5e1;
  border-radius: 22px;
  cursor: pointer;
  transition: background 0.2s;
}

.switch input:checked + .slider {
  background: #4a9eff;
}

.slider::before {
  content: '';
  position: absolute;
  width: 16px;
  height: 16px;
  left: 3px;
  bottom: 3px;
  background: #fff;
  border-radius: 50%;
  transition: transform 0.2s;
}

.switch input:checked + .slider::before {
  transform: translateX(20px);
}

.advanced-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px 20px;
}

.form-actions {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 8px 0 20px;
}

.btn-primary {
  background: #4a9eff;
  color: #fff;
  padding: 9px 24px;
  font-weight: 500;
}

.btn-primary:not(:disabled):hover {
  background: #3a8eef;
}

.save-ok {
  color: #10b981;
  font-size: 13px;
}

.loading {
  color: #94a3b8;
  text-align: center;
  margin-top: 60px;
}
</style>
