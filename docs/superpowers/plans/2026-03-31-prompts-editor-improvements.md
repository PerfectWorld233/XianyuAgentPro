# Prompts Editor Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add unsaved-state dirty tracking with tab markers and a navigation guard, plus an AI-generated preview tab so users can review and selectively apply AI results before they overwrite the editor.

**Architecture:** All changes are confined to a single Vue 3 SFC — `electron/renderer/src/views/Prompts.vue`. No backend changes are required. Dirty tracking uses a `savedState` snapshot ref + `dirtyKeys` computed; the preview flow adds a `previewPrompts` ref and a ghost "✨ AI 预览" tab that only appears when AI results arrive.

**Tech Stack:** Vue 3 `<script setup>`, Vue Router `onBeforeRouteLeave`, Electron `contextBridge` / `ipcRenderer` (already wired), no new dependencies.

---

## File Structure

Only one file is modified:

| File | Change |
|------|--------|
| `electron/renderer/src/views/Prompts.vue` | Add dirty tracking, switchTab guard, route-leave guard, preview tab, preview panels, new styles |

---

## Task 1: Dirty-state tracking — refs, computed, and onMounted snapshot

**Files:**
- Modify: `electron/renderer/src/views/Prompts.vue`

**Background:** The current `<script setup>` imports only `{ ref, onMounted }` from `'vue'`. We need to add `computed` to that import, add `savedState` + `dirtyKeys`, and snapshot `form` in `onMounted` after it is populated.

- [ ] **Step 1: Open the file and locate the script block**

  Read `electron/renderer/src/views/Prompts.vue`. Confirm the script starts with:
  ```js
  import { ref, onMounted } from 'vue'
  ```
  and that `onMounted` assigns `form.value = { ...defaultPrompts, ...prompts }` then sets `loaded.value = true`.

- [ ] **Step 2: Add `computed` to the vue import and add new refs**

  Replace:
  ```js
  import { ref, onMounted } from 'vue'
  ```
  with:
  ```js
  import { ref, computed, onMounted } from 'vue'
  import { onBeforeRouteLeave } from 'vue-router'
  ```

  After the existing `const showAiPanel = ref(false)` line, add:
  ```js
  const savedState = ref({})   // snapshot of form at last save / initial load
  const previewPrompts = ref(null)  // null | { classify_prompt, price_prompt, tech_prompt, default_prompt }

  // dirtyKeys: which of the 4 regular tabs have unsaved edits
  const dirtyKeys = computed(() =>
    tabs.filter(t => form.value[t.key] !== savedState.value[t.key]).map(t => t.key)
  )
  ```

- [ ] **Step 3: Snapshot savedState in onMounted (after form is set, before listener)**

  Current `onMounted` body:
  ```js
  const [prompts, defaultPrompts] = await Promise.all([
    window.electronAPI.getPrompts(),
    window.electronAPI.getDefaultPrompts(),
  ])
  defaults.value = defaultPrompts
  form.value = { ...defaultPrompts, ...prompts }
  window.electronAPI.onGeneratePromptsResult((msg) => {
    ...
  })
  loaded.value = true
  ```

  Add the snapshot line **immediately after** `form.value = { ...defaultPrompts, ...prompts }` and **before** `window.electronAPI.onGeneratePromptsResult(...)`:
  ```js
  savedState.value = { ...form.value }  // snapshot — must be before AI listener
  ```

- [ ] **Step 4: Add the route-leave guard after the onMounted block**

  After the closing `})` of `onMounted`, add:
  ```js
  onBeforeRouteLeave(() => {
    if (dirtyKeys.value.length > 0) {
      return confirm('有未保存的提示词修改，确定要离开吗？')
    }
  })
  ```

- [ ] **Step 5: Manual verification**

  Open the file and confirm:
  - `import { ref, computed, onMounted } from 'vue'` ✓
  - `import { onBeforeRouteLeave } from 'vue-router'` ✓
  - `savedState` and `previewPrompts` refs declared ✓
  - `dirtyKeys` computed declared ✓
  - `savedState.value = { ...form.value }` appears after `form.value = ...` and before `onGeneratePromptsResult` ✓
  - `onBeforeRouteLeave` guard present after `onMounted` ✓

- [ ] **Step 6: Commit**

  ```bash
  git add electron/renderer/src/views/Prompts.vue
  git commit -m "feat(prompts): add savedState snapshot and dirtyKeys computed"
  ```

---

## Task 2: switchTab function + update save() to clear dirty

**Files:**
- Modify: `electron/renderer/src/views/Prompts.vue`

**Background:** Tab clicks currently do `@click="activeTab = tab.key"`. We need a `switchTab(key)` function that intercepts when leaving a dirty regular tab, and the existing `save(key)` function needs to update `savedState` on success.

- [ ] **Step 1: Add switchTab function**

  Add the following function after `onBeforeRouteLeave(...)` (before `function resetPrompt`):
  ```js
  function switchTab(key) {
    // only check dirty when leaving a regular editing tab (not the preview tab)
    if (activeTab.value !== '__preview__' && dirtyKeys.value.includes(activeTab.value)) {
      const label = tabs.find(t => t.key === activeTab.value)?.label ?? activeTab.value
      if (!confirm(`「${label}」有未保存的修改，确定要切换吗？`)) return
    }
    activeTab.value = key
  }
  ```

- [ ] **Step 2: Update save() to update savedState on success**

  Locate the `save(key)` function. It currently contains:
  ```js
  await window.electronAPI.savePrompts({ [key]: form.value[key] })
  savedKey.value = key
  setTimeout(() => { savedKey.value = '' }, 3000)
  ```

  After `savedKey.value = key`, add:
  ```js
  savedState.value[key] = form.value[key]  // clear dirty for this key
  ```

  The block should read:
  ```js
  await window.electronAPI.savePrompts({ [key]: form.value[key] })
  savedKey.value = key
  savedState.value[key] = form.value[key]  // clear dirty for this key
  setTimeout(() => { savedKey.value = '' }, 3000)
  ```

- [ ] **Step 3: Manual verification**

  Read the file and confirm:
  - `switchTab(key)` function exists with the `__preview__` guard and `confirm()` dialog ✓
  - `savedState.value[key] = form.value[key]` line present inside `save()` after `savedKey.value = key` ✓

- [ ] **Step 4: Commit**

  ```bash
  git add electron/renderer/src/views/Prompts.vue
  git commit -m "feat(prompts): add switchTab with dirty guard and clear savedState on save"
  ```

---

## Task 3: Add preview-related JS functions

**Files:**
- Modify: `electron/renderer/src/views/Prompts.vue`

**Background:** Three new functions needed: `applyPreview(key)`, `applyAllPreviews()`, `discardPreview()`. Also update the `onGeneratePromptsResult` callback to route results to `previewPrompts` instead of directly into `form`.

- [ ] **Step 1: Update onGeneratePromptsResult callback in onMounted**

  Locate the existing callback in `onMounted`:
  ```js
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
  ```

  Replace the entire callback body with:
  ```js
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
  ```

- [ ] **Step 2: Add applyPreview, applyAllPreviews, discardPreview functions**

  Add these three functions after `async function save(key)`:
  ```js
  function applyPreview(key) {
    form.value[key] = previewPrompts.value[key]
    // dirtyKeys recomputes automatically (form[key] !== savedState[key])
  }

  function applyAllPreviews() {
    if (!previewPrompts.value) return
    tabs.forEach(t => { form.value[t.key] = previewPrompts.value[t.key] })
    previewPrompts.value = null
    activeTab.value = 'classify_prompt'
  }

  function discardPreview() {
    previewPrompts.value = null
    activeTab.value = 'classify_prompt'
  }
  ```

- [ ] **Step 3: Manual verification**

  Read the script section and confirm:
  - `onGeneratePromptsResult` callback sets `previewPrompts.value = { ... }` and goes to `'__preview__'` tab ✓
  - `applyPreview`, `applyAllPreviews`, `discardPreview` all present ✓
  - `applyAllPreviews` has the `if (!previewPrompts.value) return` guard ✓

- [ ] **Step 4: Commit**

  ```bash
  git add electron/renderer/src/views/Prompts.vue
  git commit -m "feat(prompts): add preview apply/discard functions and reroute AI result to preview"
  ```

---

## Task 4: Update the template — dirty dot markers + switchTab + preview tab button

**Files:**
- Modify: `electron/renderer/src/views/Prompts.vue`

**Background:** Update the tabs row in the template: use `switchTab` in `@click`, add the dirty-dot `<span>`, and append the conditional "✨ AI 预览" button.

- [ ] **Step 1: Update the tabs v-for buttons**

  Locate the current tabs section:
  ```html
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
  ```

  Replace with:
  ```html
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
  ```

  Note: `dirtyKeys` is a computed ref — in templates, refs auto-unwrap, so `dirtyKeys.includes(tab.key)` (no `.value`) is correct.

- [ ] **Step 2: Manual verification**

  Read the template and confirm:
  - Tab buttons use `@click="switchTab(tab.key)"` (not `activeTab = tab.key`) ✓
  - Each tab button has the dirty-dot span `v-if="dirtyKeys.includes(tab.key)"` ✓
  - Preview tab button present with `v-if="previewPrompts !== null"` and `class="tab tab-preview"` ✓

- [ ] **Step 3: Commit**

  ```bash
  git add electron/renderer/src/views/Prompts.vue
  git commit -m "feat(prompts): update tab buttons with switchTab and dirty-dot markers"
  ```

---

## Task 5: Add the preview content area to the template

**Files:**
- Modify: `electron/renderer/src/views/Prompts.vue`

**Background:** Add the preview panels section inside `.prompts-body`, after the existing `.editor-area` div. The preview area uses `v-show` and iterates over `tabs` to render 4 double-column panels.

- [ ] **Step 1: Locate the insertion point**

  In the template, find the closing `</div>` of `.editor-area`:
  ```html
      </div>
    </div>  <!-- end .editor-area -->
  </div>    <!-- end .prompts-body -->
  ```

- [ ] **Step 2: Insert the preview area before the closing of `.prompts-body`**

  After `</div>` (end of `.editor-area`) and before the `</div>` that closes `.prompts-body`, insert:
  ```html
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
  ```

  Note: `v-model="previewPrompts[tab.key]"` uses template auto-unwrap — no `.value` needed.

- [ ] **Step 3: Manual verification**

  Read the template and confirm:
  - `<div v-show="activeTab === '__preview__'" class="preview-area">` present inside `.prompts-body` ✓
  - `v-for="tab in tabs"` on `.preview-panel` ✓
  - Left textarea uses `:value="form[tab.key]"` (read-only) ✓
  - Right textarea uses `v-model="previewPrompts[tab.key]"` (editable) ✓
  - "全部应用" and "放弃" buttons in `.preview-actions` ✓

- [ ] **Step 4: Commit**

  ```bash
  git add electron/renderer/src/views/Prompts.vue
  git commit -m "feat(prompts): add AI preview content panels"
  ```

---

## Task 6: Add new CSS styles

**Files:**
- Modify: `electron/renderer/src/views/Prompts.vue`

**Background:** Add styles for dirty-dot, preview tab button, preview panels, and preview textareas. Append to the existing `<style scoped>` block.

- [ ] **Step 1: Append styles to the `<style scoped>` block**

  Locate the closing `</style>` tag. Before it, append:

  ```css
  /* --- dirty-state indicator --- */
  .tab-dirty-dot {
    color: #f59e0b;
  }

  /* --- preview tab button --- */
  .tab-preview {
    background: transparent;
    color: #7c3aed;
    border: 1px solid #7c3aed;
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

  /* --- preview area --- */
  .preview-area {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 12px;
    overflow-y: auto;
  }

  .preview-panel {
    display: flex;
    flex-direction: column;
    gap: 6px;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 10px 12px;
    background: #fff;
  }

  .preview-panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .preview-panel-title {
    font-size: 13px;
    font-weight: 600;
    color: #1e2030;
  }

  .preview-panel-body {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    height: 160px;
  }

  .preview-readonly {
    resize: none;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 13px;
    line-height: 1.6;
    background: #f5f5f5;
    color: #888;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 8px;
    cursor: default;
  }

  /* preview-editable inherits .prompt-editor styles via the shared class */

  .preview-actions {
    display: flex;
    gap: 12px;
    padding-top: 4px;
  }

  .btn-secondary {
    background: #e2e8f0;
    color: #475569;
    padding: 9px 24px;
    font-weight: 500;
  }

  .btn-secondary:hover {
    background: #cbd5e1;
  }

  .btn-sm {
    padding: 5px 14px;
    font-size: 12px;
  }
  ```

- [ ] **Step 2: Manual verification**

  Read the style block end and confirm all new CSS classes are present:
  `.tab-dirty-dot`, `.tab-preview`, `.preview-area`, `.preview-panel`, `.preview-panel-header`, `.preview-panel-title`, `.preview-panel-body`, `.preview-readonly`, `.preview-actions`, `.btn-secondary`, `.btn-sm` ✓

- [ ] **Step 3: Commit**

  ```bash
  git add electron/renderer/src/views/Prompts.vue
  git commit -m "feat(prompts): add styles for dirty dot, preview tab, and preview panels"
  ```

---

## Task 7: Integration smoke test (manual)

**Files:** None changed — this is a manual validation step.

**Background:** The app is Electron — there are no automated unit tests for Vue components. Verify the two features end-to-end in the running app.

- [ ] **Step 1: Start the dev app**

  ```bash
  cd electron
  npm run dev
  ```

  Wait for the Electron window to open and navigate to "提示词编辑".

- [ ] **Step 2: Verify dirty tracking**

  1. Edit any text in the "意图分类" textarea
  2. Confirm the tab label now shows `意图分类 ●` with an orange dot
  3. Click a different tab — confirm a confirm dialog appears asking "「意图分类」有未保存的修改，确定要切换吗？"
  4. Cancel — confirm you stay on "意图分类"
  5. Click Save — confirm the ● disappears
  6. Navigate away (click a different sidebar item) with a dirty tab — confirm the leave guard fires
  7. Cancel the leave guard — confirm you stay on the page

- [ ] **Step 3: Verify AI preview tab**

  1. Open "AI 生成提示词" panel
  2. Paste any short chat log and click "AI 生成"
  3. After generation completes, confirm "✨ AI 预览" tab appears and becomes active
  4. Confirm each of the 4 panels shows current content (left, gray) and AI content (right, dark)
  5. Edit the right-side text of one panel to verify it's editable
  6. Click "应用此项" on one panel — confirm the corresponding tab now has ● dirty marker
  7. Click "全部应用" — confirm all 4 tabs get ● dirty markers, preview tab disappears, switches to "意图分类"
  8. Trigger AI generation again; click "放弃" — confirm preview tab disappears, reverts to "意图分类"

- [ ] **Step 4: Confirm no regressions**

  1. Save all dirty tabs — confirm ● markers disappear
  2. "恢复默认" still works for each tab
  3. Normal tab switching without dirty state works without confirm dialog

---
