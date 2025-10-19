<!-- src/App.vue -->
<script setup lang="ts">
import { onMounted, watch, ref, computed } from 'vue';
import AppSidebar from './components/AppSidebar.vue'
import SingleFileWorkspace from './components/SingleFileWorkspace.vue';
import AuthForm from './components/AuthForm.vue';
import UserInfo from './components/UserInfo.vue';
import ExportModal from './components/ExportModal.vue';
import TaskDetails from './components/TaskDetails.vue';
import { useAuthStore } from './stores/authStore';
import { useFileStore } from './stores/fileStore';
import { ExportOutlined } from '@ant-design/icons-vue';
import { message } from 'ant-design-vue';

const authStore = useAuthStore();
const fileStore = useFileStore();

const isExportModalVisible = ref(false);
const selectedTaskId = ref<number | null>(null); // 当前选中的任务ID

// 更新后的导出点击逻辑
const handleExportClick = () => {
  if (fileStore.fileList.length === 0) {
    message.warning('文件列表为空，请先上传一些文件再执行导出操作。');
    return;
  }
  isExportModalVisible.value = true;
};

// 获取选中的任务对象
const selectedTask = computed(() => {
  if (selectedTaskId.value === null) return null;
  return fileStore.taskList.find(task => task.id === selectedTaskId.value) || null;
});

// 选择任务并显示详情
const selectTask = (taskId: number) => {
  selectedTaskId.value = taskId;
};

// 创建一个标志，用于区分是初始加载还是状态变化
let isInitialCheck = true;

onMounted(async () => {
  if (authStore.isLoggedIn) {
    // 首先验证token是否有效
    const isValid = await authStore.validateToken();
    if (isValid) {
      fileStore.initializeStore();
    } else {
      // 如果token无效，确保用户状态被清除
      authStore.logout();
    }
  }
  isInitialCheck = false; // 标记初始检查已完成
});

watch(() => authStore.isLoggedIn, async (newVal, oldVal) => {
  // 仅当状态从“未登录”变为“已登录”时，才执行此逻辑块
  // 排除初始加载的情况
  if (newVal && !oldVal && !isInitialCheck) {
    await authStore.fetchCurrentUser();
    // 确保获取用户信息成功后再获取其他数据
    if (authStore.user) {
      fileStore.initializeStore();
    }
  }
  isInitialCheck = false; // 在任何状态变化后都设置为false
}, { immediate: true });
</script>

<template>
  <AuthForm v-if="!authStore.isLoggedIn" />
  <div v-else class="app-layout">
    <div class="sidebar">
      <div class="panel-card">
        <AppSidebar @task-selected="selectTask" @file-selected="selectedTaskId = null" />
      </div>
    </div>
    <main class="main-content">
      <div class="panel-card">
        <SingleFileWorkspace v-if="!selectedTaskId" />
        <TaskDetails v-else-if="selectedTask" :task="selectedTask" @close="selectedTaskId = null" />
      </div>
    </main>

    <!-- 左下角工具栏 -->
    <div class="bottom-toolbar">
      <UserInfo />
      <a-button
        type="primary"
        shape="round"
        size="large"
        @click="handleExportClick"
      >
        <template #icon><ExportOutlined /></template>
        导出文件
      </a-button>
    </div>

    <!-- 导出模态框 (移除 :file-info 属性) -->
    <ExportModal
      v-model:visible="isExportModalVisible"
      :initial-start-time="fileStore.startTime"
      :initial-end-time="fileStore.endTime"
    />
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  flex-direction: row;
  height: 100vh;
  width: 100vw;
  background-color: #f0f2f5;
  overflow: hidden;
}

.sidebar {
  width: 350px;
  min-width: 300px;
  /* 保持与主背景一致，减少内边距以让内部卡片靠近边缘 */
  background-color: transparent; /* 使用透明，显示上层 .app-layout 背景 */
  padding: 4px;
  overflow-y: auto;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
}

.main-content {
  flex-grow: 1;
  padding: 4px;
  overflow-y: auto;
}

.panel-card {
  background-color: #fff;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  padding: 8px;
  height: 100%;
  display: flex;
  flex-direction: column;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}

.bottom-toolbar {
  position: fixed;
  bottom: 10px;
  left: 20px;
  z-index: 1000;
  display: flex;
  align-items: center;
  gap: 16px; /* 按钮和用户信息之间的间距 */
}

@media (max-width: 768px) {
  .app-layout {
    flex-direction: column;
  }

  .sidebar {
    width: 100%;
    height: auto;
    max-height: 40vh;
    border-right: none;
    min-width: unset;
  }

  .main-content {
    height: 100%;
  }
}
</style>

