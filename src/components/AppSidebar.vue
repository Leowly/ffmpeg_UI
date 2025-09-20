<!-- src/components/AppSidebar.vue -->
<template>
  <div class="app-sidebar">
    <h2>文件管理</h2>

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
import { ref, onMounted } from 'vue';
import { message } from 'ant-design-vue';
// 移除了未使用的 UploadOutlined
import { DeleteOutlined, InboxOutlined } from '@ant-design/icons-vue';
import axios from 'axios';
import { API_ENDPOINTS } from '@/api/index';

import type { UploadFile as AntdUploadFile, UploadChangeParam } from 'ant-design-vue';

interface MyUploadFile extends AntdUploadFile {
  id?: string;
}

const fileList = ref<MyUploadFile[]>([]);
const selectedFileUid = ref<string | null>(null);

// 简化后的 handleChange 函数
const handleChange = (info: UploadChangeParam) => {
  // 关键：在 'done' 状态时，用 info.file（包含 response） 替换掉 info.fileList 中对应的旧文件对象
  if (info.file.status === 'done') {
    const targetFile = info.fileList.find(file => file.uid === info.file.uid);
    if (targetFile) {
      // 将后端返回的 id 附加到文件对象上
      (targetFile as MyUploadFile).id = info.file.response?.file_id;
    }
    message.success(`${info.file.name} 文件上传成功.`);
  } else if (info.file.status === 'error') {
    message.error(`${info.file.name} 文件上传失败.`);
  }

  // 无论如何，都用最新的 fileList 更新我们的 ref
  fileList.value = info.fileList;
};

onMounted(() => {
  fetchUserFiles();
});

const fetchUserFiles = async () => {
  try {
    const response = await axios.get<MyUploadFile[]>(API_ENDPOINTS.FILE_LIST);
    fileList.value = response.data;
    // 移除了成功的消息提示，保持界面安静
  } catch (error) {
    console.error("获取文件列表失败:", error);
    // 只在失败时提示用户
    message.error('同步文件列表失败，请刷新页面重试');
  }
};

const beforeUpload = (file: AntdUploadFile) => {
  const isVideoOrAudio = file.type?.startsWith('video/') || file.type?.startsWith('audio/');
  if (!isVideoOrAudio) {
    message.error('只能上传视频或音频文件!');
    return false;
  }
  const isLt4G = file.size ? file.size / 1024 / 1024 / 1024 < 4 : true;
  if (!isLt4G) {
    message.error('文件大小不能超过 4GB!');
    return false;
  }
  return true;
};

const selectFile = (uid: string) => {
  selectedFileUid.value = uid;
};

const removeFile = async (uid: string) => {
  const fileToRemove = fileList.value.find(file => file.uid === uid);
  if (!fileToRemove) return;

  const file_id = fileToRemove.response?.file_id || fileToRemove.id;

  // 如果文件从未上传成功（没有 file_id），则直接从前端移除
  if (!file_id) {
    updateFrontendFileList(uid);
    message.success('文件已从列表移除');
    return;
  }

  // 如果有 file_id，则调用后端 API
  try {
    await axios.delete(API_ENDPOINTS.FILE_DELETE(file_id));
    updateFrontendFileList(uid);
    message.success('文件已从服务器和列表移除');
  } catch (error) {
    console.error("删除文件失败:", error);
    message.error('从服务器删除文件失败，请重试');
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
.file-list-container .ant-list-item.file-selected {
  background-color: #e6f7ff;
  border-left: 3px solid #1890ff;
  padding-left: 17px;
}
</style>
