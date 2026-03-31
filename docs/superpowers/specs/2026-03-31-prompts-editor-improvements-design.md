# 提示词编辑页面优化 设计文档

**日期：** 2026-03-31
**状态：** 已批准
**项目：** XianyuAgentPro

---

## 1. 功能概述

对 `Prompts.vue` 提示词编辑页面进行两项优化：

1. **未保存状态提示** — Tab 标题显示修改标记，切换 tab 或离开页面时拦截未保存改动
2. **AI 生成预览 Tab** — AI 生成结果进入独立预览 tab，用户逐项确认后再应用，不再直接覆盖当前内容

---

## 2. 未保存状态提示

### 2.1 数据结构

新增 `savedState` ref，在 `onMounted` 内 `form.value` 赋值后**立即**快照（`loaded.value = true` 之前）：

```js
const savedState = ref({})  // { classify_prompt: '...', price_prompt: '...', ... }
```

`dirtyKeys` 通过 computed 派生，仅计算常规 4 个 tab（不含 `__preview__`）：

```js
const dirtyKeys = computed(() =>
  tabs.filter(t => form.value[t.key] !== savedState.value[t.key]).map(t => t.key)
)
```

`onMounted` 内初始化顺序：

```js
onMounted(async () => {
  const [prompts, defaultPrompts] = await Promise.all([...])
  defaults.value = defaultPrompts
  form.value = { ...defaultPrompts, ...prompts }
  savedState.value = { ...form.value }  // ← 快照（此处！在注册 AI 监听器之前）
  window.electronAPI.onGeneratePromptsResult(...)
  loaded.value = true
})
```

### 2.2 Tab 标题标记

Tab 按钮用 `<span>` 包裹 ●，通过 CSS 类控制橙色（`color: #f59e0b`）：

```html
<button ... class="tab" :class="{ active: activeTab === tab.key }" @click="switchTab(tab.key)">
  {{ tab.label }}<span v-if="dirtyKeys.includes(tab.key)" class="tab-dirty-dot"> ●</span>
</button>
```

注意：Vue 3 模板中 computed ref 自动解包（`dirtyKeys.includes(...)`）；在 `<script>` 函数中则需 `.value`（`dirtyKeys.value.includes(...)`）。

### 2.3 切换 Tab 时拦截

`activeTab` 不再直接绑定 `@click="activeTab = tab.key"`，改为调用 `switchTab(key)`。

`switchTab` 只对常规 4 个 tab 检查 dirty；从预览 tab 切走不触发 dirty 拦截：

```js
function switchTab(key) {
  // 仅在当前 tab 是常规编辑 tab（而非预览 tab）时才检查 dirty
  if (activeTab.value !== '__preview__' && dirtyKeys.value.includes(activeTab.value)) {
    const label = tabs.find(t => t.key === activeTab.value)?.label ?? activeTab.value
    if (!confirm(`「${label}」有未保存的修改，确定要切换吗？`)) return
  }
  activeTab.value = key
}
```

### 2.4 离开页面时拦截

Vue Router 已在项目中配置（`electron/renderer/src/router/index.js`，Prompts.vue 通过 `<RouterView>` 渲染）。
在 `<script setup>` 顶部新增 import：

```js
import { onBeforeRouteLeave } from 'vue-router'
```

守卫在 `<script setup>` 顶层调用（Vue Router 自动在组件卸载时清理）：

```js
onBeforeRouteLeave(() => {
  if (dirtyKeys.value.length > 0) {
    return confirm('有未保存的提示词修改，确定要离开吗？')
  }
})
```

### 2.5 保存后清除 dirty

`save(key)` 成功后同步更新 `savedState`：

```js
savedKey.value = key
savedState.value[key] = form.value[key]  // ← 清除该 key 的 dirty
```

---

## 3. AI 生成预览 Tab

### 3.1 预览 Tab 的显示条件

新增 `previewPrompts` ref，初始为 `null`；`null` 时预览 tab 不显示：

```js
const previewPrompts = ref(null)
// null | { classify_prompt: string, price_prompt: string, tech_prompt: string, default_prompt: string }
```

模板中 tabs 渲染：常规 4 个 tab 用 `v-for="tab in tabs"` 渲染，预览 tab 用独立的条件渲染追加：

```html
<div class="tabs">
  <button v-for="tab in tabs" :key="tab.key" class="tab"
    :class="{ active: activeTab === tab.key }"
    @click="switchTab(tab.key)">
    {{ tab.label }}<span v-if="dirtyKeys.includes(tab.key)" class="tab-dirty-dot"> ●</span>
  </button>
  <!-- 预览 tab：仅在有 AI 结果时显示 -->
  <button v-if="previewPrompts !== null" key="__preview__" class="tab tab-preview"
    :class="{ active: activeTab === '__preview__' }"
    @click="switchTab('__preview__')">
    ✨ AI 预览
  </button>
</div>
```

`tabs` 常量本身不变（仍为 4 个元素）。预览 tab 的 key 为字符串 `'__preview__'`，不在 `tabs` 数组中，不参与 `dirtyKeys` 计算。

### 3.2 AI 生成完成后的行为

`onGeneratePromptsResult` 回调修改为（收到结果时验证 key 完整性）：

```js
window.electronAPI.onGeneratePromptsResult((msg) => {
  generating.value = false
  if (msg.success) {
    const p = msg.prompts || {}
    // 确保每个 key 都有字符串值，缺失时回退为当前 form 内容（不丢失）
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
```

### 3.3 预览 Tab 布局

预览 tab 内展示 4 个面板，每个面板：

```
┌──────────────────────────────────────────────────┐
│  意图分类                           [应用此项]    │
├───────────────────────┬──────────────────────────┤
│ 当前内容（只读）       │ AI 生成内容（可编辑）     │
│ 灰色背景               │ 深色背景（同编辑器样式）  │
└───────────────────────┴──────────────────────────┘
```

底部全局操作：`[全部应用]` `[放弃]`

"应用此项"按钮始终启用（用户可以重复应用）。

### 3.4 预览内容绑定

预览内容区用 `v-for="tab in tabs"` 遍历常规 4 个 tab，每个 tab 生成一个面板。右侧可编辑区直接绑定 `previewPrompts[tab.key]`（双向绑定），用户在预览中的修改实时更新 `previewPrompts`：

```html
<!-- 预览 tab 内容区（仅当 activeTab === '__preview__' 时 v-show 显示） -->
<div v-show="activeTab === '__preview__'" class="preview-area">
  <div v-for="tab in tabs" :key="tab.key" class="preview-panel">
    <div class="preview-panel-header">
      <span class="preview-panel-title">{{ tab.label }}</span>
      <button class="btn btn-sm btn-primary" @click="applyPreview(tab.key)">应用此项</button>
    </div>
    <div class="preview-panel-body">
      <!-- 左侧：当前内容只读 -->
      <textarea class="preview-readonly" readonly :value="form[tab.key]" spellcheck="false" />
      <!-- 右侧：AI 生成内容可编辑，双向绑定 previewPrompts -->
      <textarea class="preview-editable prompt-editor" v-model="previewPrompts[tab.key]" spellcheck="false" />
    </div>
  </div>
  <div class="preview-actions">
    <button class="btn btn-primary" @click="applyAllPreviews">全部应用</button>
    <button class="btn btn-secondary" @click="discardPreview">放弃</button>
  </div>
</div>
```

`applyPreview(key)` 将此时 `previewPrompts[key]`（可能已被用户修改）写入 `form`：

```js
function applyPreview(key) {
  form.value[key] = previewPrompts.value[key]
  // dirty 由 computed 自动更新（form[key] !== savedState[key]）
}
```

**全部应用：**
```js
function applyAllPreviews() {
  if (!previewPrompts.value) return
  tabs.forEach(t => { form.value[t.key] = previewPrompts.value[t.key] })
  previewPrompts.value = null
  activeTab.value = 'classify_prompt'
}
```

**放弃：**
```js
function discardPreview() {
  previewPrompts.value = null
  activeTab.value = 'classify_prompt'
}
```

应用后内容进入 `form[key]`，因 `form[key] !== savedState[key]`，dirty 自动为 `true`，tab 出现 ● 标记，提醒用户还需点保存。

### 3.5 预览 Tab 样式

- 预览 tab 按钮背景（active）：`#7c3aed`（紫色，与 AI 生成按钮一致）；文字白色
- Tab 文字：`✨ AI 预览`
- 左侧只读区（`.preview-readonly`）：`background: #f5f5f5; color: #888; resize: none`
- 右侧可编辑区（`.preview-editable`）：与现有 `.prompt-editor` 样式相同（深色背景 `#1e1e2e`，浅色文字）

---

## 4. 数据流

```
加载时：
  getPrompts() → form.value = { ...defaults, ...prompts }
               → savedState.value = { ...form.value }  ← 快照（在注册 AI 监听器之前）

编辑时：
  用户改动 textarea → form[key] 变化 → dirtyKeys 自动计算 → tab 出现 ●

保存时：
  save(key) → savePrompts({ [key]: form[key] }) → savedState[key] = form[key] → dirty 消除

AI 生成时：
  generatePrompts(chatLog) → Python 处理 → onGeneratePromptsResult
  → 校验 msg.prompts 各 key → previewPrompts = 校验后对象 → 切换到预览 tab

预览中编辑时：
  用户改动预览 textarea → previewPrompts[key] 实时更新（双向绑定）

应用预览时：
  applyPreview(key) / applyAllPreviews()
  → form[key] = previewPrompts[key]（包含用户在预览中的修改）
  → dirty 自动标记（form ≠ savedState）
  → 用户仍需手动点保存
```

---

## 5. 变更范围

**仅修改一个文件：`electron/renderer/src/views/Prompts.vue`**

- 新增 `savedState` ref 及 `dirtyKeys` computed
- `import { onBeforeRouteLeave } from 'vue-router'` 添加到 script 顶部
- `switchTab()` 函数替代直接赋值（处理 `__preview__` tab 特殊情况）
- `onBeforeRouteLeave` 守卫（Vue Router 自动管理生命周期）
- `save()` 中更新 `savedState[key]`
- `previewPrompts` ref 及相关函数（`applyPreview`、`applyAllPreviews`、`discardPreview`）
- 模板：
  - tab 标题 dirty 标记（`.tab-dirty-dot` span）
  - 预览 tab 按钮（条件渲染，独立于 `v-for` 循环）
  - 预览内容面板（4 个双栏面板 + 底部全局操作）
- 样式：`.tab-dirty-dot`、`.tab-preview`、`.preview-panel`、`.preview-readonly`、`.preview-editable`

无需修改后端（`ipcHandlers.js`、`dbManager.js`、Python）。

---

## 6. 关键约束

- **应用预览后不自动保存**：应用 = 填入编辑器，用户需手动点"保存"，保持与现有保存流程一致
- **预览内容可编辑且双向绑定**：右侧 AI 生成区直接 `v-model="previewPrompts[tab.key]"`，用户修改立即反映，`applyPreview` 时取用已修改后的值
- **AI 结果 key 缺失时安全降级**：若后端未返回某 key，预览中对应区域显示当前 form 内容（不丢失用户数据）
- **`__preview__` 不参与 dirty 计算**：`dirtyKeys` 仅基于 `tabs`（4 个常规 tab），切换出预览 tab 不触发 dirty 确认
- **`onGeneratePromptsResult` 无 cleanup**：现有监听器在 `onMounted` 注册但无 `onUnmounted` 清理（预存 bug），本次不修复此预存问题（超出范围）
- **`onBeforeRouteLeave` 生命周期**：该守卫由 Vue Router 在组件卸载时自动清理，无需手动 `onUnmounted` 处理
