<!-- src/App.vue -->
<script setup lang="ts">
import { onMounted, watch } from 'vue';
import AppSidebar from './components/AppSidebar.vue'
import SingleFileWorkspace from './components/SingleFileWorkspace.vue';
import AuthForm from './components/AuthForm.vue';
import { useAuthStore } from './stores/authStore';
import { useFileStore } from './stores/fileStore';
import { LogoutOutlined } from '@ant-design/icons-vue';

const authStore = useAuthStore();
const fileStore = useFileStore();

onMounted(() => {
  // 尝试在应用加载时获取当前用户，以验证token并设置isLoggedIn状态
  authStore.fetchCurrentUser();
});

// 监听登录状态变化，当用户登录后同步文件列表
watch(() => authStore.isLoggedIn, (newVal) => {
  if (newVal) {
    fileStore.fetchFileList();
  }
}, { immediate: true });
</script>

<template>
  <AuthForm v-if="!authStore.isLoggedIn" />
  <div v-else class="app-layout">
    <div class="sidebar">
      <AppSidebar />
      <a-button v-if="authStore.isLoggedIn" @click="authStore.logout" type="primary" danger block style="margin-top: 20px;">
        <template #icon><LogoutOutlined /></template>
        退出登录
      </a-button>
    </div>
    <main class="main-content">
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
  background-color: #f0f2f5;
  padding: 16px;
  /* 👇 允许侧边栏自身滚动 */
  overflow-y: auto;
  flex-shrink: 0; /* 防止侧边栏被挤压 */
  display: flex; /* 使内部元素垂直排列 */
  flex-direction: column;
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
    min-width: unset; /* 取消最小宽度限制 */
  }

  .main-content {
    /* 3. 主内容区将自然地占据剩余空间 */
    height: 100%;
  }
}
</style>
