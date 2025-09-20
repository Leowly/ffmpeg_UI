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
// 移除了未使用的 UploadOutlined
import { DeleteOutlined, InboxOutlined } from '@ant-design/icons-vue'
import axios from 'axios'
import { API_ENDPOINTS } from '@/api/index'
import { useFileStore } from '@/stores/fileStore' // 👈 1. 导入 store

const fileStore = useFileStore()
import type { UploadFile as AntdUploadFile, UploadChangeParam } from 'ant-design-vue'

interface MyUploadFile extends AntdUploadFile {
  id?: string
}

const fileList = ref<MyUploadFile[]>([])
const selectedFileUid = ref<string | null>(null)

const handleChange = (info: UploadChangeParam) => {
  // 1. 保留你现有的成功/失败提示逻辑
  if (info.file.status === 'done') {
    message.success(`${info.file.name} 文件上传成功`);
    const serverResponse = info.file.response;
    if (serverResponse) {
      // 这里的 uid 更新非常重要，它保证了即使在刷新前，
      // 新上传的文件也能被正确地选中或删除。
      info.file.uid = serverResponse.file_id;
    }
  } else if (info.file.status === 'error') {
    const errorMsg = info.file.response?.error || '上传失败';
    message.error(`${info.file.name} 文件上传失败: ${errorMsg}`);
  }

  // 2. 检查这是否是最后一个正在上传的文件
  // 当一个文件变为 'done' 或 'error' 时，我们检查列表里是否还有其他文件处于 'uploading' 状态
  if (info.file.status === 'done' || info.file.status === 'error') {
    // 使用 .some() 检查是否还存在正在上传的文件
    const isStillUploading = fileList.value.some(file => file.status === 'uploading');

    // 如果没有任何文件在上传了，说明整批任务已结束
    if (!isStillUploading) {
      console.log("所有文件上传完毕，准备从服务器同步最新列表...");
      // 在这里安全地调用 fetchUserFiles，进行最终同步
      fetchUserFiles();
    }
  }
};
onMounted(() => {
  fetchUserFiles()
})

const fetchUserFiles = async () => {
  try {
    const response = await axios.get<MyUploadFile[]>(API_ENDPOINTS.FILE_LIST)
    fileList.value = response.data
    // 移除了成功的消息提示，保持界面安静
  } catch (error) {
    console.error('获取文件列表失败:', error)
    // 只在失败时提示用户
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

const removeFile = async (uid: string) => {
  const fileToRemove = fileList.value.find((file) => file.uid === uid)
  if (!fileToRemove) return

  const file_id = fileToRemove.response?.file_id || fileToRemove.id

  // 如果文件从未上传成功（没有 file_id），则直接从前端移除
  if (!file_id) {
    updateFrontendFileList(uid)
    message.success('文件已从列表移除')
    return
  }

  // 如果有 file_id，则调用后端 API
  try {
    await axios.delete(API_ENDPOINTS.FILE_DELETE(file_id))
    updateFrontendFileList(uid)
    message.success('文件已从服务器和列表移除')
  } catch (error) {
    console.error('删除文件失败:', error)
    message.error('从服务器删除文件失败，请重试')
  }
}

const updateFrontendFileList = (uid: string) => {
  fileList.value = fileList.value.filter((file) => file.uid !== uid)
  if (selectedFileUid.value === uid) {
    selectedFileUid.value = null
  }
}
const handleFileSelect = (fileId: string) => {
  // 如果点击的是已经选中的文件，则取消选中
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
    padding: 0px 0; /* 从 12px 减小到 8px，或者你觉得合适的任何值 */
  }
}
</style>
