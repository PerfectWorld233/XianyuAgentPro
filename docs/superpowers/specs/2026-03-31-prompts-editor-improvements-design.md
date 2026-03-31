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

新增 `savedState` ref，在加载完成时记录每个 key 的初始值（来自数据库）：

```js
const savedState = ref({})  // { classify_prompt: '...', price_prompt: '...', ... }
```

`dirty` 通过 computed 派生：

```js
const dirtyKeys = computed(() =>
  tabs.filter(t => form.value[t.key] !== savedState.value[t.key]).map(t => t.key)
)
```

### 2.2 Tab 标题标记

Tab 按钮标题：`{{ tab.label }}{{ dirtyKeys.includes(tab.key) ? ' ●' : '' }}`

● 的颜色：`color: #f59e0b`（橙色），通过 `.tab.dirty` 修饰符控制。

### 2.3 切换 Tab 时拦截

`activeTab` 不再直接绑定 `@click="activeTab = tab.key"`，改为调用 `switchTab(key)`：

```js
function switchTab(key) {
  if (dirtyKeys.value.includes(activeTab.value)) {
    const label = tabs.find(t => t.key === activeTab.value)?.label
    if (!confirm(`「${label}」有未保存的修改，确定要切换吗？`)) return
  }
  activeTab.value = key
}
```

### 2.4 离开页面时拦截

使用 Vue Router 的 `onBeforeRouteLeave` 守卫：

```js
import { onBeforeRouteLeave } from 'vue-router'

onBeforeRouteLeave(() => {
  if (dirtyKeys.value.length > 0) {
    return confirm('有未保存的提示词修改，确定要离开吗？')
  }
})
```

### 2.5 保存后清除 dirty

`save(key)` 成功后同步更新 `savedState`：

```js
savedState.value[key] = form.value[key]
```

---

## 3. AI 生成预览 Tab

### 3.1 预览 Tab 的显示条件

新增 `previewPrompts` ref，初始为 `null`，有值时预览 tab 显示：

```js
const previewPrompts = ref(null)  // null | { classify_prompt, price_prompt, tech_prompt, default_prompt }
```

Tabs 渲染逻辑：常规 4 个 tab 后，当 `previewPrompts !== null` 时追加"✨ AI 预览"幽灵 tab。

### 3.2 AI 生成完成后的行为

`onGeneratePromptsResult` 回调修改为：

```js
window.electronAPI.onGeneratePromptsResult((msg) => {
  generating.value = false
  if (msg.success) {
    previewPrompts.value = msg.prompts   // 存入预览，不直接写入 form
    showAiPanel.value = false
    activeTab.value = '__preview__'      // 切换到预览 tab
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
│ 灰色背景               │ 白色背景                  │
└───────────────────────┴──────────────────────────┘
```

底部全局操作：`[全部应用]` `[放弃]`

### 3.4 应用逻辑

**应用单项：**
```js
function applyPreview(key) {
  form.value[key] = previewPrompts.value[key]
  // dirty 由 computed 自动更新（form[key] !== savedState[key]）
}
```

**全部应用：**
```js
function applyAllPreviews() {
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

- 边框/Tab 背景：`#7c3aed`（紫色，与 AI 生成按钮一致）
- Tab 文字：`✨ AI 预览`
- 左侧只读区：`background: #f5f5f5; color: #888`
- 右侧可编辑区：与现有 `.prompt-editor` 样式一致

---

## 4. 数据流

```
加载时：
  getPrompts() → form.value = { ...defaults, ...prompts }
               → savedState.value = { ...form.value }  ← 快照

编辑时：
  用户改动 textarea → form[key] 变化 → dirtyKeys 自动计算 → tab 出现 ●

保存时：
  save(key) → savePrompts({ [key]: form[key] }) → savedState[key] = form[key] → dirty 消除

AI 生成时：
  generatePrompts(chatLog) → Python 处理 → onGeneratePromptsResult
  → previewPrompts = msg.prompts → 切换到预览 tab

应用预览时：
  applyPreview(key) / applyAllPreviews()
  → form[key] = previewPrompts[key]
  → dirty 自动标记（form ≠ savedState）
  → 用户仍需手动点保存
```

---

## 5. 变更范围

**仅修改一个文件：`electron/renderer/src/views/Prompts.vue`**

- 新增 `savedState` ref 及 `dirtyKeys` computed
- `switchTab()` 函数替代直接赋值
- `onBeforeRouteLeave` 守卫
- `save()` 中更新 `savedState`
- `previewPrompts` ref 及相关函数（`applyPreview`、`applyAllPreviews`、`discardPreview`）
- 模板：tab 标题 dirty 标记、预览 tab 渲染、预览内容面板
- 样式：`.tab-dirty-dot`、`.preview-tab`、`.preview-pane`、`.preview-readonly`

无需修改后端（`ipcHandlers.js`、`dbManager.js`、Python）。

---

## 6. 关键约束

- **应用预览后不自动保存**：应用 = 填入编辑器，用户需手动点"保存"，保持与现有保存流程一致
- **预览内容可编辑**：右侧 AI 生成区支持用户在确认前微调内容
- **`onGeneratePromptsResult` 无 cleanup**：现有监听器在 `onMounted` 注册但无 `onUnmounted` 清理（预存 bug），本次不引入新的监听器问题，但也不修复此预存问题（超出范围）
