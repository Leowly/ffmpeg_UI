// src/stores/fileStore.ts
import { defineStore } from 'pinia'
import { ref, type Ref, computed } from 'vue'
import axios, { isAxiosError } from 'axios'
import { API_ENDPOINTS } from '@/api'
import { message } from 'ant-design-vue'

// --- 类型定义 ---

export interface UserFile {
  uid: string
  id: string
  name: string
  status: 'done' | 'uploading' | 'error'
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
  id: number;
  ffmpeg_command: string;
  output_path: string | null;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  details: string | null;
  owner_id: number;
}

// --- Store 定义 ---

export const useFileStore = defineStore('file', () => {
  // --- State ---

  // 文件列表相关
  const fileList: Ref<UserFile[]> = ref([])
  const selectedFileId = ref<string | null>(null)
  const taskList: Ref<Task[]> = ref([]) // 新增：任务列表

  // 单个文件详细信息相关 (之前在 SingleFileWorkspace 组件中)
  const isLoading = ref(false)
  const fileInfo = ref<FFProbeResult | null>(null)
  const error = ref<string | null>(null)

  // 文件裁剪时间相关
  const startTime = ref(0)
  const endTime = ref(0)

  // --- Getters ---

  const totalDuration = computed(() => {
    return fileInfo.value ? parseFloat(fileInfo.value.format.duration) : 0
  })

  const hasActiveTasks = computed(() => {
    return taskList.value.some(task => ['pending', 'processing'].includes(task.status));
  });

  // --- Actions ---

  // 从后端获取并更新文件列表
  async function fetchFileList() {
    try {
      const response = await axios.get<UserFile[]>(API_ENDPOINTS.FILE_LIST)
      fileList.value = response.data
    } catch (error) {
      console.error('Failed to fetch file list:', error)
      fileList.value = []
    }
  }

  // 新增：从后端获取并更新任务列表
  async function fetchTaskList() {
    try {
      const response = await axios.get<Task[]>(API_ENDPOINTS.TASK_LIST);
      taskList.value = response.data;
    } catch (error) {
      console.error('Failed to fetch task list:', error);
    }
  }

  // 获取单个文件的详细信息
  async function fetchFileInfo(fileId: string) {
    isLoading.value = true
    error.value = null

    try {
      const response = await axios.get<FFProbeResult>(API_ENDPOINTS.FILE_INFO(fileId))
      fileInfo.value = response.data
      // 成功获取信息后，重置裁剪时间
      const duration = parseFloat(response.data.format.duration)
      startTime.value = 0
      endTime.value = isNaN(duration) ? 0 : duration
    } catch (err: unknown) {
      let errorMessage = '无法连接到服务器或发生未知错误'
      if (isAxiosError(err)) {
        errorMessage = err.response?.data?.error || err.message
      } else if (err instanceof Error) {
        errorMessage = err.message
      }
      error.value = errorMessage
      message.error(`加载文件信息失败: ${errorMessage}`)
    } finally {
      isLoading.value = false
    }
  }

  // 选中一个文件，并触发信息获取
  function selectFile(fileId: string | null) {
    selectedFileId.value = fileId
    if (fileId) {
      fetchFileInfo(fileId)
    } else {
      // 如果取消选择，则清空文件详情
      fileInfo.value = null
      error.value = null
    }
  }

  // 添加一个文件到列表 (上传成功后调用)
  function addFile(file: UserFile) {
    fileList.value.push(file)
  }

  // 新增：添加多个任务到列表
  function addTasks(tasks: Task[]) {
    taskList.value.unshift(...tasks);
  }

  // 从列表中移除一个文件 (删除成功后调用)
  async function removeFile(fileId: string) {
    try {
      await axios.delete(API_ENDPOINTS.DELETE_FILE(fileId));
      fileList.value = fileList.value.filter((f) => f.id !== fileId);
      if (selectedFileId.value === fileId) {
        selectFile(null); // 如果删除的是当前选中的文件，则取消选中
      }
    } catch (error) {
      console.error('Failed to delete file:', error);
      // 抛出错误，以便 UI 层可以捕获并显示消息
      throw error;
    }
  }

  // 更新裁剪时间
  function updateTrimTimes({ start, end }: { start: number; end: number }) {
    startTime.value = start
    endTime.value = end
  }

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
    updateTrimTimes,
  }
})
