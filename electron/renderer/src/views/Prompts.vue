<template>
  <div class="page">
    <div class="page-header">
      <h1 class="page-title">提示词编辑</h1>
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
        </div>
      </div>

      <div class="form-actions">
        <button class="btn btn-primary" :disabled="saving" @click="save">
          {{ saving ? '保存中...' : '保存提示词' }}
        </button>
        <span v-if="saved" class="save-ok">✓ 已保存，机器人将自动重载</span>
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
const saving = ref(false)
const saved = ref(false)

onMounted(async () => {
  form.value = await window.electronAPI.getPrompts()
  // Store originals as soft defaults (before any edits this session)
  defaults.value = { ...form.value }
  loaded.value = true
})

function resetPrompt(key) {
  if (confirm(`确定要恢复 "${tabs.find(t => t.key === key)?.label}" 提示词为当前默认内容吗？`)) {
    form.value[key] = defaults.value[key] || ''
  }
}

async function save() {
  saving.value = true
  saved.value = false
  try {
    await window.electronAPI.savePrompts(form.value)
    saved.value = true
    defaults.value = { ...form.value }
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
</style>
