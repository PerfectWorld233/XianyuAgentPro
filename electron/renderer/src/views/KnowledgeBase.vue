<template>
  <div class="knowledge-page">
    <div class="page-header">
      <h2>知识库管理</h2>
      <button class="btn-primary" @click="openAddModal">+ 新增条目</button>
    </div>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <select v-model="filterItemId">
        <option value="">全部</option>
        <option value="__global__">全局通用</option>
      </select>
      <input v-model="searchKeyword" placeholder="搜索关键词..." class="search-input" />
    </div>

    <!-- 知识条目列表 -->
    <table class="knowledge-table">
      <thead>
        <tr>
          <th>范围</th>
          <th>问题</th>
          <th>答案预览</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="entry in filteredEntries" :key="entry.id">
          <td class="scope-cell">{{ entry.item_id ? `#${entry.item_id}` : '全局' }}</td>
          <td>{{ entry.question }}</td>
          <td class="answer-preview">{{ entry.answer.slice(0, 40) }}{{ entry.answer.length > 40 ? '...' : '' }}</td>
          <td class="action-cell">
            <button class="btn-sm" @click="openEditModal(entry)">编辑</button>
            <button class="btn-sm btn-danger" @click="deleteEntry(entry.id)">删除</button>
          </td>
        </tr>
        <tr v-if="filteredEntries.length === 0">
          <td colspan="4" class="empty-tip">暂无知识条目</td>
        </tr>
      </tbody>
    </table>

    <!-- AI 生成按钮 -->
    <div class="ai-actions">
      <button class="btn-secondary" @click="triggerGenerateFromImage" :disabled="isGenerating">
        {{ isGenerating ? 'AI 生成中...' : 'AI 从图片生成' }}
      </button>
      <button class="btn-secondary" @click="showChatPanel = true" :disabled="isGenerating">
        AI 从聊天记录生成
      </button>
    </div>

    <!-- 聊天记录输入面板 -->
    <div v-if="showChatPanel" class="chat-panel">
      <h3>从聊天记录生成知识</h3>
      <textarea v-model="chatText" placeholder="粘贴聊天记录..." rows="8"></textarea>
      <div class="panel-actions">
        <button class="btn-primary" @click="generateFromChat" :disabled="!chatText.trim() || isGenerating">生成</button>
        <button class="btn-secondary" @click="showChatPanel = false">取消</button>
      </div>
    </div>

    <!-- AI 生成结果审核面板 -->
    <div v-if="pendingEntries.length > 0" class="review-panel">
      <h3>AI 生成结果（请审核后入库）</h3>
      <div v-for="(entry, idx) in pendingEntries" :key="idx" class="pending-entry">
        <input type="checkbox" v-model="entry.selected" />
        <div class="qa-content">
          <div><strong>Q:</strong> {{ entry.question }}</div>
          <div><strong>A:</strong> {{ entry.answer }}</div>
        </div>
      </div>
      <div class="review-actions">
        <select v-model="pendingItemId" class="item-id-select">
          <option value="">全局通用</option>
        </select>
        <button class="btn-primary" @click="confirmBatchAdd" :disabled="!hasSelectedPending">
          确认入库（{{ selectedPendingCount }} 条）
        </button>
        <button class="btn-secondary" @click="pendingEntries = []">放弃</button>
      </div>
    </div>

    <!-- 新增/编辑 弹窗 -->
    <div v-if="showModal" class="modal-overlay" @click.self="closeModal">
      <div class="modal">
        <h3>{{ editingEntry ? '编辑条目' : '新增条目' }}</h3>
        <label>范围（商品 ID，留空为全局）</label>
        <input v-model="formItemId" placeholder="可选，如 123456" />
        <label>问题</label>
        <input v-model="formQuestion" placeholder="买家可能会问的问题" />
        <label>答案</label>
        <textarea v-model="formAnswer" rows="4" placeholder="对应的回答"></textarea>
        <div class="modal-actions">
          <button class="btn-primary" @click="saveEntry" :disabled="!formQuestion.trim() || !formAnswer.trim()">保存</button>
          <button class="btn-secondary" @click="closeModal">取消</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

const entries = ref([])
const filterItemId = ref('')
const searchKeyword = ref('')
const isGenerating = ref(false)
const showChatPanel = ref(false)
const chatText = ref('')
const pendingEntries = ref([])
const pendingItemId = ref('')
const showModal = ref(false)
const editingEntry = ref(null)
const formItemId = ref('')
const formQuestion = ref('')
const formAnswer = ref('')

const filteredEntries = computed(() => {
  let list = entries.value
  if (filterItemId.value === '__global__') {
    list = list.filter(e => !e.item_id)
  } else if (filterItemId.value) {
    list = list.filter(e => e.item_id === filterItemId.value)
  }
  if (searchKeyword.value.trim()) {
    const kw = searchKeyword.value.toLowerCase()
    list = list.filter(e =>
      e.question.toLowerCase().includes(kw) || e.answer.toLowerCase().includes(kw)
    )
  }
  return list
})

const hasSelectedPending = computed(() => pendingEntries.value.some(e => e.selected))
const selectedPendingCount = computed(() => pendingEntries.value.filter(e => e.selected).length)

async function loadEntries() {
  entries.value = await window.electronAPI.listKnowledge()
}

function openAddModal() {
  editingEntry.value = null
  formItemId.value = ''
  formQuestion.value = ''
  formAnswer.value = ''
  showModal.value = true
}

function openEditModal(entry) {
  editingEntry.value = entry
  formItemId.value = entry.item_id || ''
  formQuestion.value = entry.question
  formAnswer.value = entry.answer
  showModal.value = true
}

function closeModal() {
  showModal.value = false
}

async function saveEntry() {
  const itemId = formItemId.value.trim() || undefined
  if (editingEntry.value) {
    await window.electronAPI.updateKnowledge({
      id: editingEntry.value.id,
      question: formQuestion.value,
      answer: formAnswer.value,
    })
  } else {
    await window.electronAPI.addKnowledge({
      question: formQuestion.value,
      answer: formAnswer.value,
      itemId,
    })
  }
  closeModal()
  await loadEntries()
}

async function deleteEntry(id) {
  if (!confirm('确认删除此条目？')) return
  await window.electronAPI.deleteKnowledge({ id })
  await loadEntries()
}

async function triggerGenerateFromImage() {
  const result = await window.electronAPI.generateFromImage()
  if (result?.canceled) return
  isGenerating.value = true
}

async function generateFromChat() {
  if (!chatText.value.trim()) return
  await window.electronAPI.generateFromChat({ chatText: chatText.value })
  isGenerating.value = true
  showChatPanel.value = false
}

async function confirmBatchAdd() {
  const selected = pendingEntries.value.filter(e => e.selected)
  await window.electronAPI.batchAddKnowledge({
    entries: selected.map(e => ({ question: e.question, answer: e.answer })),
    itemId: pendingItemId.value || undefined,
  })
  pendingEntries.value = []
  await loadEntries()
}

// 监听 AI 生成结果广播
onMounted(async () => {
  await loadEntries()
  window.electronAPI.onKnowledgeGenerateResult((msg) => {
    isGenerating.value = false
    pendingEntries.value = (msg.data || []).map(e => ({ ...e, selected: true }))
  })
  window.electronAPI.onKnowledgeGenerateError((msg) => {
    isGenerating.value = false
    alert(`AI 生成失败：${msg.message}`)
  })
})

onUnmounted(() => {
  // 清理 IPC 监听器，防止页面切换后的内存泄漏
  window.electronAPI.removeAllKnowledgeListeners?.()
})
</script>

<style scoped>
.knowledge-page { padding: 24px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.filter-bar { display: flex; gap: 12px; margin-bottom: 16px; }
.search-input { flex: 1; padding: 6px 10px; border: 1px solid #ddd; border-radius: 4px; }
.knowledge-table { width: 100%; border-collapse: collapse; margin-bottom: 16px; }
.knowledge-table th, .knowledge-table td { padding: 10px 12px; border-bottom: 1px solid #eee; text-align: left; }
.knowledge-table th { background: #f5f5f5; font-weight: 600; }
.scope-cell { white-space: nowrap; color: #666; }
.answer-preview { color: #888; font-size: 13px; }
.action-cell { white-space: nowrap; }
.empty-tip { color: #aaa; text-align: center; padding: 24px; }
.ai-actions { display: flex; gap: 12px; margin-bottom: 16px; }
.chat-panel, .review-panel { background: #f9f9f9; border: 1px solid #ddd; border-radius: 6px; padding: 16px; margin-bottom: 16px; }
.chat-panel textarea { width: 100%; margin: 8px 0; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
.panel-actions, .review-actions, .modal-actions { display: flex; gap: 8px; margin-top: 12px; }
.pending-entry { display: flex; align-items: flex-start; gap: 10px; margin-bottom: 12px; }
.qa-content { flex: 1; }
.item-id-select { padding: 6px; border: 1px solid #ddd; border-radius: 4px; }
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal { background: #fff; border-radius: 8px; padding: 24px; min-width: 400px; max-width: 560px; width: 100%; }
.modal h3 { margin-top: 0; }
.modal label { display: block; margin: 12px 0 4px; font-size: 13px; color: #555; }
.modal input, .modal textarea { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
.btn-primary { padding: 8px 16px; background: #1677ff; color: #fff; border: none; border-radius: 4px; cursor: pointer; }
.btn-primary:disabled { background: #a0c4ff; cursor: not-allowed; }
.btn-secondary { padding: 8px 16px; background: #f0f0f0; border: 1px solid #ddd; border-radius: 4px; cursor: pointer; }
.btn-sm { padding: 4px 10px; font-size: 12px; background: #f0f0f0; border: 1px solid #ddd; border-radius: 4px; cursor: pointer; margin-right: 4px; }
.btn-danger { color: #ff4d4f; }
</style>
