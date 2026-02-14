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
import { useScreenLayout } from './composables/useScreenLayout'
import { message } from 'ant-design-vue'
import { ExportOutlined } from '@ant-design/icons-vue'

const { spacing, fontSize, borderRadius, layout } = useScreenLayout()

const cssVars = computed(() => ({
  '--spacing-xs': spacing.value.xs,
  '--spacing-sm': spacing.value.sm,
  '--spacing-md': spacing.value.md,
  '--spacing-lg': spacing.value.lg,
  '--spacing-xl': spacing.value.xl,
  '--font-xs': fontSize.value.xs,
  '--font-sm': fontSize.value.sm,
  '--font-md': fontSize.value.md,
  '--font-lg': fontSize.value.lg,
  '--font-xl': fontSize.value.xl,
  '--radius-sm': borderRadius.value.sm,
  '--radius-md': borderRadius.value.md,
  '--radius-lg': borderRadius.value.lg,
  '--sidebar-width': layout.value.sidebarWidth,
  '--content-padding': layout.value.contentPadding,
  '--card-padding': layout.value.cardPadding,
  '--gap': layout.value.gap,
}))

const authStore = useAuthStore()
const fileStore = useFileStore()

const isExportModalVisible = ref(false)
const selectedTaskId = ref<number | null>(null)
const hasSelectedFile = ref(false)

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
  const cached = fileStore.taskDetailsCache.get(selectedTaskId.value)
  if (cached) return cached
  return fileStore.taskList.find((task) => task.id === selectedTaskId.value) || null
})

const selectTask = (taskId: number) => {
  selectedTaskId.value = taskId
  hasSelectedFile.value = false
  fileStore.selectFile(null)
}

const handleFileSelected = () => {
  selectedTaskId.value = null // Switch from task to file view
  hasSelectedFile.value = true
}

const closeTask = () => {
  selectedTaskId.value = null
  hasSelectedFile.value = false
}

const switchToFile = () => {
  // Set file first, then clear task - ensures no flashing
  hasSelectedFile.value = true
  selectedTaskId.value = null
}

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
  { immediate: true }, // 初始化时立即执行一次
)

onUnmounted(() => {
  stopHealthCheck()
})
</script>

<template>
  <AuthForm v-if="!authStore.isLoggedIn" />
  <div v-else class="app-layout" :style="cssVars">
    <div class="sidebar">
      <div class="panel-card">
        <AppSidebar
          :selected-task-id="selectedTaskId"
          @task-selected="selectTask"
          @file-selected="handleFileSelected"
        />
      </div>
    </div>
    <main class="main-content">
      <div class="panel-card">
        <SingleFileWorkspace v-if="hasSelectedFile && !selectedTaskId" />
        <TaskDetails
          v-else-if="selectedTask"
          :task="selectedTask"
          @close="closeTask"
          @switch-to-file="switchToFile"
        />
        <a-empty v-else description="请从左侧选择文件或任务" />
      </div>
    </main>

    <div class="bottom-toolbar">
      <UserInfo />
      <a-button class="export-button" shape="round" size="large" @click="handleExportClick">
        <template #icon><ExportOutlined /></template>
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
  width: var(--sidebar-width, 350px);
  min-width: 250px;
  background-color: transparent;
  padding: var(--content-padding);
  overflow-y: auto;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  transition:
    width 0.3s ease,
    padding 0.3s ease;
  overflow-x: hidden;
}

.main-content {
  flex-grow: 1;
  padding: var(--content-padding);
  overflow-y: auto;
}

.panel-card {
  background-color: #fff;
  border: 1px solid #e8e8e8;
  border-radius: var(--radius-md);
  padding: var(--card-padding);
  height: 100%;
  display: flex;
  flex-direction: column;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
  overflow: hidden;
}

.bottom-toolbar {
  position: fixed;
  bottom: var(--spacing-md);
  left: 50%;
  transform: translateX(-50%);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-xs) var(--spacing-sm);
  background: rgba(255, 255, 255, 0.95);
  border-radius: 24px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
  backdrop-filter: blur(8px);
}

.export-button {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 0 20px;
  min-width: 110px;
  height: 40px;
  background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
  border: none;
  border-radius: 20px;
  color: #fff;
  font-weight: 600;
  font-size: 14px;
  box-shadow: 0 2px 10px rgba(56, 239, 125, 0.35);
  transition: all 0.3s ease;
}

.export-button:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(56, 239, 125, 0.5);
  background: linear-gradient(135deg, #0fa89a 0%, #2dd36d 100%);
}

.export-button:active {
  transform: translateY(0);
  box-shadow: 0 2px 8px rgba(56, 239, 125, 0.35);
}

.export-button :deep(.anticon) {
  font-size: 16px;
}

@media (max-width: 768px) {
  .app-layout {
    flex-direction: column;
    height: 100dvh; /* 使用动态视口高度，避免移动端地址栏问题 */
  }

  .sidebar {
    width: 100%;
    height: auto;
    max-height: 35vh;
    border-right: none;
    min-width: unset;
    padding-bottom: 0;
  }

  .main-content {
    flex: 1;
    min-height: 0;
    padding-top: var(--spacing-xs);
  }

  .panel-card {
    min-height: 0;
  }

  .bottom-toolbar {
    position: fixed;
    bottom: var(--spacing-xs);
    left: var(--spacing-sm);
    right: var(--spacing-sm);
    transform: none;
    justify-content: space-between;
    padding: 6px 10px;
    gap: 8px;
    border-radius: 16px;
  }

  .export-button {
    flex: 1;
    min-width: unset;
    padding: 0 12px;
    height: 36px;
    font-size: 13px;
  }

  .export-button :deep(.anticon) {
    font-size: 14px;
  }

  .bottom-toolbar :deep(.user-button) {
    min-width: 36px;
    width: 36px;
    height: 36px;
    padding: 0;
    border-radius: 50%;
  }

  .bottom-toolbar :deep(.user-avatar) {
    width: 24px !important;
    height: 24px !important;
    line-height: 24px !important;
  }

  .bottom-toolbar :deep(.user-avatar .anticon) {
    font-size: 14px;
  }
}
</style>
