<!-- src/components/AppSidebar.vue -->
<template>
  <div class="app-sidebar">
    <a-upload-dragger
      v-model:file-list="fileList"
      name="file"
      :action="API_ENDPOINTS.FILE_UPLOAD"
      :with-credentials="true"
      @change="handleChange"
      :before-upload="beforeUpload"
      :show-upload-list="false"
      multiple
      class="upload-area"
    >
      <p class="ant-upload-drag-icon">
        <inbox-outlined />
      </p>
      <p class="ant-upload-text">点击或拖拽文件到此区域上传</p>
      <p class="ant-upload-hint">支持视频和音频文件，单文件不超过 4GB</p>
    </a-upload-dragger>

    <a-list item-layout="horizontal" :data-source="fileList" class="file-list-container">
      <template #renderItem="{ item }">
        <a-list-item
          :class="{ 'list-item-selected': item.uid === fileStore.selectedFileId }"
          @click="handleFileSelect(item.uid)"
        >
          <a-list-item-meta>
            <template #title>
              {{ item.name }}
            </template>
            <template #description>
              <span v-if="item.size">{{ (item.size / 1024 / 1024).toFixed(2) }} MB</span>
              <a-tag v-if="item.status === 'uploading'" color="blue">上传中</a-tag>
              <a-tag v-else-if="item.status === 'done'" color="green">已完成</a-tag>
              <a-tag v-else-if="item.status === 'error'" color="red">失败</a-tag>
            </template>
          </a-list-item-meta>
          <template #actions>
            <a-tooltip title="删除文件">
              <a-button type="text" danger @click.stop="removeFile(item.uid)">
                <delete-outlined />
              </a-button>
            </a-tooltip>
          </template>
        </a-list-item>
      </template>
    </a-list>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { DeleteOutlined, InboxOutlined } from '@ant-design/icons-vue'
import axios from 'axios'
import { API_ENDPOINTS } from '@/api/index'
import { useFileStore } from '@/stores/fileStore'
import type { UploadFile as AntdUploadFile, UploadChangeParam } from 'ant-design-vue'

interface MyUploadFile extends AntdUploadFile {
  id?: string
}

const fileStore = useFileStore() // 只保留 Pinia store
const fileList = ref<MyUploadFile[]>([])
//  👇 1. 删除这个无用的、会引起混淆的局部 ref
// const selectedFileUid = ref<string | null>(null)

// handleChange 函数保持不变
const handleChange = (info: UploadChangeParam) => {
  if (info.file.status === 'done' || info.file.status === 'error') {
    const isStillUploading = fileList.value.some(file => file.status === 'uploading');
    if (!isStillUploading) {
      fetchUserFiles();
    }
  }

  if (info.file.status === 'done') {
    message.success(`${info.file.name} 文件上传成功`);
  } else if (info.file.status === 'error') {
    const errorMsg = info.file.response?.error || '上传失败';
    message.error(`${info.file.name} 文件上传失败: ${errorMsg}`);
  }
};

// fetchUserFiles, onMounted, beforeUpload 保持不变
onMounted(() => {
  fetchUserFiles()
})

const fetchUserFiles = async () => {
  try {
    const response = await axios.get<MyUploadFile[]>(API_ENDPOINTS.FILE_LIST)
    fileList.value = response.data
  } catch (error) {
    console.error('获取文件列表失败:', error)
    message.error('同步文件列表失败，请刷新页面重试')
  }
}

const beforeUpload = (file: AntdUploadFile) => {
  const isVideoOrAudio = file.type?.startsWith('video/') || file.type?.startsWith('audio/')
  if (!isVideoOrAudio) {
    message.error('只能上传视频或音频文件!')
    return false
  }
  const isLt4G = file.size ? file.size / 1024 / 1024 / 1024 < 4 : true
  if (!isLt4G) {
    message.error('文件大小不能超过 4GB!')
    return false
  }
  return true
}

// 👇 2. 修正核心的 removeFile 函数
const removeFile = async (uid: string) => {
  const fileToRemove = fileList.value.find((file) => file.uid === uid)
  if (!fileToRemove) return

  // 使用 uid 作为 file_id，因为它们现在是相同的
  const file_id = uid;

  try {
    await axios.delete(API_ENDPOINTS.FILE_DELETE(file_id))
    message.success(`文件 '${file_id}' 已从服务器移除`)

    // 从前端列表中移除
    fileList.value = fileList.value.filter((file) => file.uid !== uid)

    // 👇 3. 核心修正：检查并更新全局 Store！
    // 如果被删除的文件正是当前选中的文件
    if (fileStore.selectedFileId === uid) {
      // 就调用 store 的 action 来清空选择
      fileStore.selectFile(null)
    }

  } catch (error) {
    console.error('删除文件失败:', error)
    message.error('从服务器删除文件失败，请重试')
  }
}

// 移除了 updateFrontendFileList 函数，因为它的逻辑已经合并到 removeFile 中

// handleFileSelect 函数保持不变
const handleFileSelect = (fileId: string) => {
  if (fileStore.selectedFileId === fileId) {
    fileStore.selectFile(null)
  } else {
    fileStore.selectFile(fileId)
  }
}
</script>

<style scoped>
/* 样式部分保持不变，因为它们已经很好了 */
.app-sidebar {
  padding: 20px;
  background-color: #fff;
  height: 100%;
  box-sizing: border-box;
  border: 1px solid #d9d9d9;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.app-sidebar h2 {
  margin: 0;
  font-size: 1.2em;
  color: #333;
  text-align: center;
}

.upload-area {
  width: 100%;
}

:deep(.ant-upload-drag) {
  padding: 20px 0;
}
:deep(.ant-upload-drag-icon .anticon) {
  font-size: 32px;
  color: #1890ff;
}
:deep(.ant-upload-text) {
  font-size: 16px;
}
:deep(.ant-upload-hint) {
  font-size: 12px;
  color: #999;
}

.file-list-container {
  flex-grow: 1;
  overflow-y: auto;
}

.file-list-container .ant-list-item {
  cursor: pointer;
  transition: background-color 0.2s;
}
.file-list-container .ant-list-item:hover {
  background-color: #f0f2f5;
}

.list-item-selected {
  background-color: #e6f7ff; /* Ant Design 的主题蓝色浅色变体 */
  border-left: 3px solid #1890ff; /* 左侧蓝色边框 */
}

@media (max-width: 768px) {
  /* 直接隐藏图标 */
  :deep(.upload-area .ant-upload-drag-icon) {
    display: none;
  }

  /* 让文字居中 */
  :deep(.upload-area .ant-upload-text) {
    text-align: center;
  }

  :deep(.upload-area.ant-upload-drag) {
    padding: 0px 0;
  }
}
</style>
