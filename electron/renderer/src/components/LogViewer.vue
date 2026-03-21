<template>
  <div ref="containerRef" class="log-viewer">
    <div
      v-for="entry in logs"
      :key="entry.id"
      class="log-line"
      :class="`level-${entry.level}`"
    >
      <span class="log-time">{{ formatTime(entry.time) }}</span>
      <span class="log-level">{{ entry.level?.toUpperCase() }}</span>
      <span class="log-msg">{{ entry.message }}</span>
    </div>
    <div v-if="logs.length === 0" class="log-empty">暂无日志</div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'

const props = defineProps({
  logs: {
    type: Array,
    default: () => [],
  },
})

const containerRef = ref(null)
let autoScroll = true

function formatTime(iso) {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    return d.toLocaleTimeString('zh-CN', { hour12: false })
  } catch {
    return ''
  }
}

function onScroll() {
  if (!containerRef.value) return
  const el = containerRef.value
  const threshold = 60
  autoScroll = el.scrollHeight - el.scrollTop - el.clientHeight < threshold
}

watch(
  () => props.logs.length,
  () => {
    if (autoScroll) {
      nextTick(() => {
        if (containerRef.value) {
          containerRef.value.scrollTop = containerRef.value.scrollHeight
        }
      })
    }
  }
)
</script>

<style scoped>
.log-viewer {
  flex: 1;
  overflow-y: auto;
  background: #1e1e2e;
  padding: 12px;
  font-family: 'Consolas', 'Courier New', monospace;
  font-size: 12.5px;
  line-height: 1.7;
  border-radius: 8px;
}

.log-line {
  display: flex;
  gap: 8px;
  padding: 1px 0;
}

.log-time {
  color: #6c7086;
  flex-shrink: 0;
  width: 80px;
}

.log-level {
  flex-shrink: 0;
  width: 52px;
  font-weight: 600;
  text-align: center;
}

.log-msg {
  color: #cdd6f4;
  word-break: break-all;
}

.level-debug .log-level { color: #6c7086; }
.level-info .log-level  { color: #89b4fa; }
.level-warning .log-level { color: #f9e2af; }
.level-error .log-level   { color: #f38ba8; }

.level-error .log-msg { color: #f38ba8; }
.level-warning .log-msg { color: #f9e2af; }

.log-empty {
  color: #6c7086;
  text-align: center;
  margin-top: 40px;
}
</style>
