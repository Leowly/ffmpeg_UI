<!-- src/App.vue -->
<script setup lang="ts">
import AppSidebar from './components/AppSidebar.vue'
</script>

<template>
  <div class="app-layout">
    <!-- 左侧 1/3 区域 -->
    <div class="sidebar-container">
      <AppSidebar />
    </div>
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  height: 100vh;
  gap: 16px;
  padding: 16px;
  background-color: #f0f2f5;
  box-sizing: border-box;
}

.sidebar-container {
  /* flex: 0 0 20%; 是一种更精确的写法 */
  width: 20%; /* 设置侧边栏宽度为 1/5 */
  flex-shrink: 0; /* 防止侧边栏在空间不足时被压缩 */
}
</style>
