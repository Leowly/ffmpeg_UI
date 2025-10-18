<!-- src/components/AppSidebar.vue -->
<template>
  <div class="sidebar-container">
      <div class="upload-section">
            <a-upload-dragger
              v-model:fileList="fileList"
              name="file"
              :multiple="true"
              :show-upload-list="false"
              :action="uploadUrl"
              :headers="uploadHeaders"
              @change="handleUploadChange" @drop="handleDrop"
            >
        <p class="ant-upload-drag-icon">
          <inbox-outlined></inbox-outlined>
        </p>
        <p class="ant-upload-text">点击或拖拽文件到此区域以上传</p>
        <p class="ant-upload-hint">支持单个或批量上传</p>
      </a-upload-dragger>
    </div>

    <!-- 任务列表 -->
    <a-divider v-if="fileStore.taskList.length > 0">处理任务</a-divider>
    <a-list
      v-if="fileStore.taskList.length > 0"
      item-layout="horizontal"
      :data-source="fileStore.taskList"
      class="task-list-container"
    >
      <template #renderItem="{ item: task }">
        <a-list-item class="task-item">
          <template #actions>
            <a-tooltip v-if="task.status === 'completed'" title="下载文件">
              <a @click.prevent="downloadTaskOutput(task.id)"><DownloadOutlined /></a>
            </a-tooltip>
            <a-tooltip v-if="task.status === 'failed'" :title="task.details || '未知错误'">
              <ExclamationCircleOutlined style="color: red" />
            </a-tooltip>
          </template>
          <a-list-item-meta :description="getTaskDescription(task)">
            <template #title>
              <span class="task-title">任务 #{{ task.id }}</span>
            </template>
            <template #avatar>
              <a-spin v-if="task.status === 'processing' || task.status === 'pending'" />
              <CheckCircleOutlined v-else-if="task.status === 'completed'" style="color: green; font-size: 24px;" />
              <CloseCircleOutlined v-else-if="task.status === 'failed'" style="color: red; font-size: 24px;" />
            </template>
          </a-list-item-meta>
        </a-list-item>
      </template>
    </a-list>

    <!-- 文件列表 -->
    <a-divider>媒体文件</a-divider>
    <a-list
      item-layout="horizontal"
      :data-source="fileStore.fileList"
      class="file-list-container"
    >
      <template #renderItem="{ item }">
        <a-list-item
          @click="() => handleFileSelect(item.id)"
          :class="{ 'selected-item': fileStore.selectedFileId === item.id }"
        >
          <template #actions>
            <a key="list-load-more-edit" @click.stop="handleDeleteFile(item.id)"><delete-outlined /></a>
          </template>
          <a-list-item-meta :description="`${(item.size / 1024 / 1024).toFixed(2)} MB`">
            <template #title>
              <a>{{ item.name }}</a>
            </template>
            <template #avatar>
              <video-camera-outlined v-if="item.name.match(/\.(mp4|mov|mkv|avi)$/i)" />
              <customer-service-outlined v-else />
            </template>
          </a-list-item-meta>
        </a-list-item>
      </template>
    </a-list>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue';
import { useFileStore, type UserFile, type Task } from '@/stores/fileStore';
import { useAuthStore } from '@/stores/authStore';
import { API_ENDPOINTS } from '@/api';
import { message, type UploadChangeParam } from 'ant-design-vue';
import {
  InboxOutlined,
  VideoCameraOutlined,
  CustomerServiceOutlined,
  DeleteOutlined,
  DownloadOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons-vue';

const fileStore = useFileStore();
const authStore = useAuthStore();

const fileList = ref<UserFile[]>([]);

const uploadUrl = computed(() => API_ENDPOINTS.UPLOAD_FILE);
const uploadHeaders = computed(() => ({
  Authorization: `Bearer ${authStore.token}`,
}));

let pollingInterval: number | null = null;

const startPolling = () => {
  if (pollingInterval) return; // 如果已经在轮询，则不重复启动
  pollingInterval = window.setInterval(async () => {
    if (fileStore.hasActiveTasks) {
      await fileStore.fetchTaskList();
    } else {
      stopPolling(); // 如果没有活动任务，则停止轮询
    }
  }, 5000); // 每5秒轮询一次
};

const stopPolling = () => {
  if (pollingInterval) {
    clearInterval(pollingInterval);
    pollingInterval = null;
  }
};

watch(() => fileStore.hasActiveTasks, (hasActive) => {
  if (hasActive) {
    startPolling();
  } else {
    stopPolling();
  }
}, { immediate: true });

onMounted(() => {
  if (fileStore.hasActiveTasks) {
    startPolling();
  }
});

onBeforeUnmount(() => {
  stopPolling();
});

const handleUploadChange = (info: UploadChangeParam) => {
  if (info.file.status === 'done') {
    message.success(`${info.file.name} 文件上传成功`);
    fileStore.addFile(info.file.response as UserFile);
  } else if (info.file.status === 'error') {
    message.error(`${info.file.name} 文件上传失败`);
  }
};

const handleDrop = (e: DragEvent) => {
  console.log(e);
};

const handleFileSelect = (fileId: string) => {
  fileStore.selectFile(fileId);
};

const handleDeleteFile = async (fileId: string) => {
  try {
    await fileStore.removeFile(fileId);
    message.success('文件删除成功');
  } catch {
    message.error('文件删除失败');
  }
};

const getTaskDescription = (task: Task) => {
  const commandParts = task.ffmpeg_command.split(' ');
  const outputIndex = commandParts.findIndex(part => part.includes('_processed'));
  if (outputIndex !== -1) {
    return `-> ${decodeURIComponent(commandParts[outputIndex].split('/').pop() || '')}`;
  }
  return '生成中...';
};

const downloadTaskOutput = (taskId: number) => {
  const url = API_ENDPOINTS.DOWNLOAD_TASK(taskId);
  const token = authStore.token;

  // 使用 fetch 和 headers 来处理认证
  fetch(url, {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  })
  .then(async res => {
    if (res.ok) {
      const blob = await res.blob();
      const contentDisposition = res.headers.get('content-disposition');
      let filename = 'downloaded_file';
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename="?(.+)"?/i);
        if (filenameMatch && filenameMatch.length > 1) {
          filename = filenameMatch[1];
        }
      }
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(link.href);
    } else {
      const errorData = await res.json();
      message.error(`下载失败: ${errorData.detail || res.statusText}`);
    }
  })
  .catch(err => {
    message.error(`下载请求失败: ${err}`);
  });
};

</script>

<style scoped>
.sidebar-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  box-sizing: border-box;
}

.file-list-container, .task-list-container {
  flex-grow: 1;
  overflow-y: auto;
  margin-top: 8px; /* 减少间隙 */
  padding-right: 4px; /* 避免与滚动条贴边 */
}

.selected-item {
  background-color: #e6f7ff;
  border-right: 3px solid #1890ff;
}

.task-title {
  font-weight: 500;
}

.ant-list-item-meta-description {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 200px; /* 根据需要调整 */
}
.error-log-pre {
  background-color: #f5f5f5;
  padding: 12px;
  border-radius: 4px;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 60vh;
  overflow-y: auto;
}

@media (max-width: 768px) {
  .sidebar-container :deep(.ant-upload-drag-icon) {
    display: none;
  }
  .sidebar-container :deep(.ant-upload-hint) {
    display: none;
  }
}

/* 减少分隔符（标题）上下间距，使“处理任务”“媒体文件”等更紧凑 */
.sidebar-container :deep(.ant-divider) {
  margin: 10px 0; /* 默认较大，缩小为 10px */
}
.sidebar-container :deep(.ant-divider-inner-text) {
  padding: 2px; /* 减少内边距 */
  line-height: 0; /* 紧凑行高 */
  font-size: 15px;
}
.sidebar-container .task-title {
  margin: 0;
  padding: 0;
  line-height: 1.2;
}
</style>
