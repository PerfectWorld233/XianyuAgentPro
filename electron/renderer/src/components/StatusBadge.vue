<template>
  <span class="status-badge" :class="running ? 'running' : 'stopped'">
    <span class="dot"></span>
    {{ running ? '运行中' : '已停止' }}
  </span>
</template>

<script setup>
defineProps({
  running: {
    type: Boolean,
    default: false,
  },
})
</script>

<style scoped>
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 500;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.running {
  background: #d1fae5;
  color: #065f46;
}

.running .dot {
  background: #10b981;
  animation: pulse 1.5s infinite;
}

.stopped {
  background: #fee2e2;
  color: #991b1b;
}

.stopped .dot {
  background: #ef4444;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
</style>
