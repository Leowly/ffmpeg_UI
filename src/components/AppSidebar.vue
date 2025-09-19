<!-- src/components/AppSidebar.vue -->
<template>
  <div class="app-sidebar">
    <h2>文件管理</h2>

    <a-upload-dragger
      v-model:file-list="fileList"
      name="file"
      :action="API_ENDPOINTS.FILE_UPLOAD"
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
      <p class="ant-upload-hint">拖拽即可上传</p>
    </a-upload-dragger>

    <a-list item-layout="horizontal" :data-source="fileList" class="file-list-container">
      <template #renderItem="{ item }">
        <a-list-item
          :class="{ 'file-selected': item.uid === selectedFileUid }"
          @click="selectFile(item.uid)"
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
import { ref } from 'vue'
import { message } from 'ant-design-vue'
// 引入 InboxOutlined 图标
import { DeleteOutlined, InboxOutlined } from '@ant-design/icons-vue'
import type { UploadFile, UploadChangeParam } from 'ant-design-vue'
import axios from 'axios';
import { API_ENDPOINTS } from '@/api/index'

const fileList = ref<UploadFile[]>([])
const selectedFileUid = ref<string | null>(null)

const handleChange = (info: UploadChangeParam) => {
  const newFileList = info.fileList.filter((file) => file.status !== 'removed')
  fileList.value = newFileList

  if (info.file.status !== 'uploading') {
    console.log('文件信息:', info.file)
  }
  if (info.file.status === 'done') {
    message.success(`${info.file.name} 文件上传成功.`)
    console.log('模拟后端成功响应:', info.file.response)
  } else if (info.file.status === 'error') {
    message.error(`${info.file.name} 文件上传失败.`)
    console.error('模拟后端错误响应:', info.file.response || info.file.error)
  }
}

const beforeUpload = (file: UploadFile) => {
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

const selectFile = (uid: string) => {
  selectedFileUid.value = uid
  console.log(`选中文件 UID: ${uid}`)
}

const removeFile = async (uid: string) => {
  // a. 从列表中找到要删除的文件对象
  const fileToRemove = fileList.value.find(file => file.uid === uid);
  if (!fileToRemove) return;

  // b. 检查文件是否已成功上传并有后端返回的 file_id
  const file_id = fileToRemove.response?.file_id;

  if (file_id) {
    // --- 文件已在服务器上，需要调用后端 API 删除 ---
    try {
      // c. 发送 DELETE 请求到后端
      await axios.delete(API_ENDPOINTS.FILE_DELETE(file_id));

      // d. 只有在后端成功删除后，才更新前端列表
      updateFrontendFileList(uid);
      message.success('文件已从服务器和列表移除');

    } catch (error) {
      // e. 如果后端删除失败，显示错误消息，并且不更新前端列表
      console.error("删除文件失败:", error);
      message.error('从服务器删除文件失败，请重试');
    }
  } else {
    // --- 文件从未成功上传到服务器 (例如上传失败或还在上传中) ---
    // f. 直接从前端列表移除即可
    updateFrontendFileList(uid);
    message.success('文件已从列表移除');
  }
};

const updateFrontendFileList = (uid: string) => {
  fileList.value = fileList.value.filter(file => file.uid !== uid);
  if (selectedFileUid.value === uid) {
    selectedFileUid.value = null;
  }
};
</script>

<style scoped>
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
  margin-top: 0;
  margin-bottom: 0;
  font-size: 1.2em;
  color: #333;
  text-align: center;
}

.upload-area {
  width: 100%;
}

/* 使用 :deep() 来修改子组件 a-upload-dragger 的内部样式 */
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
.file-list-container .ant-list-item.file-selected {
  background-color: #e6f7ff;
  border-left: 3px solid #1890ff;
  padding-left: 17px;
}
</style>
