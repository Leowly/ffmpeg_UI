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
            <!-- 仅当任务完成且有有效输出路径时显示下载按钮 -->
            <a-tooltip v-if="task.status === 'completed' && task.output_path" title="下载处理后的文件">
              <a @click.prevent="downloadTaskOutput(task)"><DownloadOutlined /></a>
            </a-tooltip>
            <a-tooltip v-if="task.status === 'failed'" :title="task.details || '未知错误'">
              <ExclamationCircleOutlined style="color: red" />
            </a-tooltip>
          </template>
          <a-list-item-meta :description="getTaskDescription(task)">
            <template #title>
              <a-tooltip :title="getTaskDescription(task)" placement="topLeft">
                <span class="task-title">任务 #{{ task.id }}</span>
              </a-tooltip>
            </template>
            <template #avatar>
              <a-spin v-if="['pending', 'processing'].includes(task.status)" />
              <CheckCircleOutlined v-else-if="task.status === 'completed'" style="color: #52c41a; font-size: 24px;" />
              <CloseCircleOutlined v-else-if="task.status === 'failed'" style="color: #ff4d4f; font-size: 24px;" />
            </template>
          </a-list-item-meta>
        </a-list-item>
      </template>
    </a-list>

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
            <a-popconfirm
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
              <customer-service-outlined v-else-if="item.name.match(/\.(mp3|wav|flac|aac|ogg)$/i)" />
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
import { ref, computed } from 'vue';
import { useFileStore, type Task } from '@/stores/fileStore';
import { useAuthStore } from '@/stores/authStore';
import { API_ENDPOINTS } from '@/api';
import { message, type UploadChangeParam, type UploadFile } from 'ant-design-vue';
import {
  InboxOutlined,
  VideoCameraOutlined,
  CustomerServiceOutlined,
  FileOutlined,
  DeleteOutlined,
  DownloadOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons-vue';

const fileStore = useFileStore();
const authStore = useAuthStore();

// 这个 ref 仅用于 antd-upload 组件的 v-model，不作为核心状态
const uploadComponentFileList = ref<UploadFile[]>([]);

const uploadUrl = computed(() => API_ENDPOINTS.UPLOAD_FILE);
const uploadHeaders = computed(() => ({
  Authorization: `Bearer ${authStore.token}`,
}));


/**
 * 处理文件上传状态的变化
 */
const handleUploadChange = (info: UploadChangeParam) => {
  if (info.file.status === 'done') {
    message.success(`${info.file.name} 文件上传成功`);
    // 调用 store 的 action 来添加文件，保持状态统一
    fileStore.addFile(info.file.response);
  } else if (info.file.status === 'error') {
    const errorMsg = info.file.response?.detail || '网络错误';
    message.error(`${info.file.name} 文件上传失败: ${errorMsg}`);
  }
};

/**
 * 处理文件拖拽事件 (可在此处添加逻辑)
 */
const handleDrop = (e: DragEvent) => {
  console.log('Files dropped:', e);
};

/**
 * 选中文件时，调用 store 的 action
 */
const handleFileSelect = (fileId: string) => {
  fileStore.selectFile(fileId);
};

/**
 * 删除文件时，调用 store 的 action
 */
const handleDeleteFile = (fileId: string) => {
  fileStore.removeFile(fileId);
};

/**
 * 从任务对象中提取并格式化描述信息
 */
const getTaskDescription = (task: Task): string => {
  if (task.output_path) {
    // 从完整路径中提取文件名
    const filename = task.output_path.split(/[\\/]/).pop();
    return `-> ${filename || '未知输出'}`;
  }
  return '正在准备任务...';
};

/**
 * 下载已完成任务的输出文件
 * @param task - 已完成的任务对象
 */
const downloadTaskOutput = async (task: Task) => {
  if (!task.output_path) {
    message.error("任务没有有效的输出文件路径。");
    return;
  }
  // 注意：因为新文件已经通过轮询加入文件列表，理论上可以直接从文件列表下载。
  // 但为了任务列表的独立功能性，这里保留通过任务ID下载的逻辑。
  // 后端需要一个 download-task/{taskId} 的接口
  const url = API_ENDPOINTS.DOWNLOAD_TASK(task.id);
  const token = authStore.token;

  try {
    const response = await fetch(url, {
      headers: { 'Authorization': `Bearer ${token}` }
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || `服务器错误: ${response.status}`);
    }

    const blob = await response.blob();
    const contentDisposition = response.headers.get('content-disposition');
    let filename = task.output_path.split(/[\\/]/).pop() || 'downloaded_file'; // 默认使用任务的输出文件名

    if (contentDisposition) {
      const filenameMatch = contentDisposition.match(/filename="?(.+?)"?/i);
      if (filenameMatch && filenameMatch[1]) {
        filename = filenameMatch[1];
      }
    }

    // 创建并触发下载链接
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(link.href);

  } catch (err) {
    message.error(`下载失败: ${err instanceof Error ? err.message : String(err)}`);
  }
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
  margin-top: 8px;
  padding-right: 4px;
}

/* 优化滚动条样式 */
.file-list-container::-webkit-scrollbar,
.task-list-container::-webkit-scrollbar {
  width: 6px;
}
.file-list-container::-webkit-scrollbar-thumb,
.task-list-container::-webkit-scrollbar-thumb {
  background: #cccccc;
  border-radius: 3px;
}
.file-list-container::-webkit-scrollbar-thumb:hover,
.task-list-container::-webkit-scrollbar-thumb:hover {
  background: #aaaaaa;
}

.file-item, .task-item {
  cursor: pointer;
  padding: 8px 12px;
}

.file-item:hover, .task-item:hover {
  background-color: #f5f5f5;
}

.selected-item {
  background-color: #e6f7ff !important;
  border-right: 3px solid #1890ff;
}

.task-title, .file-name {
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

@media (max-width: 768px) {
  .sidebar-container :deep(.ant-upload-drag-icon),
  .sidebar-container :deep(.ant-upload-hint) {
    display: none;
  }
  .sidebar-container :deep(.ant-upload-text) {
    font-size: 14px;
  }
}
</style>
