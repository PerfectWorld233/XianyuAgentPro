<template>
  <div class="page">
    <div class="page-header">
      <h1 class="page-title">提示词编辑</h1>
    </div>

    <!-- AI 生成面板 -->
    <div class="ai-panel">
      <div class="ai-panel-header" @click="showAiPanel = !showAiPanel">
        <span>AI 生成提示词（粘贴聊天记录）</span>
        <span class="chevron">{{ showAiPanel ? '▲' : '▼' }}</span>
      </div>
      <div v-if="showAiPanel" class="ai-panel-body">
        <textarea
          class="chat-log-input"
          v-model="chatLog"
          rows="6"
          placeholder="将买卖双方的聊天记录粘贴到此处…"
          spellcheck="false"
        />
        <div class="ai-actions">
          <button
            class="btn btn-ai"
            :disabled="generating || !chatLog.trim()"
            @click="generatePrompts"
          >
            {{ generating ? 'AI 生成中…' : 'AI 生成' }}
          </button>
          <span v-if="generateError" class="generate-err">✗ {{ generateError }}</span>
        </div>
      </div>
    </div>

    <div class="prompts-body" v-if="loaded">
      <!-- Tabs -->
      <div class="tabs">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          class="tab"
          :class="{ active: activeTab === tab.key }"
          @click="activeTab = tab.key"
        >
          {{ tab.label }}
        </button>
      </div>

      <!-- Editor -->
      <div class="editor-area">
        <div v-for="tab in tabs" :key="tab.key" v-show="activeTab === tab.key" class="editor-pane">
          <div class="editor-toolbar">
            <span class="char-count">{{ (form[tab.key] || '').length }} 字符</span>
            <button type="button" class="btn btn-text" @click="resetPrompt(tab.key)">
              恢复默认
            </button>
          </div>
          <textarea
            class="prompt-editor"
            v-model="form[tab.key]"
            :placeholder="`在此输入 ${tab.label} 提示词...`"
            spellcheck="false"
          />
          <div class="form-actions">
            <button class="btn btn-primary" :disabled="savingKey === tab.key" @click="save(tab.key)">
              {{ savingKey === tab.key ? '保存中...' : `保存${tab.label}` }}
            </button>
            <span v-if="savedKey === tab.key" class="save-ok">✓ 已保存</span>
          </div>
        </div>
      </div>
    </div>

    <div v-else class="loading">加载中...</div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const tabs = [
  { key: 'classify_prompt', label: '意图分类' },
  { key: 'price_prompt',    label: '价格谈判' },
  { key: 'tech_prompt',     label: '技术咨询' },
  { key: 'default_prompt',  label: '默认回复' },
]

const activeTab = ref('classify_prompt')
const form = ref({})
const defaults = ref({})
const loaded = ref(false)
const savingKey = ref('')   // 当前正在保存的 tab key
const savedKey = ref('')    // 最近保存成功的 tab key
const chatLog = ref('')
const generating = ref(false)
const generateError = ref('')
const showAiPanel = ref(false)

onMounted(async () => {
  const [prompts, defaultPrompts] = await Promise.all([
    window.electronAPI.getPrompts(),
    window.electronAPI.getDefaultPrompts(),
  ])
  defaults.value = defaultPrompts
  // 以默认值为底座，合并数据库中已保存的值，确保每个 key 始终有字符串值
  form.value = { ...defaultPrompts, ...prompts }
  window.electronAPI.onGeneratePromptsResult((msg) => {
    generating.value = false
    if (msg.success) {
      Object.assign(form.value, msg.prompts)
      showAiPanel.value = false
      activeTab.value = 'classify_prompt'
    } else {
      generateError.value = msg.message || '生成失败，请重试'
    }
  })
  loaded.value = true
})

function resetPrompt(key) {
  if (confirm(`确定要恢复 "${tabs.find(t => t.key === key)?.label}" 提示词为当前默认内容吗？`)) {
    form.value[key] = defaults.value[key] || ''
  }
}

async function generatePrompts() {
  generating.value = true
  generateError.value = ''
  await window.electronAPI.generatePrompts(chatLog.value)
}

async function save(key) {
  savingKey.value = key
  savedKey.value = ''
  try {
    await window.electronAPI.savePrompts({ [key]: form.value[key] })
    savedKey.value = key
    setTimeout(() => { savedKey.value = '' }, 3000)
  } finally {
    savingKey.value = ''
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

.prompts-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  gap: 12px;
}

.tabs {
  display: flex;
  gap: 4px;
  background: #e2e8f0;
  padding: 4px;
  border-radius: 8px;
}

.tab {
  flex: 1;
  padding: 7px 12px;
  border-radius: 6px;
  font-size: 13px;
  background: transparent;
  color: #475569;
  transition: background 0.15s, color 0.15s;
}

.tab:hover {
  background: #fff;
}

.tab.active {
  background: #fff;
  color: #1e2030;
  font-weight: 600;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

.editor-area {
  flex: 1;
  overflow: hidden;
}

.editor-pane {
  display: flex;
  flex-direction: column;
  height: 100%;
  gap: 6px;
  overflow: hidden;
}

.editor-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.char-count {
  font-size: 12px;
  color: #94a3b8;
}

.btn-text {
  background: transparent;
  color: #4a9eff;
  font-size: 12px;
  padding: 4px 8px;
}

.btn-text:hover {
  text-decoration: underline;
}

.prompt-editor {
  flex: 1;
  resize: none;
  font-family: 'Consolas', 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
  background: #1e1e2e;
  color: #cdd6f4;
  border: 1px solid #313244;
  border-radius: 8px;
  padding: 12px;
}

.prompt-editor:focus {
  border-color: #4a9eff;
}

.form-actions {
  display: flex;
  align-items: center;
  gap: 16px;
  padding-top: 4px;
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

.ai-panel {
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
  margin-bottom: 12px;
  overflow: hidden;
}

.ai-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  font-size: 13px;
  font-weight: 600;
  color: #475569;
  cursor: pointer;
  user-select: none;
}

.ai-panel-header:hover {
  background: #f8fafc;
}

.ai-panel-body {
  padding: 0 14px 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.chat-log-input {
  width: 100%;
  resize: vertical;
  font-size: 12px;
  font-family: 'Consolas', monospace;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 8px;
  color: #1e2030;
  line-height: 1.5;
  box-sizing: border-box;
}

.chat-log-input:focus {
  border-color: #4a9eff;
  outline: none;
}

.ai-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.btn-ai {
  background: #7c3aed;
  color: #fff;
  padding: 7px 18px;
  font-size: 13px;
  border-radius: 6px;
  font-weight: 500;
}

.btn-ai:not(:disabled):hover {
  background: #6d28d9;
}

.btn-ai:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.generate-err {
  font-size: 12px;
  color: #d20f39;
}
</style>
