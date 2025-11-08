<template>
  <div class="task-details">
    <div class="task-header">
      <div class="header-content">
        <h2>任务详情 #{{ task.id }}</h2>
        <div class="task-status-badge">
          <a-tag :color="getStatusColor(task.status)">{{ getStatusText(task.status) }}</a-tag>
        </div>
      </div>
      <a-button @click="emit('close')" type="text" class="close-btn">
        <template #icon>
          <close-outlined />
        </template>
      </a-button>
    </div>

    <div class="task-info">
      <a-descriptions :column="descriptionColumns" bordered>
        <a-descriptions-item label="状态">
          <a-tag :color="getStatusColor(task.status)">{{ getStatusText(task.status) }}</a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="源文件">
          {{ task.source_filename || '未知' }}
        </a-descriptions-item>
        <a-descriptions-item label="输出路径">
          {{ task.output_path || '未生成' }}
        </a-descriptions-item>
        <a-descriptions-item label="进度">
          <a-progress
            v-if="isProcessing(task.status)"
            :percent="getProgress(task)"
            :status="task.status === 'failed' ? 'exception' : 'active'"
          />
          <span v-else>{{ getProgress(task) }}%</span>
        </a-descriptions-item>
        <a-descriptions-item label="命令" :span="descriptionColumns">
          <div class="command-preview">
            <code>{{ task.ffmpeg_command }}</code>
            <a-tooltip title="复制命令">
              <copy-outlined class="copy-icon" @click="copyCommand" />
            </a-tooltip>
          </div>
        </a-descriptions-item>
        <a-descriptions-item
          v-if="task.details && task.details.length > 0"
          label="详细信息"
          :span="descriptionColumns"
        >
          <div class="details-content">
            <pre class="details-text">{{ task.details }}</pre>
          </div>
        </a-descriptions-item>
      </a-descriptions>
    </div>

    <div class="task-actions" v-if="task.status === 'completed' && task.output_path">
      <a-button type="primary" @click="goToFileAndDownload">
        <DownloadOutlined />
        定位到文件并下载
      </a-button>
      <a-button @click="goToFile">
        <FileOutlined />
        定位到文件
      </a-button>
    </div>

    <div class="task-actions" v-else-if="task.status === 'failed' && task.details">
      <a-button type="primary" @click="copyErrorDetails">
        <CopyOutlined />
        复制错误信息
      </a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useFileStore, type Task } from '@/stores/fileStore'
import { message } from 'ant-design-vue'
import { CopyOutlined, DownloadOutlined, FileOutlined, CloseOutlined } from '@ant-design/icons-vue'

const props = defineProps<{
  task: Task
}>()

const emit = defineEmits(['close'])

const fileStore = useFileStore()

const descriptionColumns = ref(2)
let observer: ResizeObserver | null = null
const workspaceRef = ref<HTMLElement | null>(null)

const setupResizeObserver = () => {
  if (workspaceRef.value) {
    observer = new ResizeObserver((entries) => {
      const contentWidth = entries[0].contentRect.width
      descriptionColumns.value = contentWidth < 620 ? 1 : 2
    })
    observer.observe(workspaceRef.value)
  }
}

// =========================================================
// 核心修复：将所有 onMounted 逻辑合并到一个钩子中
// =========================================================
onMounted(() => {
  // 1. 立即发起 API 请求以获取最新任务数据
  fileStore.fetchSingleTaskAndUpdate(props.task.id)

  // 2. 在下一个 DOM 更新周期后，初始化响应式布局的观察器
  nextTick(() => {
    workspaceRef.value = document.querySelector('.task-details') as HTMLElement
    setupResizeObserver()
  })
})
// =========================================================

onBeforeUnmount(() => {
  if (observer) {
    observer.disconnect()
  }
})

const getStatusColor = (status: string) => {
  switch (status) {
    case 'pending':
      return 'orange'
    case 'processing':
      return 'blue'
    case 'completed':
      return 'green'
    case 'failed':
      return 'red'
    default:
      return 'default'
  }
}

const getStatusText = (status: string) => {
  switch (status) {
    case 'pending':
      return '等待中'
    case 'processing':
      return '处理中'
    case 'completed':
      return '已完成'
    case 'failed':
      return '已失败'
    default:
      return status
  }
}

const isProcessing = (status: string) => {
  return ['pending', 'processing'].includes(status)
}

const getProgress = (task: Task) => {
  if (task.status === 'completed') return 100
  if (task.status === 'failed') return 0
  return task.progress || 0
}

const copyCommand = async () => {
  try {
    await navigator.clipboard.writeText(props.task.ffmpeg_command)
    message.success('命令已复制到剪贴板')
  } catch {
    message.error('复制命令失败')
  }
}

const copyErrorDetails = async () => {
  try {
    await navigator.clipboard.writeText(props.task.details || '')
    message.success('错误信息已复制到剪贴板')
  } catch {
    message.error('复制错误信息失败')
  }
}

const goToFile = () => {
  fileStore.selectFileByTask(props.task)
  emit('close')
}

const goToFileAndDownload = () => {
  const fileId = fileStore.selectFileByTask(props.task)
  if (fileId) {
    emit('close')
    nextTick(() => {
      fileStore.downloadFile(fileId)
    })
  }
}
</script>

<style scoped>
.task-details {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 16px;
  overflow-y: auto;
}

.task-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid #f0f0f0;
}

.header-content {
  display: flex;
  align-items: center;
  flex-grow: 1;
}

.header-content h2 {
  margin: 0;
  margin-right: 16px;
}

.task-status-badge .ant-tag {
  font-size: 12px;
  padding: 2px 8px;
}

.task-info {
  flex-grow: 1;
  margin-bottom: 20px;
}

.command-preview {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background-color: #f9f9f9;
  border-radius: 4px;
  padding: 8px;
  font-family: monospace;
  word-break: break-all;
  position: relative;
}

.command-preview code {
  flex-grow: 1;
  overflow-x: auto;
  font-size: 12px;
  max-height: 100px;
  white-space: pre-wrap;
  line-height: 1.5;
}

.copy-icon {
  cursor: pointer;
  margin-left: 8px;
  color: #1890ff;
  font-size: 16px;
  flex-shrink: 0;
}

.details-content {
  position: relative;
}

.details-text {
  background-color: #f9f9f9;
  border-radius: 4px;
  padding: 12px;
  font-size: 13px;
  line-height: 1.5;
  max-height: 200px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
  margin-bottom: 8px;
}

.task-actions {
  display: flex;
  gap: 12px;
  margin-top: auto;
  padding-top: 16px;
  border-top: 1px solid #f0f0f0;
}

.close-btn {
  padding: 0;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
