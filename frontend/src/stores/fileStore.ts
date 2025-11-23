// src/stores/fileStore.ts
import { defineStore } from 'pinia'
import { ref, type Ref, computed, onUnmounted } from 'vue'
import axios, { isAxiosError } from 'axios'
import { API_ENDPOINTS } from '@/api'
import { message } from 'ant-design-vue'
import { Capacitor } from '@capacitor/core'
import { Filesystem, Directory } from '@capacitor/filesystem'

// --- Types ---
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

// 新增类型
interface SystemCapabilities {
  has_hardware_acceleration: boolean
  hardware_type: string | null
}

export interface Task {
  id: number
  ffmpeg_command: string
  source_filename: string | null
  output_path: string | null
  status: 'pending' | 'processing' | 'completed' | 'failed'
  details: string | null
  owner_id: number
  progress: number
  result_file_id: number | null
}

// --- Store Definition ---
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
  const triggerTaskPanel = ref(false)
  const wsConnections: Ref<Map<number, WebSocket>> = ref(new Map())

  // 新增 State
  const systemCapabilities = ref<SystemCapabilities>({
    has_hardware_acceleration: false,
    hardware_type: null
  })

  // --- Getters ---
  const totalDuration = computed(() => {
    return fileInfo.value ? parseFloat(fileInfo.value.format.duration) : 0
  })

  const hasActiveTasks = computed(() => {
    return taskList.value.some((task) => ['pending', 'processing'].includes(task.status))
  })

  // --- Actions ---
  async function fetchFileList() {
    try {
      const response = await axios.get<UserFile[]>(API_ENDPOINTS.FILE_LIST)
      fileList.value = response.data
    } catch (error) {
      console.error('Failed to fetch file list:', error)
      fileList.value = []
    }
  }

  async function fetchTaskList() {
    try {
      const response = await axios.get<Task[]>(API_ENDPOINTS.TASK_LIST)
      const oldTaskIds = new Set(taskList.value.map((task) => task.id))
      taskList.value = response.data

      response.data.forEach((task) => {
        if (['pending', 'processing'].includes(task.status) && !oldTaskIds.has(task.id)) {
          connectToTask(task.id)
        }
      })
    } catch (error) {
      console.error('Failed to fetch task list:', error)
    }
  }

  function connectToTask(taskId: number) {
    const existingWs = wsConnections.value.get(taskId)
    if (existingWs && existingWs.readyState === WebSocket.OPEN) {
      return
    }

    const ws = new WebSocket(API_ENDPOINTS.WS_PROGRESS(taskId))
    ws.onopen = () => {
      console.log(`WebSocket connected for task ${taskId}`)
      wsConnections.value.set(taskId, ws)
    }

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      if (data.progress !== undefined) {
        updateTaskProgress(taskId, data.progress, data.status)
      }
    }

    ws.onclose = () => {
      console.log(`WebSocket disconnected for task ${taskId}`)
      wsConnections.value.delete(taskId)
    }

    ws.onerror = (error) => {
      console.error(`WebSocket error for task ${taskId}:`, error)
      wsConnections.value.delete(taskId)
    }
  }

  function checkAndReconnectWebSockets() {
    taskList.value.forEach((task) => {
      if (['pending', 'processing'].includes(task.status)) {
        const ws = wsConnections.value.get(task.id)
        if (!ws || ws.readyState === WebSocket.CLOSED) {
          console.warn(`WebSocket for active task #${task.id} is missing or closed. Reconnecting...`)
          connectToTask(task.id)
        }
      }
    })
  }

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
      let errorMessage = 'Could not connect to server or unknown error occurred'
      if (isAxiosError(err)) {
        errorMessage = err.response?.data?.detail || err.message
      } else if (err instanceof Error) {
        errorMessage = err.message
      }
      error.value = errorMessage
      message.error(`Failed to load file info: ${errorMessage}`)
    } finally {
      isLoading.value = false
    }
  }

  function selectFile(fileId: string | null) {
    selectedFileId.value = fileId
    if (fileId) {
      fetchFileInfo(fileId)
    } else {
      fileInfo.value = null
      error.value = null
    }
  }

  function addFile(file: UserFile) {
    if (!fileList.value.some((f) => f.id === file.id)) {
      fileList.value.push(file)
    }
  }

  async function fetchSingleTaskAndUpdate(taskId: number) {
    try {
      const response = await axios.get<Task>(API_ENDPOINTS.GET_TASK_DETAILS(taskId))
      const updatedTask = response.data

      const taskIndex = taskList.value.findIndex((task) => task.id === taskId)
      if (taskIndex !== -1) {
        // 如果找到了任务，就用最新的数据替换它
        taskList.value[taskIndex] = updatedTask
      }
    } catch (error) {
      console.error(`Failed to fetch details for task #${taskId}:`, error)
      message.error('无法获取最新的任务详情。')
    }
  }

  function addTasks(newTasks: Task[]) {
    newTasks.forEach((newTask) => {
      const existingIndex = taskList.value.findIndex((task) => task.id === newTask.id)
      if (existingIndex !== -1) {
        taskList.value[existingIndex] = newTask
      } else {
        // 🔴 【修改】删除或注释掉下面这一行 - 不强制将新任务状态设为 'processing'
        // newTask.status = 'processing'
        taskList.value.unshift(newTask)
      }
      if (['pending', 'processing'].includes(newTask.status)) {
        connectToTask(newTask.id)
      }
    })
    expandTaskPanel()
  }

  function expandTaskPanel() {
    triggerTaskPanel.value = true
    setTimeout(() => {
      triggerTaskPanel.value = false
    }, 500)
  }

  function updateTaskProgress(taskId: number, progress: number, status?: 'completed' | 'failed') {
    const task = taskList.value.find((t) => t.id === taskId)
    if (task) {
      task.progress = progress
      if (status) {
        task.status = status
        wsConnections.value.get(taskId)?.close()
        if (status === 'completed' || status === 'failed') {
          fetchTaskList()
          fetchFileList()
        }
      }
    }
  }

  async function removeFile(fileId: string) {
    try {
      await axios.delete(`${API_ENDPOINTS.DELETE_FILE}?filename=${fileId}`)
      fileList.value = fileList.value.filter((f) => f.id !== fileId)
      if (selectedFileId.value === fileId) {
        selectFile(null)
      }
      await fetchTaskList()
      message.success('File deleted successfully')
    } catch (error: unknown) {
      let errorMsg = 'Failed to delete file'
      if (isAxiosError(error)) {
        errorMsg = error.response?.data?.detail || error.message || errorMsg
      } else if (error instanceof Error) {
        errorMsg = error.message
      }
      message.error(errorMsg)
      console.error('Failed to delete file:', error)
    }
  }

  async function removeTask(taskId: number) {
    try {
      await axios.delete(API_ENDPOINTS.DELETE_TASK(taskId))
      taskList.value = taskList.value.filter((t) => t.id !== taskId)
      wsConnections.value.get(taskId)?.close()
      message.success(`Task #${taskId} has been cleared`)
    } catch (error) {
      message.error(`Failed to clear task #${taskId}`)
      console.error('Failed to delete task:', error)
    }
  }

  function updateTrimTimes({ start, end }: { start: number; end: number }) {
    startTime.value = start
    endTime.value = end
  }

  function selectFileByTask(task: Task): string | null {
    if (!task.result_file_id) {
      message.error('Task information is missing the result file ID.')
      return null
    }
    const targetFile = fileList.value.find((file) => file.id === String(task.result_file_id))
    if (targetFile) {
      selectFile(targetFile.id)
      message.success(`Located file: ${targetFile.name}`)
      return targetFile.id
    } else {
      message.warning('Could not find the processed file. Please ensure the file list is up to date.')
      return null
    }
  }

  async function downloadFile(fileId: string) {
    const downloadUrl = API_ENDPOINTS.DOWNLOAD_FILE(fileId)
    const loadingMessage = message.loading('Preparing to download...', 0)

    try {
      const response = await axios.get(downloadUrl, {
        responseType: 'blob',
      })

      const contentDisposition = response.headers['content-disposition']
      let filename = 'downloaded_file'
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/)
        if (filenameMatch && filenameMatch.length > 1) {
          filename = decodeURIComponent(filenameMatch[1])
        }
      }

      const blob = new Blob([response.data], { type: response.headers['content-type'] })

      if (Capacitor.isNativePlatform()) {
        const reader = new FileReader()
        reader.readAsDataURL(blob)
        reader.onloadend = async () => {
          const base64data = reader.result as string
          try {
            await Filesystem.writeFile({
              path: filename,
              data: base64data,
              directory: Directory.Documents,
            })
            loadingMessage()
            message.success(`File "${filename}" has been saved to the "Documents" folder.`)
          } catch (_e) {
            loadingMessage()
            console.error('Unable to save file', _e)
            message.error('Failed to save file. Please check app permissions.')
          }
        }
      } else {
        const link = document.createElement('a')
        link.href = window.URL.createObjectURL(blob)
        link.download = filename
        document.body.appendChild(link)
        link.click()

        window.URL.revokeObjectURL(link.href)
        document.body.removeChild(link)
        loadingMessage()
        message.success(`File "${filename}" has started downloading.`)
      }
    } catch (error: unknown) {
      loadingMessage()
      let errorMessage = 'Download failed.'
      if (isAxiosError(error)) {
        if (error.response && error.response.data) {
          try {
            const errorText = await (error.response.data as Blob).text()
            const errorJson = JSON.parse(errorText)
            errorMessage = errorJson.detail || 'Could not parse error details'
          } catch (e) {
            console.error('Unable to parse error blob', e)
            errorMessage = error.message || 'An unknown network error occurred'
          }
        }
      } else if (error instanceof Error) {
        errorMessage = error.message
      }
      message.error(errorMessage)
      console.error('Download failed:', error)
    }
  }

  function resetStore() {
    // 1. 关闭所有活跃的 WebSocket 连接
    wsConnections.value.forEach((ws) => ws.close())
    wsConnections.value.clear()

    // 2. 重置状态
    fileList.value = []
    taskList.value = []
    selectedFileId.value = null
    fileInfo.value = null
    error.value = null
    isLoading.value = false
    startTime.value = 0
    endTime.value = 0
  }

  // 新增 Action
  async function fetchSystemCapabilities() {
    try {
      const response = await axios.get<SystemCapabilities>(API_ENDPOINTS.GET_CAPABILITIES)
      systemCapabilities.value = response.data
    } catch (error) {
      console.error('Failed to fetch system capabilities:', error)
      // 默认无硬件加速
      systemCapabilities.value = { has_hardware_acceleration: false, hardware_type: null }
    }
  }

  async function initializeStore() {
    await fetchFileList()
    await fetchTaskList()
    await fetchSystemCapabilities() // 初始化时获取能力
  }

  onUnmounted(() => {
    wsConnections.value.forEach((ws) => ws.close())
  })

  return {
    selectedFileId,
    fileList,
    taskList,
    isLoading,
    fileInfo,
    error,
    startTime,
    endTime,
    triggerTaskPanel,
    totalDuration,
    hasActiveTasks,
    selectFile,
    fetchFileList,
    fetchTaskList,
    addFile,
    addTasks,
    removeFile,
    removeTask,
    updateTrimTimes,
    selectFileByTask,
    initializeStore,
    updateTaskProgress,
    downloadFile,
    checkAndReconnectWebSockets,
    fetchSingleTaskAndUpdate,
    systemCapabilities, // 导出状态
    fetchSystemCapabilities, // 导出方法
    resetStore, // 导出此方法
  }
})
