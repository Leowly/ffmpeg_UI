<!-- src/App.vue -->
<script setup lang="ts">
import { onUnmounted, ref, computed, watch } from 'vue'
import AppSidebar from './components/AppSidebar.vue'
import SingleFileWorkspace from './components/SingleFileWorkspace.vue'
import AuthForm from './components/AuthForm.vue'
import UserInfo from './components/UserInfo.vue'
import ExportModal from './components/ExportModal.vue'
import TaskDetails from './components/TaskDetails.vue'
import { useAuthStore } from './stores/authStore'
import { useFileStore } from './stores/fileStore'
import { message } from 'ant-design-vue'

const authStore = useAuthStore()
const fileStore = useFileStore()

const isExportModalVisible = ref(false)
const selectedTaskId = ref<number | null>(null)

let healthCheckInterval: number | null = null

const handleExportClick = () => {
  if (fileStore.fileList.length === 0) {
    message.warning('文件列表为空，请先上传一些文件再执行导出操作。')
    return
  }
  isExportModalVisible.value = true
}

const selectedTask = computed(() => {
  if (selectedTaskId.value === null) return null
  return fileStore.taskList.find((task) => task.id === selectedTaskId.value) || null
})

const selectTask = (taskId: number) => {
  selectedTaskId.value = taskId
}

// =========================================================
// 核心修复：将定时器改造为 WebSocket 健康检查器
// =========================================================
const startHealthCheck = () => {
  if (healthCheckInterval) {
    clearInterval(healthCheckInterval)
  }
  // 每 10 秒检查一次连接的健康状况
  healthCheckInterval = window.setInterval(() => {
    if (fileStore.hasActiveTasks) {
      // 不再调用 fetchTaskList()，而是调用新的健康检查函数
      fileStore.checkAndReconnectWebSockets()
    } else {
      // 如果没有活动任务，停止定时器
      stopHealthCheck()
    }
  }, 10000)
}

const stopHealthCheck = () => {
  if (healthCheckInterval) {
    clearInterval(healthCheckInterval)
    healthCheckInterval = null
  }
}
// =========================================================
// 修复结束
// =========================================================

// 监听登录状态变化
watch(
  () => authStore.isLoggedIn,
  (isLoggedIn) => {
    if (isLoggedIn) {
      // 登录后：获取用户 -> 初始化 Store -> 启动检查
      authStore.fetchCurrentUser().then(() => {
        fileStore.initializeStore()
        startHealthCheck()
      })
    } else {
      // 退出后：停止检查
      stopHealthCheck()
    }
  },
  { immediate: true } // 初始化时立即执行一次
)

onUnmounted(() => {
  stopHealthCheck()
})
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

    <div class="bottom-toolbar">
      <UserInfo />
      <a-button type="primary" shape="round" size="large" @click="handleExportClick">
        导出文件
      </a-button>
    </div>

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
  background-color: transparent;
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
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
}

.bottom-toolbar {
  position: fixed;
  bottom: 10px;
  left: 20px;
  z-index: 1000;
  display: flex;
  align-items: center;
  gap: 16px;
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
