<script setup lang="ts">
import { ref, reactive, watch, computed, onUnmounted } from 'vue'
import { useFileStore, type UserFile } from '@/stores/fileStore'
import { API_ENDPOINTS } from '@/api'
import { message } from 'ant-design-vue'
import { DownloadOutlined } from '@ant-design/icons-vue'
import axios from 'axios'

interface DownloadItem {
  fileId: string
  fileName: string
  status: 'pending' | 'downloading' | 'completed' | 'error'
  progress: number
  error?: string
}

interface DownloadProgress {
  fileId: string
  loaded: number
  total: number
}

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits(['update:visible'])

const fileStore = useFileStore()
const selectedFileIds = ref<string[]>([])
const downloadQueue = ref<DownloadItem[]>([])
const isDownloading = ref(false)
const currentDownloadIndex = ref(-1)

// Track active download XHRs for abort
const activeXHRs = ref<Map<string, XMLHttpRequest>>(new Map())

const canStartDownload = computed(() => 
  selectedFileIds.value.length > 0 && !isDownloading.value
)

const completedCount = computed(() => 
  downloadQueue.value.filter(d => d.status === 'completed').length
)

const totalCount = computed(() => downloadQueue.value.length)

watch(
  () => props.visible,
  (isVisible) => {
    if (isVisible) {
      // Reset state when modal opens
      selectedFileIds.value = []
      downloadQueue.value = []
      isDownloading.value = false
      currentDownloadIndex.value = -1
      
      // Fetch file list if empty
      if (fileStore.fileList.length === 0) {
        fileStore.fetchFileList()
      }
    }
  }
)

const handleOk = () => {
  if (selectedFileIds.value.length === 0) {
    message.warning('请选择要下载的文件')
    return
  }
  
  // Build download queue
  downloadQueue.value = selectedFileIds.value.map(fileId => {
    const file = fileStore.fileList.find(f => f.id === fileId)
    return {
      fileId,
      fileName: file?.name || fileId,
      status: 'pending',
      progress: 0
    }
  })
  
  // Start downloads
  isDownloading.value = true
  startNextDownload()
}

const handleCancel = () => {
  emit('update:visible', false)
}

const startNextDownload = async () => {
  const nextIndex = downloadQueue.value.findIndex(d => d.status === 'pending')
  
  if (nextIndex === -1) {
    // All downloads completed
    isDownloading.value = false
    const errorCount = downloadQueue.value.filter(d => d.status === 'error').length
    if (errorCount === 0) {
      message.success(`已成功下载 ${downloadQueue.value.length} 个文件`)
    } else {
      message.warning(`下载完成，成功 ${completedCount.value} 个，失败 ${errorCount} 个`)
    }
    return
  }
  
  currentDownloadIndex.value = nextIndex
  const item = downloadQueue.value[nextIndex]
  item.status = 'downloading'
  
  await downloadFile(item)
}

const downloadFile = async (item: DownloadItem) => {
  const downloadUrl = API_ENDPOINTS.DOWNLOAD_FILE(item.fileId)
  
  try {
    // Create XHR for progress tracking
    const xhr = new XMLHttpRequest()
    activeXHRs.value.set(item.fileId, xhr)
    
    await new Promise<void>((resolve, reject) => {
      xhr.open('GET', downloadUrl, true)
      xhr.responseType = 'blob'
      
      xhr.onprogress = (event) => {
        if (event.lengthComputable) {
          item.progress = Math.round((event.loaded / event.total) * 100)
        }
      }
      
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          const blob = xhr.response
          const contentDisposition = xhr.getResponseHeader('content-disposition')
          let filename = item.fileName
          
          if (contentDisposition) {
            const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/)
            if (filenameMatch && filenameMatch.length > 1) {
              filename = decodeURIComponent(filenameMatch[1])
            }
          }
          
          // Trigger download
          const link = document.createElement('a')
          link.href = window.URL.createObjectURL(blob)
          link.download = filename
          document.body.appendChild(link)
          link.click()
          window.URL.revokeObjectURL(link.href)
          document.body.removeChild(link)
          
          item.status = 'completed'
          item.progress = 100
          resolve()
        } else {
          item.status = 'error'
          item.error = `HTTP ${xhr.status}`
          reject(new Error(`HTTP ${xhr.status}`))
        }
      }
      
      xhr.onerror = () => {
        item.status = 'error'
        item.error = 'Network error'
        reject(new Error('Network error'))
      }
      
      xhr.send()
    })
  } catch (error) {
    console.error(`Download failed for ${item.fileName}:`, error)
  } finally {
    activeXHRs.value.delete(item.fileId)
    // Continue with next download
    startNextDownload()
  }
}

const cancelAllDownloads = () => {
  // Abort all active downloads
  activeXHRs.value.forEach((xhr, fileId) => {
    xhr.abort()
  })
  activeXHRs.value.clear()
  
  // Mark remaining as pending
  downloadQueue.value.forEach(item => {
    if (item.status === 'downloading') {
      item.status = 'pending'
      item.progress = 0
    }
  })
  
  isDownloading.value = false
  message.info('已取消下载')
}

// Cleanup on unmount
onUnmounted(() => {
  cancelAllDownloads()
})
</script>

<template>
  <a-modal
    :open="props.visible"
    title="一键下载"
    :width="600"
    :footer="null"
    @cancel="handleCancel"
  >
    <div class="download-modal-content">
      <!-- File Selection Section -->
      <div v-if="!isDownloading" class="file-selection">
        <a-alert
          message="选择要下载的文件"
          description="选择完成后点击开始下载，关闭弹窗后下载将在后台继续进行"
          type="info"
          show-icon
          style="margin-bottom: 16px"
        />
        
        <div class="file-list">
          <a-checkbox-group
            v-if="fileStore.fileList.length > 0"
            v-model:value="selectedFileIds"
            style="width: 100%"
          >
            <a-row :gutter="[8, 8]">
              <a-col v-for="file in fileStore.fileList" :key="file.id" :span="24">
                <a-checkbox :value="file.id">
                  {{ file.name }}
                  <span class="file-size">({{ (file.size / 1024 / 1024).toFixed(2) }} MB)</span>
                </a-checkbox>
              </a-col>
            </a-row>
          </a-checkbox-group>
          <a-empty v-else description="没有可下载的文件" />
        </div>
        
        <div class="modal-footer">
          <a-button @click="handleCancel">取消</a-button>
          <a-button
            type="primary"
            :disabled="selectedFileIds.length === 0"
            @click="handleOk"
          >
            <DownloadOutlined />
            开始下载 ({{ selectedFileIds.length }})
          </a-button>
        </div>
      </div>
      
      <!-- Download Progress Section -->
      <div v-else class="download-progress">
        <a-alert
          message="下载进行中"
          description="关闭弹窗后下载将继续在后台进行"
          type="info"
          show-icon
          style="margin-bottom: 16px"
        />
        
        <div class="progress-list">
          <div
            v-for="(item, index) in downloadQueue"
            :key="item.fileId"
            class="progress-item"
            :class="{ 'is-active': index === currentDownloadIndex }"
          >
            <div class="progress-info">
              <span class="file-name">{{ item.fileName }}</span>
              <span v-if="item.status === 'completed'" class="status-text success">已完成</span>
              <span v-else-if="item.status === 'error'" class="status-text error">{{ item.error }}</span>
              <span v-else-if="item.status === 'downloading'" class="status-text">{{ item.progress }}%</span>
              <span v-else class="status-text">等待中</span>
            </div>
            <a-progress
              :percent="item.progress"
              :status="item.status === 'completed' ? 'success' : item.status === 'error' ? 'exception' : 'active'"
              :show-info="false"
              size="small"
            />
          </div>
        </div>
        
        <div class="progress-summary">
          <span>进度: {{ completedCount }} / {{ totalCount }}</span>
        </div>
        
        <div class="modal-footer">
          <a-button @click="handleCancel">关闭弹窗（后台继续）</a-button>
          <a-button danger @click="cancelAllDownloads">取消全部</a-button>
        </div>
      </div>
    </div>
  </a-modal>
</template>

<style scoped>
.download-modal-content {
  min-height: 300px;
}

.file-selection {
  max-height: 400px;
  overflow-y: auto;
}

.file-list {
  margin-bottom: 16px;
}

.file-size {
  color: #999;
  font-size: 12px;
  margin-left: 8px;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #f0f0f0;
}

.download-progress {
  max-height: 500px;
  overflow-y: auto;
}

.progress-list {
  margin-bottom: 16px;
}

.progress-item {
  padding: 12px;
  margin-bottom: 8px;
  background: #fafafa;
  border-radius: 6px;
  border: 1px solid #f0f0f0;
}

.progress-item.is-active {
  border-color: #1890ff;
  background: #e6f7ff;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.progress-info .file-name {
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 300px;
}

.status-text {
  font-size: 12px;
}

.status-text.success {
  color: #52c41a;
}

.status-text.error {
  color: #ff4d4f;
}

.progress-summary {
  text-align: center;
  font-weight: 500;
  margin-bottom: 16px;
  color: #1890ff;
}
</style>
