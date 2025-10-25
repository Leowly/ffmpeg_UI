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
        <a-descriptions-item label="命令" :span="2">
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
          :span="2"
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
import { ref, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { useFileStore, type Task } from '@/stores/fileStore'
import { message } from 'ant-design-vue'
import { CopyOutlined, DownloadOutlined, FileOutlined, CloseOutlined } from '@ant-design/icons-vue'
import axios from 'axios'
import { API_ENDPOINTS } from '@/api'

// 接收任务作为 prop
const props = defineProps<{
  task: Task
}>()

// 定义 emits
const emit = defineEmits(['close'])

// 文件store实例
const fileStore = useFileStore()

// --- 实时进度轮询 ---
const progressPoller = ref<number | null>(null)

const fetchProgress = async () => {
  if (props.task.status !== 'processing') {
    stopProgressPolling()
    return
  }
  try {
    const response = await axios.get<{ progress: number }>(
      API_ENDPOINTS.TASK_PROGRESS(props.task.id)
    )

    const progress = response.data.progress

    // 总是先更新进度，让UI即时反应
    fileStore.updateTaskProgress(props.task.id, progress)

    // 处理失败信号
    if (progress === -1) {
      stopProgressPolling() // 停止当前轮询
      // 强制刷新整个任务列表以获取最新的“failed”状态和其他详情
      await fileStore.fetchTaskList()
      return
    }

    // 处理完成信号
    if (progress >= 100) {
      stopProgressPolling()
      // 添加一个短暂的延迟，以确保后端有足够的时间将任务状态完全更新为“completed”
      setTimeout(() => {
        fileStore.fetchTaskList()
      }, 500)
      return
    }
  } catch (error) {
    console.error(`Failed to fetch progress for task ${props.task.id}:`, error)
    // 如果接口404（可能任务已完成，缓存已清理），则停止轮询
    if (axios.isAxiosError(error) && error.response?.status === 404) {
      stopProgressPolling()
    }
  }
}

const startProgressPolling = () => {
  if (progressPoller.value) return // 避免重复启动
  fileStore.pauseMainPolling() // 暂停主轮询
  console.log(`[TaskDetails] Starting progress polling for task #${props.task.id}`)
  progressPoller.value = window.setInterval(fetchProgress, 1000) // 每 1s 查询一次
}

const stopProgressPolling = () => {
  if (progressPoller.value) {
    console.log(`[TaskDetails] Stopping progress polling for task #${props.task.id}`)
    clearInterval(progressPoller.value)
    progressPoller.value = null
    fileStore.resumeMainPolling() // 恢复主轮询
  }
}

// 监视任务状态，自动启停轮询器
watch(
  () => props.task.status,
  (newStatus, oldStatus) => {
    if (newStatus === 'processing') {
      startProgressPolling()
    } else if (oldStatus === 'processing' && newStatus !== 'processing') {
      stopProgressPolling()
      // 当任务从处理中变为完成时，确保进度条达到100%
      if (newStatus === 'completed') {
        fileStore.updateTaskProgress(props.task.id, 100)
      }
    }
  },
  { immediate: true } // 立即执行一次，以便组件加载时就能启动轮询
)

// 响应式列数，根据屏幕宽度调整
const descriptionColumns = ref(2)

// 创建 ResizeObserver 实例
let observer: ResizeObserver | null = null
const workspaceRef = ref<HTMLElement | null>(null)

// 设置响应式列数
const setupResizeObserver = () => {
  if (workspaceRef.value) {
    observer = new ResizeObserver((entries) => {
      const contentWidth = entries[0].contentRect.width
      descriptionColumns.value = contentWidth < 620 ? 1 : 2
    })
    observer.observe(workspaceRef.value)
  }
}

onMounted(() => {
  nextTick(() => {
    workspaceRef.value = document.querySelector('.task-details') as HTMLElement
    setupResizeObserver()
  })
})

onBeforeUnmount(() => {
  stopProgressPolling() // 组件卸载时确保停止轮询
  fileStore.resumeMainPolling() // 同时确保主轮询已恢复
  if (observer) {
    observer.disconnect()
  }
})

// 文件store实例

// 根据状态获取颜色
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

// 根据状态获取文本
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

// 检查是否在处理中
const isProcessing = (status: string) => {
  return ['pending', 'processing'].includes(status)
}

// 获取进度
const getProgress = (task: Task) => {
  if (task.status === 'completed') return 100
  if (task.status === 'failed') return 0
  return task.progress || 0
}

// 格式化日期

// 复制命令到剪贴板
const copyCommand = async () => {
  try {
    await navigator.clipboard.writeText(props.task.ffmpeg_command)
    message.success('命令已复制到剪贴板')
  } catch {
    message.error('复制命令失败')
  }
}

// 复制错误详情到剪贴板
const copyErrorDetails = async () => {
  try {
    await navigator.clipboard.writeText(props.task.details || '')
    message.success('错误信息已复制到剪贴板')
  } catch {
    message.error('复制错误信息失败')
  }
}

// 定位到处理后的文件
const goToFile = () => {
  fileStore.selectFileByTask(props.task)
  emit('close') // 切换回工作区视图
}

// 定位到文件并下载
const goToFileAndDownload = () => {
  goToFile() // 这个函数会选中文件并触发视图切换
  // 稍作延迟，以确保视图切换和文件选中状态更新完毕
  setTimeout(() => {
    if (fileStore.selectedFileId) {
      fileStore.downloadFile(fileStore.selectedFileId)
    }
  }, 300)
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
