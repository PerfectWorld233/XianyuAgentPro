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
          @click="switchTab(tab.key)"
        >
          {{ tab.label }}<span v-if="dirtyKeys.includes(tab.key)" class="tab-dirty-dot"> ●</span>
        </button>
        <!-- preview tab: only shown when AI results are pending -->
        <button
          v-if="previewPrompts !== null"
          class="tab tab-preview"
          :class="{ active: activeTab === '__preview__' }"
          @click="switchTab('__preview__')"
        >
          ✨ AI 预览
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

      <!-- AI Preview Tab content -->
      <div v-show="activeTab === '__preview__'" class="preview-area">
        <div v-for="tab in tabs" :key="tab.key" class="preview-panel">
          <div class="preview-panel-header">
            <span class="preview-panel-title">{{ tab.label }}</span>
            <button class="btn btn-primary btn-sm" @click="applyPreview(tab.key)">应用此项</button>
          </div>
          <div class="preview-panel-body">
            <textarea
              class="preview-readonly"
              readonly
              :value="form[tab.key]"
              spellcheck="false"
            />
            <textarea
              class="preview-editable prompt-editor"
              v-model="previewPrompts[tab.key]"
              spellcheck="false"
            />
          </div>
        </div>
        <div class="preview-actions">
          <button class="btn btn-primary" @click="applyAllPreviews">全部应用</button>
          <button class="btn btn-secondary" @click="discardPreview">放弃</button>
        </div>
      </div>
    </div>

    <div v-else class="loading">加载中...</div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'

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

const savedState = ref({})   // snapshot of form at last save / initial load
const previewPrompts = ref(null)  // null | { classify_prompt, price_prompt, tech_prompt, default_prompt }

// dirtyKeys: which of the 4 regular tabs have unsaved edits
const dirtyKeys = computed(() =>
  tabs.filter(t => form.value[t.key] !== savedState.value[t.key]).map(t => t.key)
)

onMounted(async () => {
  const [prompts, defaultPrompts] = await Promise.all([
    window.electronAPI.getPrompts(),
    window.electronAPI.getDefaultPrompts(),
  ])
  defaults.value = defaultPrompts
  // 以默认值为底座，合并数据库中已保存的值，确保每个 key 始终有字符串值
  form.value = { ...defaultPrompts, ...prompts }
  savedState.value = { ...form.value }  // snapshot — must be before AI listener
  window.electronAPI.onGeneratePromptsResult((msg) => {
    generating.value = false
    if (msg.success) {
      const p = msg.prompts || {}
      // validate each key; fall back to current form value if missing
      previewPrompts.value = {
        classify_prompt: typeof p.classify_prompt === 'string' ? p.classify_prompt : form.value.classify_prompt,
        price_prompt:    typeof p.price_prompt    === 'string' ? p.price_prompt    : form.value.price_prompt,
        tech_prompt:     typeof p.tech_prompt     === 'string' ? p.tech_prompt     : form.value.tech_prompt,
        default_prompt:  typeof p.default_prompt  === 'string' ? p.default_prompt  : form.value.default_prompt,
      }
      showAiPanel.value = false
      activeTab.value = '__preview__'
    } else {
      generateError.value = msg.message || '生成失败，请重试'
    }
  })
  loaded.value = true
})

onBeforeRouteLeave(() => {
  if (dirtyKeys.value.length > 0) {
    return confirm('有未保存的提示词修改，确定要离开吗？')
  }
})

function switchTab(key) {
  // only check dirty when leaving a regular editing tab (not the preview tab)
  if (activeTab.value !== '__preview__' && dirtyKeys.value.includes(activeTab.value)) {
    const label = tabs.find(t => t.key === activeTab.value)?.label ?? activeTab.value
    if (!confirm(`「${label}」有未保存的修改，确定要切换吗？`)) return
  }
  activeTab.value = key
}

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
    savedState.value[key] = form.value[key]  // clear dirty for this key
    setTimeout(() => { savedKey.value = '' }, 3000)
  } finally {
    savingKey.value = ''
  }
}

function applyPreview(key) {
  form.value[key] = previewPrompts.value[key]
  // dirtyKeys recomputes automatically (form[key] !== savedState[key])
}

function applyAllPreviews() {
  if (!previewPrompts.value) return
  tabs.forEach(t => { form.value[t.key] = previewPrompts.value[t.key] })
  previewPrompts.value = null
  generateError.value = ''
  activeTab.value = 'classify_prompt'
}

function discardPreview() {
  previewPrompts.value = null
  generateError.value = ''
  activeTab.value = 'classify_prompt'
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

.tab-dirty-dot {
  color: #f59e0b;
  font-size: 14px;
  font-weight: bold;
  margin-left: 2px;
  vertical-align: baseline;
}

.tab-preview {
  background: transparent;
  color: #7c3aed;
  border: 1px solid #7c3aed;
  font-size: 13px;
  font-weight: 500;
}

.tab-preview:hover {
  background: #f5f3ff;
}

.tab-preview.active {
  background: #7c3aed;
  color: #fff;
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
