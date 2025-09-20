<!-- src/App.vue -->
<script setup lang="ts">
import AppSidebar from './components/AppSidebar.vue'
import SingleFileWorkspace from './components/SingleFileWorkspace.vue';
</script>

<template>
  <div class="app-layout">
    <div class="sidebar">
      <AppSidebar />
    </div>
    <main class="main-content">
      <!-- 👇 2. 在这里使用新组件 -->
      <SingleFileWorkspace />
    </main>
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  /* 👇 默认是横向排列 */
  flex-direction: row;
  height: 100vh;
  width: 100vw;
  background-color: #f0f2f5;
  overflow: hidden; /* 防止在小屏幕上出现双滚动条 */
}

.sidebar {
  width: 350px;
  min-width: 300px;
  background-color: #fff;
  border-right: 1px solid #d9d9d9;
  padding: 16px;
  /* 👇 允许侧边栏自身滚动 */
  overflow-y: auto;
  flex-shrink: 0; /* 防止侧边栏被挤压 */
}

.main-content {
  flex-grow: 1;
  padding: 24px;
  overflow-y: auto; /* 允许主内容区自身滚动 */
}

/* --- 👇 响应式布局的核心 --- */
/* 当屏幕宽度小于等于 768px 时 */
@media (max-width: 768px) {
  .app-layout {
    /* 1. 将主容器变为纵向排列 */
    flex-direction: column;
  }

  .sidebar {
    /* 2. 宽度占满，高度自动，并设置一个最大高度 */
    width: 100%;
    height: auto;
    max-height: 40vh; /* 例如，最大高度为屏幕的 40% */
    border-right: none; /* 移除右边框 */
    border-bottom: 1px solid #d9d9d9; /* 添加下边框 */
    min-width: unset; /* 取消最小宽度限制 */
  }

  .main-content {
    /* 3. 主内容区将自然地占据剩余空间 */
    height: 100%;
  }
}
</style>
