// src/stores/fileStore.ts
import { defineStore } from 'pinia'
import { ref, type Ref, computed, onUnmounted } from 'vue'
import axios, { isAxiosError } from 'axios'
import { API_ENDPOINTS } from '@/api'
import { message } from 'ant-design-vue'

// --- 类型定义 ---

export interface UserFile {
  uid: string
  id: string
  name: string
  status: 'done' | 'uploading' | 'error' | 'processing' | 'processed'
  size: number
  response: {
    file_id: string
    original_name: string
    temp_path: string
  }
}

interface StreamInfo {
  codec_type: 'video' | 'audio'
  width?: number
  height?: number
  codec_name: string
  codec_long_name: string
  r_frame_rate: string
  sample_rate?: string
  channels?: number
  channel_layout?: string
  bit_rate?: string
}

interface FormatInfo {
  filename: string
  format_name: string
  format_long_name: string
  duration: string
  size: string
  bit_rate: string
}

export interface FFProbeResult {
  streams: StreamInfo[]
  format: FormatInfo
}

export interface Task {
  id: number
  ffmpeg_command: string
  source_filename: string | null // 新增字段
  output_path: string | null
  status: 'pending' | 'processing' | 'completed' | 'failed'
  details: string | null
  owner_id: number
  progress: number
  result_file_id: number | null // 新增：用于直接关联结果文件的ID
}

// --- Store 定义 ---

export const useFileStore = defineStore('file', () => {
  // --- State ---
  const fileList: Ref<UserFile[]> = ref([])
  const selectedFileId = ref<string | null>(null)
  const taskList: Ref<Task[]> = ref([])
  const isLoading = ref(false)
  const fileInfo = ref<FFProbeResult | null>(null)
  const error = ref<string | null>(null)
  const startTime = ref(0)
  const endTime = ref(0)
  const triggerTaskPanel = ref(false) // 用于触发侧边栏任务列表展开的信号

  // 用于轮询的定时器ID，这是管理轮询的核心
  const taskPoller: Ref<number | null> = ref(null)
  const isPollingPaused = ref(false) // 新增：用于暂停主轮询的状态

  // --- Getters ---
  const totalDuration = computed(() => {
    return fileInfo.value ? parseFloat(fileInfo.value.format.duration) : 0
  })

  // 计算属性，用于判断当前是否有任务在 'pending' 或 'processing' 状态
  const hasActiveTasks = computed(() => {
    return taskList.value.some((task) => ['pending', 'processing'].includes(task.status))
  })

  // --- Actions ---

  /**
   * 从后端获取并更新文件列表
   */
  async function fetchFileList() {
    try {
      const response = await axios.get<UserFile[]>(API_ENDPOINTS.FILE_LIST)
      fileList.value = response.data
    } catch (error) {
      console.error('Failed to fetch file list:', error)
      fileList.value = []
    }
  }

  /**
   * 从后端获取任务列表。
   * 此函数现在包含核心逻辑：对比新旧任务状态，以决定是否刷新文件列表。
   */
  async function fetchTaskList() {
    const oldTaskStatus = new Map(taskList.value.map((task) => [task.id, task.status]))

    try {
      const response = await axios.get<Task[]>(API_ENDPOINTS.TASK_LIST)
      // 强制使用后端数据覆盖本地状态
      taskList.value = response.data

      let justCompleted = false
      // 检查是否有任务状态从 'processing' 变为 'completed'
      for (const task of taskList.value) {
        if (oldTaskStatus.get(task.id) === 'processing' && task.status === 'completed') {
          justCompleted = true
          const fileName =
            task.output_path?.split('\\').pop()?.split('/').pop() || `任务 #${task.id}`
          message.success(`文件 "${fileName}" 已处理完成!`)
        } else if (oldTaskStatus.get(task.id) !== 'failed' && task.status === 'failed') {
          const fileName =
            task.output_path?.split('\\').pop()?.split('/').pop() || `任务 #${task.id}`
          message.error(`文件 "${fileName}" 处理失败。`)
        }
      }

      // 如果有任务刚刚完成，则刷新文件列表以显示新文件
      if (justCompleted) {
        await fetchFileList()
      }

      // 如果所有任务都完成了，轮询器会自动停止（见 startTaskPolling）
      if (!hasActiveTasks.value) {
        stopTaskPolling()
      }
    } catch (error) {
      console.error('Failed to fetch task list:', error)
      stopTaskPolling() // 发生错误时也停止轮询，防止无限循环
    }
  }

  /**
   * 启动任务状态轮询
   */
  function startTaskPolling() {
    // 防止重复启动轮询
    if (taskPoller.value) return

    console.log('>>> [FileStore] Starting task polling...')
    taskPoller.value = window.setInterval(async () => {
      if (isPollingPaused.value) {
        console.log('>>> [FileStore] Main polling is paused.')
        return
      }
      // 只要还有活动任务，就一直获取最新任务列表
      if (hasActiveTasks.value) {
        await fetchTaskList()
      } else {
        // 当没有活动任务时，自动停止轮询
        stopTaskPolling()
      }
    }, 3000) // 每3秒查询一次
  }

  /**
   * 停止任务状态轮询
   */
  function stopTaskPolling() {
    if (taskPoller.value) {
      console.log('>>> [FileStore] Stopping task polling.')
      clearInterval(taskPoller.value)
      taskPoller.value = null
    }
  }

  /**
   * 暂停主任务轮询（当高频轮询启动时）
   */
  function pauseMainPolling() {
    isPollingPaused.value = true
  }

  /**
   * 恢复主任务轮询
   */
  function resumeMainPolling() {
    isPollingPaused.value = false
  }

  /**
   * 获取单个文件的详细信息 (ffprobe)
   */
  async function fetchFileInfo(fileId: string) {
    isLoading.value = true
    error.value = null
    try {
      const response = await axios.get<FFProbeResult>(API_ENDPOINTS.FILE_INFO(fileId))
      fileInfo.value = response.data
      const duration = parseFloat(response.data.format.duration)
      startTime.value = 0
      endTime.value = isNaN(duration) ? 0 : duration
    } catch (err: unknown) {
      let errorMessage = '无法连接到服务器或发生未知错误'
      if (isAxiosError(err)) {
        errorMessage = err.response?.data?.detail || err.message
      } else if (err instanceof Error) {
        errorMessage = err.message
      }
      error.value = errorMessage
      message.error(`加载文件信息失败: ${errorMessage}`)
    } finally {
      isLoading.value = false
    }
  }

  /**
   * 选中一个文件，并触发信息获取
   */
  function selectFile(fileId: string | null) {
    selectedFileId.value = fileId
    if (fileId) {
      fetchFileInfo(fileId)
    } else {
      fileInfo.value = null
      error.value = null
    }
  }

  /**
   * 上传成功后，在前端列表中添加一个文件
   */
  function addFile(file: UserFile) {
    // 避免重复添加
    if (!fileList.value.some((f) => f.id === file.id)) {
      fileList.value.push(file)
    }
  }

  /**
   * 当用户发起处理请求后，将新任务添加到列表，并确保轮询已启动
   */
  function addTasks(newTasks: Task[]) {
    newTasks.forEach((newTask) => {
      const existingIndex = taskList.value.findIndex((task) => task.id === newTask.id)
      if (existingIndex !== -1) {
        // 如果任务已存在，则更新它
        taskList.value[existingIndex] = newTask
      } else {
        // 如果任务不存在，则添加到列表顶部
        taskList.value.unshift(newTask)
      }
    })

    // 如果有活动任务，立即启动轮询
    if (hasActiveTasks.value) {
      startTaskPolling()
    }
    // 触发UI展开任务面板
    expandTaskPanel()
  }

  /**
   * 触发任务面板展开，并随后重置状态
   */
  function expandTaskPanel() {
    triggerTaskPanel.value = true
    // 短暂延迟后重置，以便下次可以再次触发
    setTimeout(() => {
      triggerTaskPanel.value = false
    }, 500)
  }

  /**
   * 更新单个任务的进度（由高频轮询器调用）
   */
  function updateTaskProgress(taskId: number, progress: number) {
    const task = taskList.value.find((t) => t.id === taskId)
    if (task && task.status === 'processing') {
      task.progress = progress
    }
  }

  /**
   * 从服务器和前端列表中删除一个文件
   */
  async function removeFile(fileId: string) {
    try {
      // 使用 apiClient，它会自动处理认证
      await axios.delete(`${API_ENDPOINTS.DELETE_FILE}?filename=${fileId}`)

      // UI 更新逻辑
      fileList.value = fileList.value.filter((f) => f.id !== fileId)
      if (selectedFileId.value === fileId) {
        selectFile(null)
      }
      message.success('文件删除成功')
    } catch (error: unknown) {
      // 捕获的 error 是 unknown 类型
      let errorMsg = '文件删除失败' // 默认错误信息

      // 1. 首先检查它是否是一个 Axios 错误
      if (isAxiosError(error)) {
        errorMsg = error.response?.data?.detail || error.message || errorMsg
      }
      // 2. 其次，检查它是否是一个标准的 JavaScript Error 对象
      else if (error instanceof Error) {
        // 在这里，TypeScript 知道 'error' 是一个 Error
        // 我们可以安全地访问 error.message
        errorMsg = error.message
      }

      // 现在显示最终确定的错误信息
      message.error(errorMsg)
      console.error('Failed to delete file:', error)
    }
  }

  /**
   * 从服务器和前端列表中删除一个任务记录
   */
  async function removeTask(taskId: number) {
    try {
      await axios.delete(API_ENDPOINTS.DELETE_TASK(taskId))
      taskList.value = taskList.value.filter((t) => t.id !== taskId)
      message.success(`任务 #${taskId} 已清除`)
    } catch (error) {
      message.error(`任务 #${taskId} 清除失败`)
      console.error('Failed to delete task:', error)
    }
  }

  /**
   * 更新裁剪时间
   */
  function updateTrimTimes({ start, end }: { start: number; end: number }) {
    startTime.value = start
    endTime.value = end
  }

  /**
   * 根据任务信息定位到对应的处理后文件
   */
  function selectFileByTask(task: Task) {
    if (!task.result_file_id) {
      message.error('任务信息中缺少结果文件ID，无法定位文件。')
      console.warn('任务没有输出文件ID', task)
      return
    }

    // 使用结果文件ID直接、精确地查找文件
    const targetFile = fileList.value.find((file) => file.id === String(task.result_file_id))

    if (targetFile) {
      // 选中文件并跳转到工作区
      selectFile(targetFile.id)
      message.success(`已定位到文件: ${targetFile.name}`)
    } else {
      message.warning('未找到对应的处理后文件，请确保文件列表已刷新')
      console.warn(
        `Could not find file with ID ${task.result_file_id} in the current file list.`,
        fileList.value
      )
    }
  }

  /**
   * Store初始化/应用启动时的逻辑
   */
  async function initializeStore() {
    await fetchFileList()
    await fetchTaskList()
    // 如果初始加载后发现有未完成的任务，则启动轮询
    if (hasActiveTasks.value) {
      startTaskPolling()
    }
  }

  /**
   * 使用 Axios 和 Blob 安全地下载文件, 解决 token 和新窗口问题
   */
  async function downloadFile(fileId: string) {
    const downloadUrl = API_ENDPOINTS.DOWNLOAD_FILE(fileId)
    const loadingMessage = message.loading('正在准备下载...', 0)

    try {
      const response = await axios.get(downloadUrl, {
        responseType: 'blob' // 关键：期望响应是二进制数据
      })

      // 从 Content-Disposition 头中提取文件名
      const contentDisposition = response.headers['content-disposition']
      let filename = 'downloaded_file' // 默认文件名
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/)
        if (filenameMatch && filenameMatch.length > 1) {
          filename = decodeURIComponent(filenameMatch[1])
        }
      }

      // 创建 Blob URL 并触发下载
      const blob = new Blob([response.data], { type: response.headers['content-type'] })
      const link = document.createElement('a')
      link.href = window.URL.createObjectURL(blob)
      link.download = filename
      document.body.appendChild(link)
      link.click()

      // 清理
      window.URL.revokeObjectURL(link.href)
      document.body.removeChild(link)

      loadingMessage() // 关闭加载提示
      message.success(`文件 "${filename}" 已开始下载。`)
    } catch (error: unknown) {
      loadingMessage() // 关闭加载提示
      let errorMessage = '下载失败。'
      if (isAxiosError(error)) {
        // 对于Blob响应，错误信息可能需要特殊处理
        if (error.response && error.response.data) {
          try {
            // 尝试将Blob错误响应解析为JSON文本
            const errorText = await error.response.data.text()
            const errorJson = JSON.parse(errorText)
            errorMessage = errorJson.detail || '无法解析错误详情'
          } catch (e) {
            errorMessage = error.message || '发生未知网络错误'
          }
        }
      } else if (error instanceof Error) {
        errorMessage = error.message
      }
      message.error(errorMessage)
      console.error('Download failed:', error)
    }
  }

  // 确保在应用卸载时清除定时器，防止内存泄漏
  onUnmounted(() => {
    stopTaskPolling()
  })

  // --- 返回暴露给组件的 state, getters, 和 actions ---
  return {
    // State
    selectedFileId,
    fileList,
    taskList,
    isLoading,
    fileInfo,
    error,
    startTime,
    endTime,
    triggerTaskPanel,
    // Getters
    totalDuration,
    hasActiveTasks,
    // Actions
    selectFile,
    fetchFileList,
    fetchTaskList,
    addFile,
    addTasks,
    removeFile,
    removeTask,
    updateTrimTimes,
    selectFileByTask,
    initializeStore, // 暴露初始化方法
    updateTaskProgress, // 暴露给 TaskDetails 组件使用
    pauseMainPolling,
    resumeMainPolling,
    downloadFile, // 暴露下载方法
  }
})
