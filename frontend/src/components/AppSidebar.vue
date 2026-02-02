<!-- src/components/AppSidebar.vue -->
<template>
  <div class="sidebar-container">
    <div class="upload-section">
      <a-upload-dragger
        v-model:fileList="uploadComponentFileList"
        name="file"
        :multiple="true"
        :show-upload-list="false"
        :action="uploadUrl"
        :headers="uploadHeaders"
        :before-upload="beforeUpload"
        @change="handleUploadChange"
        @drop="handleDrop"
      >
        <p class="ant-upload-drag-icon">
          <inbox-outlined></inbox-outlined>
        </p>
        <p class="ant-upload-text">点击或拖拽文件到此区域以上传</p>
        <p class="ant-upload-hint">支持单个或批量上传</p>
      </a-upload-dragger>
    </div>

    <!-- 任务列表 -->
    <a-collapse v-model:activeKey="activeTaskPanelKey" ghost>
      <a-collapse-panel key="1">
        <template #header>
          <div class="divider-header">处理任务</div>
        </template>
        <div class="task-list-wrapper">
          <a-list
            v-if="fileStore.taskList.length > 0"
            item-layout="horizontal"
            :data-source="fileStore.taskList"
            class="task-list-container"
          >
            <template #renderItem="{ item: task }">
              <a-list-item class="task-item" @click="$emit('task-selected', task.id)">
                <template #actions>
                  <a-popconfirm
                    v-if="['completed', 'failed'].includes(task.status)"
                    title="确定要清除这个任务记录吗？"
                    ok-text="确定"
                    cancel-text="取消"
                    @confirm="fileStore.removeTask(task.id)"
                  >
                    <a @click.stop><delete-outlined /></a>
                  </a-popconfirm>
                </template>
                <a-list-item-meta :description="getTaskDescription(task)">
                  <template #title>
                    <a-tooltip>
                      <span class="task-title"
                        >任务 #{{ task.id }}</span
                      >
                    </a-tooltip>
                  </template>
                  <template #avatar>
                    <a-spin v-if="['pending', 'processing'].includes(task.status)" />
                    <CheckCircleOutlined
                      v-else-if="task.status === 'completed'"
                      style="color: #52c41a; font-size: 24px"
                    />
                    <CloseCircleOutlined
                      v-else-if="task.status === 'failed'"
                      style="color: #ff4d4f; font-size: 24px"
                    />
                  </template>
                </a-list-item-meta>
              </a-list-item>
            </template>
          </a-list>
        </div>
      </a-collapse-panel>
    </a-collapse>

    <!-- 文件列表 -->
    <a-divider>媒体文件</a-divider>
    <a-list
      v-if="fileStore.fileList.length > 0"
      item-layout="horizontal"
      :data-source="fileStore.fileList"
      class="file-list-container"
    >
      <template #renderItem="{ item }">
        <a-list-item
          @click="() => handleFileSelect(item.id)"
          :class="{ 'selected-item': fileStore.selectedFileId === item.id }"
          class="file-item"
        >
          <template #actions>
            <a-spin v-if="item.status === 'uploading'" :indicator="progressIndicator(item)" />
            <a-popconfirm
              v-if="item.status === 'uploading'"
              title="确定要取消上传吗？"
              ok-text="确定"
              cancel-text="取消"
              @confirm="handleCancelUpload(item.uid)"
            >
              <a @click.stop><close-outlined /></a>
            </a-popconfirm>
            <a-popconfirm
              v-else
              title="确定要删除这个文件吗？"
              ok-text="确定"
              cancel-text="取消"
              @confirm="handleDeleteFile(item.id)"
            >
              <a @click.stop><delete-outlined /></a>
            </a-popconfirm>
          </template>
          <a-list-item-meta :description="`${(item.size / 1024 / 1024).toFixed(2)} MB`">
            <template #title>
              <a-tooltip :title="item.name" placement="topLeft">
                <span class="file-name">{{ item.name }}</span>
              </a-tooltip>
            </template>
            <template #avatar>
              <video-camera-outlined v-if="item.name.match(/\.(mp4|mov|mkv|avi|webm)$/i)" />
              <customer-service-outlined
                v-else-if="item.name.match(/\.(mp3|wav|flac|aac|ogg)$/i)"
              />
              <file-outlined v-else />
            </template>
          </a-list-item-meta>
        </a-list-item>
      </template>
    </a-list>
    <a-empty v-else description="暂无媒体文件" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, h } from 'vue'
import { useFileStore, type Task, type UserFile } from '@/stores/fileStore'
import { useAuthStore } from '@/stores/authStore'
import { API_ENDPOINTS } from '@/api'
import { message, type UploadChangeParam, type UploadFile } from 'ant-design-vue'
import {
  InboxOutlined,
  VideoCameraOutlined,
  CustomerServiceOutlined,
  FileOutlined,
  DeleteOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  CloseOutlined,
} from '@ant-design/icons-vue'

const emit = defineEmits(['task-selected', 'file-selected'])

const fileStore = useFileStore()
const authStore = useAuthStore()

const activeTaskPanelKey = ref<string[]>([]) // 控制折叠面板的展开

// 监听来自 store 的信号，以展开面板
watch(
  () => fileStore.triggerTaskPanel,
  (shouldExpand) => {
    if (shouldExpand) {
      activeTaskPanelKey.value = ['1']
    }
  },
)

// 这个 ref 仅用于 antd-upload 组件的 v-model，不作为核心状态
const uploadComponentFileList = ref<UploadFile[]>([])

const uploadUrl = computed(() => API_ENDPOINTS.UPLOAD_FILE)
const uploadHeaders = computed(() => ({
  Authorization: `Bearer ${authStore.token}`,
}))

/**
 * 处理文件上传状态的变化
 */
const handleUploadChange = (info: UploadChangeParam) => {
  if (info.file.status === 'uploading') {
    const percent = info.file.percent || 0
    fileStore.updateFileProgress(info.file.uid, Math.round(percent))
  } else if (info.file.status === 'done') {
    message.success(`${info.file.name} 文件上传成功`)
    fileStore.updateFileStatus(info.file.uid, 'done')
    fileStore.addFile(info.file.response)
  } else if (info.file.status === 'error') {
    const errorMsg = info.file.response?.detail || '网络错误'
    message.error(`${info.file.name} 文件上传失败: ${errorMsg}`)
    fileStore.updateFileStatus(info.file.uid, 'error')
  }
}

/**
 * 处理文件拖拽事件 (可在此处添加逻辑)
 */
const handleDrop = (e: DragEvent) => {
  console.log('Files dropped:', e)
}

const ALLOWED_EXTENSIONS = [
  '.mp4', '.m4v', '.mov', '.mkv', '.webm', '.flv', '.avi', '.wmv',
  '.mpg', '.mpeg', '.m2ts', '.mts', '.ts', '.vob', '.3gp', '.3g2',
  '.ogv', '.rm', '.rmvb', '.asf', '.divx', '.f4v', '.h264', '.hevc',
  '.mp3', '.aac', '.flac', '.wav', '.ogg', '.m4a', '.wma', '.opus',
  '.alac', '.aiff', '.ape', '.ac3', '.dts', '.pcm', '.amr',
]

const MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024 // 2GB

const beforeUpload = (file: UploadFile) => {
  const ext = '.' + (file.name?.split('.').pop() || '').toLowerCase()

  if (!ALLOWED_EXTENSIONS.includes(ext)) {
    message.error(`不支持的文件格式: ${ext}`)
    return false
  }

  if (file.size !== undefined && file.size > MAX_FILE_SIZE) {
    message.error(`文件大小不能超过 2GB`)
    return false
  }

  const tempFile: UserFile = {
    uid: file.uid,
    id: file.uid,
    name: file.name || '未知文件',
    status: 'uploading',
    size: file.size || 0,
    uploadProgress: 0,
    response: {
      file_id: '',
      original_name: file.name || '',
      temp_path: '',
    },
  }
  fileStore.addFile(tempFile)

  return true
}

const progressIndicator = (item: UserFile) => {
  return h('div', { class: 'upload-progress-circle' }, [
    h(
      'svg',
      { viewBox: '0 0 36 36', class: 'progress-ring' },
      {
        default: () => [
          h('path', {
            d: 'M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831',
            stroke: '#e6e6e6',
            'stroke-width': '3',
            fill: 'none',
          }),
          h('path', {
            d: 'M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831',
            stroke: '#1890ff',
            'stroke-width': '3',
            fill: 'none',
            'stroke-dasharray': `${item.uploadProgress}, 100`,
          }),
        ],
      },
    ),
    h('span', { class: 'progress-text' }, `${item.uploadProgress}%`),
  ])
}

interface UploadInstance {
  file?: { uid?: string }
  abort?: () => void
}

const handleCancelUpload = (fileUid: string) => {
  fileStore.removeUploadingFile(fileUid)
  const uploadInstances = (window as unknown as { __uploadInstances?: UploadInstance[] }).__uploadInstances
  const uploadInstance = uploadInstances?.find(
    (instance) => instance.file?.uid === fileUid,
  )
  if (uploadInstance) {
    uploadInstance.abort?.()
  }
  message.info('上传已取消')
}

/**
 * 选中文件时，调用 store 的 action
 */
const handleFileSelect = (fileId: string) => {
  fileStore.selectFile(fileId)
  emit('file-selected')
}

/**
 * 删除文件时，调用 store 的 action
 */
const handleDeleteFile = (fileId: string) => {
  fileStore.removeFile(fileId)
}

/**
 * 从任务对象中提取并格式化描述信息
 */
const getTaskDescription = (task: Task): string => {
  // 对于已完成的任务，尝试从 fileList 中获取原始文件名
  if (task.status === 'completed' && task.result_file_id) {
    const resultFile = fileStore.fileList.find((f) => f.id === String(task.result_file_id))
    if (resultFile) {
      return `-> ${resultFile.name}`
    }
  }

  // 对于其他任务，显示源文件名
  const sourceName = task.source_filename || '未知文件'
  if (task.status === 'completed' && task.output_path) {
    return `-> ${sourceName}`
  }

  return `源: ${sourceName}`
}
</script>

<style scoped>
.sidebar-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  box-sizing: border-box;
}

.file-list-container {
  flex-grow: 1;
  overflow-y: auto;
  margin-top: 8px;
  padding-right: 4px;
}

.task-list-wrapper {
  max-height: 200px;
  overflow-y: auto;
  padding-right: 4px; /* 为滚动条留出空间 */
}

/* 优化滚动条样式 */
.file-list-container::-webkit-scrollbar,
.task-list-wrapper::-webkit-scrollbar {
  width: 6px;
}
.file-list-container::-webkit-scrollbar-thumb,
.task-list-wrapper::-webkit-scrollbar-thumb {
  background: #cccccc;
  border-radius: 3px;
}
.file-list-container::-webkit-scrollbar-thumb:hover,
.task-list-wrapper::-webkit-scrollbar-thumb:hover {
  background: #aaaaaa;
}

.file-item,
.task-item {
  cursor: pointer;
  padding: 8px 12px;
}

.file-item:hover,
.task-item:hover {
  background-color: #f5f5f5;
}

.selected-item {
  background-color: #e6f7ff !important;
  border-right: 3px solid #1890ff;
}

.task-title,
.file-name {
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: block;
}

.sidebar-container :deep(.ant-list-item-meta-description) {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 180px; /* 限制描述文本宽度 */
}

/* 紧凑化分隔符样式 */
.sidebar-container :deep(.ant-divider-with-text) {
  margin: 12px 0;
  font-weight: 500;
  color: rgba(0, 0, 0, 0.65);
}

.divider-header {
  font-weight: 500;
  color: rgba(0, 0, 0, 0.65);
  text-align: center;
}

.sidebar-container :deep(.ant-collapse) {
  margin: 12px 0;
  border: none; /* 移除边框 */
  background-color: transparent; /* 移除背景色 */
}
.sidebar-container :deep(.ant-collapse > .ant-collapse-item) {
  border-bottom: none; /* 移除项的下边框 */
}
.sidebar-container :deep(.ant-collapse-header) {
  padding: 0 !important; /* 移除内边距 */
  display: flex;
  align-items: center;
  justify-content: center; /* 居中文本 */
  color: rgba(0, 0, 0, 0.85);
  font-weight: 500;
}
.sidebar-container :deep(.ant-collapse-content) {
  border-top: none; /* 移除内容的顶部边框 */
}
.sidebar-container :deep(.ant-collapse-content-box) {
  padding: 0 !important;
}
.sidebar-container :deep(.ant-collapse-arrow) {
  display: none; /* 隐藏默认的箭头 */
}

@media (max-width: 768px) {
  .sidebar-container :deep(.ant-upload-drag-icon),
  .sidebar-container :deep(.ant-upload-hint) {
    display: none;
  }
  .sidebar-container :deep(.ant-upload-text) {
    font-size: 14px;
  }
}

.upload-progress-circle {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}

.progress-ring {
  width: 28px;
  height: 28px;
  transform: rotate(-90deg);
}

.progress-ring path:nth-child(2) {
  transition: stroke-dasharray 0.3s ease;
}

.progress-text {
  position: absolute;
  font-size: 10px;
  font-weight: 500;
  color: #1890ff;
}
</style>
