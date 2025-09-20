<template>
  <div class="workspace-container">
    <!-- 未选择文件时的占位符 -->
    <div v-if="!fileStore.selectedFileId" class="placeholder">
      <a-empty description="请从左侧文件列表中选择一个文件开始操作" />
    </div>

    <!-- 加载状态 -->
    <div v-else-if="isLoading" class="loading-spinner">
      <a-spin size="large" tip="正在加载文件信息..." />
    </div>

    <!-- 错误状态 -->
    <div v-else-if="error" class="error-message">
      <a-alert
        message="加载失败"
        :description="error"
        type="error"
        show-icon
      />
    </div>

    <!-- 成功加载文件信息 -->
    <div v-else-if="fileInfo" class="file-workspace" ref="workspaceRef">
      <a-page-header :title="extractFilename(fileInfo.format.filename)" sub-title="文件元数据" />

      <!-- 👇 2. 将 :column="2" 绑定到一个动态变量 -->
      <a-descriptions bordered :column="descriptionColumns">
        <a-descriptions-item label="格式">{{ fileInfo.format.format_long_name }}</a-descriptions-item>
        <a-descriptions-item label="时长">{{ parseFloat(fileInfo.format.duration).toFixed(2) }} 秒</a-descriptions-item>
        <a-descriptions-item label="大小">{{ (parseInt(fileInfo.format.size) / 1024 / 1024).toFixed(2) }} MB</a-descriptions-item>
        <a-descriptions-item label="比特率">{{ (parseInt(fileInfo.format.bit_rate) / 1000).toFixed(0) }} kb/s</a-descriptions-item>

        <template v-if="videoStream">
          <a-descriptions-item label="分辨率">{{ videoStream.width }} x {{ videoStream.height }}</a-descriptions-item>
          <a-descriptions-item label="视频编码">{{ videoStream.codec_name }} ({{ videoStream.codec_long_name }})</a-descriptions-item>
          <!-- 修正: 调用辅助函数计算帧率，而不是使用 eval -->
          <a-descriptions-item label="帧率">{{ calculateFrameRate(videoStream.r_frame_rate).toFixed(2) }} fps</a-descriptions-item>
        </template>

        <template v-if="audioStream">
            <a-descriptions-item label="音频编码">{{ audioStream.codec_name }} ({{ audioStream.codec_long_name }})</a-descriptions-item>
            <a-descriptions-item label="采样率">{{ audioStream.sample_rate }} Hz</a-descriptions-item>
            <a-descriptions-item label="声道">{{ audioStream.channels }}</a-descriptions-item>
        </template>
      </a-descriptions>

      <a-divider>视频操作</a-divider>

      <!-- 视频剪辑区域 -->
      <div class="operation-section">
        <h3>视频剪辑</h3>
        <a-space>
          <span>开始时间:</span>
          <a-input-number v-model:value="startTime" :min="0" />
          <span>结束时间:</span>
          <a-input-number v-model:value="endTime" :min="0" />
        </a-space>
      </div>

      <a-divider />

      <a-button type="primary" size="large" style="margin-top: 24px;">
        配置并导出
      </a-button>

    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed, nextTick } from 'vue';
import axios, { isAxiosError } from 'axios';
import { useFileStore } from '@/stores/fileStore';
import { API_ENDPOINTS } from '@/api';
import { message } from 'ant-design-vue';

// --- 修正: 为 ffprobe 的输出定义类型接口 ---
interface StreamInfo {
  codec_type: 'video' | 'audio';
  width?: number;
  height?: number;
  codec_name: string;
  codec_long_name: string;
  r_frame_rate: string; // e.g., "25/1"
  sample_rate?: string;
  channels?: number;
}

interface FormatInfo {
  filename: string;
  format_long_name: string;
  duration: string;
  size: string;
  bit_rate: string;
}

interface FFProbeResult {
  streams: StreamInfo[];
  format: FormatInfo;
}

const fileStore = useFileStore();

// --- Reactive State ---
const isLoading = ref(false);
// 修正: 使用我们定义的接口代替 'any'
const fileInfo = ref<FFProbeResult | null>(null);
const error = ref<string | null>(null);

// --- Operation State ---
const startTime = ref(0);
const endTime = ref(0);
const workspaceRef = ref<HTMLElement | null>(null);
const descriptionColumns = ref(2); // 默认是 2 列
let observer: ResizeObserver | null = null;

watch(fileInfo, (newFileInfo) => {
  // 步骤 1: 清理旧的观察者
  if (observer) {
    observer.disconnect(); // 使用 disconnect 更彻底
    observer = null;
  }

  // 步骤 2: 如果有新数据 (意味着元素即将被渲染)
  if (newFileInfo) {
    // 使用 nextTick 确保 DOM 已经更新完毕
    nextTick(() => {
      if (workspaceRef.value) { // 此时 ref 应该已经可用
        observer = new ResizeObserver(entries => {
          const entry = entries[0];
          const contentWidth = entry.contentRect.width;

          // 我也把断点值调高了一点，这样效果更好
          // 当容器内容宽度小于 620px 时，变为 1 列
          descriptionColumns.value = contentWidth < 620 ? 1 : 2;
        });
        observer.observe(workspaceRef.value);
      }
    });
  }
});
// --- Computed Properties ---
// 's' 的类型现在会被正确推断为 StreamInfo
const videoStream = computed(() => fileInfo.value?.streams.find((s) => s.codec_type === 'video'));
const audioStream = computed(() => fileInfo.value?.streams.find((s) => s.codec_type === 'audio'));

// --- Helper Functions ---
/**
 * 修正: 安全地计算帧率，替代 eval
 * @param rateString - ffprobe 返回的帧率字符串 (例如 "30000/1001" or "25/1")
 */
const calculateFrameRate = (rateString: string): number => {
  if (!rateString || !rateString.includes('/')) return 0;
  const parts = rateString.split('/');
  const numerator = parseInt(parts[0], 10);
  const denominator = parseInt(parts[1], 10);
  if (isNaN(numerator) || isNaN(denominator) || denominator === 0) return 0;
  return numerator / denominator;
}

/**
 * 从完整路径中提取文件名
 * @param fullPath - ffprobe 返回的文件路径
 */
const extractFilename = (fullPath: string): string => {
    // 兼容 Windows (\) 和 Linux (/) 的路径分隔符
    return fullPath.replace(/^.*[\\\/]/, '');
}

// --- Logic ---
const fetchFileInfo = async (fileId: string) => {
  isLoading.value = true;
  error.value = null;
  fileInfo.value = null;

  try {
    const response = await axios.get<FFProbeResult>(API_ENDPOINTS.FILE_INFO(fileId));
    fileInfo.value = response.data;
    // 设置默认的结束时间为视频总时长
    if (fileInfo.value?.format?.duration) {
      endTime.value = Math.floor(parseFloat(fileInfo.value.format.duration));
    }
  } catch (err: unknown) { // 修正: 使用 'unknown' 代替 'any'
    let errorMessage = '无法连接到服务器或发生未知错误';
    // 修正: 类型守卫，安全地处理错误
    if (isAxiosError(err)) {
        errorMessage = err.response?.data?.error || err.message;
    } else if (err instanceof Error) {
        errorMessage = err.message;
    }
    error.value = errorMessage;
    message.error(`加载文件信息失败: ${errorMessage}`);
  } finally {
    isLoading.value = false;
  }
};

// --- Watcher ---
watch(
  () => fileStore.selectedFileId,
  (newId) => { // 修正: 将未使用的 'oldId' 重命名为 '_oldId'
    if (newId) {
      fetchFileInfo(newId);
    } else {
      // 如果ID被清空，重置所有状态
      fileInfo.value = null;
      error.value = null;
      startTime.value = 0;
      endTime.value = 0;
    }
  },
  { immediate: true } // 立即执行一次，处理初始状态
);

</script>

<style scoped>
.workspace-container, .placeholder, .loading-spinner, .error-message {
  width: 100%;
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 24px;
  box-sizing: border-box;
}
.file-workspace {
  width: 100%;
  height: 100%;
  display: block;
  text-align: left;
}
.operation-section {
  margin-top: 16px;
}
</style>
