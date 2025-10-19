<template>
  <div class="workspace-container">
    <!-- 未选择文件时的占位符 -->
    <div v-if="!fileStore.selectedFileId" class="placeholder">
      <a-empty description="请从左侧文件列表中选择一个文件开始操作" />
    </div>

    <!-- 加载状态 -->
    <div v-else-if="fileStore.isLoading" class="loading-spinner">
      <a-spin size="large" tip="正在加载文件信息..." />
    </div>

    <!-- 错误状态 -->
    <div v-else-if="fileStore.error" class="error-message">
      <a-alert message="加载失败" :description="fileStore.error" type="error" show-icon />
    </div>

    <!-- 成功加载文件信息 -->
    <div v-else-if="fileStore.fileInfo" class="file-workspace" ref="workspaceRef">
      <a-page-header
        :title="selectedFile?.name || ''"
        :sub-title="mediaTypeDisplay"
      />

      <a-descriptions bordered :column="descriptionColumns">
        <!-- 1. 通用信息 -->
        <a-descriptions-item label="容器格式" :span="descriptionColumns >= 2 ? 2 : 1">{{ fileStore.fileInfo.format.format_long_name }}</a-descriptions-item>
        <a-descriptions-item label="时长">{{ parseFloat(fileStore.fileInfo.format.duration).toFixed(2) }} 秒</a-descriptions-item>
        <a-descriptions-item label="文件大小">{{ (parseInt(fileStore.fileInfo.format.size) / 1024 / 1024).toFixed(2) }} MB</a-descriptions-item>
        <a-descriptions-item label="总比特率">{{ (parseInt(fileStore.fileInfo.format.bit_rate) / 1000).toFixed(0) }} kb/s</a-descriptions-item>

        <!-- 视频专属信息 -->
        <template v-if="mediaType === 'video' && videoStream">
          <a-descriptions-item v-if="videoStream.bit_rate" label="视频比特率">
            {{ (parseInt(videoStream.bit_rate) / 1000).toFixed(0) }} kb/s
          </a-descriptions-item>
          <a-descriptions-item label="分辨率">{{ videoStream.width }} x {{ videoStream.height }}</a-descriptions-item>
          <a-descriptions-item label="视频编码">{{ videoStream.codec_name }} ({{ videoStream.codec_long_name }})</a-descriptions-item>
          <a-descriptions-item label="帧率">{{ calculateFrameRate(videoStream.r_frame_rate).toFixed(2) }} fps</a-descriptions-item>
        </template>

        <!-- 音频专属信息 -->
        <template v-if="mediaType === 'audio' && audioStream">
          <a-descriptions-item label="音频比特率">{{ audioBitrate }}</a-descriptions-item>
        </template>

        <!-- 音频流通用信息 -->
        <template v-if="audioStream">
          <a-descriptions-item label="音频编码">{{ audioStream.codec_name }} ({{ audioStream.codec_long_name }})</a-descriptions-item>
          <a-descriptions-item label="采样率">{{ audioStream.sample_rate }} Hz</a-descriptions-item>
          <a-descriptions-item label="声道">{{ audioStream.channels }} ({{ audioStream.channel_layout }})</a-descriptions-item>
        </template>

        <!-- 封面专属信息 -->
        <template v-if="mediaType === 'audio' && videoStream">
          <a-descriptions-item label="内嵌封面尺寸">{{ videoStream.width }} x {{ videoStream.height }}</a-descriptions-item>
          <a-descriptions-item label="内嵌封面格式">{{ videoStream.codec_name }}</a-descriptions-item>
        </template>
      </a-descriptions>

      <a-divider>裁剪与其他操作</a-divider>
      <div class="operation-section">
        <h3>视频/音频裁剪</h3>
        <a-slider
          v-model:value="trimRange"
          range
          :min="0"
          :max="fileStore.totalDuration"
          :step="0.01"
          :tip-formatter="formatTime"
        />
        <div class="time-input-grid">
          <span>开始时间:</span>
          <a-input-number
            v-model:value="startTimeValue"
            :min="0"
            :max="endTimeValue"
            :step="0.1"
            string-mode
          />
          <span class="time-display">{{ formatTime(startTimeValue) }}</span>
          <span>结束时间:</span>
          <a-input-number
            v-model:value="endTimeValue"
            :min="startTimeValue"
            :max="fileStore.totalDuration"
            :step="0.1"
            string-mode
          />
          <span class="time-display">{{ formatTime(endTimeValue) }}</span>
        </div>
        <!-- 为浮动按钮添加的底部安全空间 -->
        <div class="bottom-spacer"></div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { useFileStore } from '@/stores/fileStore'

const fileStore = useFileStore()

// --- Refs for UI ---
const workspaceRef = ref<HTMLElement | null>(null)
const descriptionColumns = ref(2)
let observer: ResizeObserver | null = null

// --- Computed Properties from Store ---
const videoStream = computed(() => fileStore.fileInfo?.streams.find((s) => s.codec_type === 'video'))
const audioStream = computed(() => fileStore.fileInfo?.streams.find((s) => s.codec_type === 'audio'))

const selectedFile = computed(() => {
  if (!fileStore.selectedFileId) return null;
  return fileStore.fileList.find(f => f.id === fileStore.selectedFileId);
});

// --- Computed properties for trim controls ---
const trimRange = computed({
  get(): [number, number] {
    return [fileStore.startTime, fileStore.endTime] as [number, number];
  },
  set(newRange: [number, number]) {
    fileStore.updateTrimTimes({ start: newRange[0], end: newRange[1] });
  }
});

const startTimeValue = computed<number>({
  get: () => fileStore.startTime,
  set: (newStart) => {
    fileStore.updateTrimTimes({ start: newStart, end: fileStore.endTime })
  }
});

const endTimeValue = computed<number>({
  get: () => fileStore.endTime,
  set: (newEnd) => {
    fileStore.updateTrimTimes({ start: fileStore.startTime, end: newEnd })
  }
});


// --- UI Logic ---
const mediaType = computed<'video' | 'audio' | 'unknown'>(() => {
  if (!fileStore.fileInfo) return 'unknown'
  const vs = videoStream.value
  if (vs && !['mjpeg', 'png'].includes(vs.codec_name)) return 'video'
  if (audioStream.value) return 'audio'
  return 'unknown'
})

const mediaTypeDisplay = computed(() => {
  if (mediaType.value === 'video') return '视频文件'
  if (mediaType.value === 'audio') return '音频文件'
  return '媒体文件'
})

const audioBitrate = computed(() => {
  if (audioStream.value && audioStream.value.bit_rate) {
    return `${(parseInt(audioStream.value.bit_rate) / 1000).toFixed(0)} kb/s`
  }
  if (audioStream.value && fileStore.fileInfo?.format) {
    const calculatedBps =
      (parseInt(fileStore.fileInfo.format.size) * 8) / parseFloat(fileStore.fileInfo.format.duration)
    if (
      fileStore.fileInfo.streams.length === 1 ||
      (fileStore.fileInfo.streams.length === 2 && videoStream.value?.codec_name.match(/mjpeg|png/))
    ) {
      return `${(calculatedBps / 1000).toFixed(0)} kb/s (计算值)`
    }
    return `(总比特率: ${(parseInt(fileStore.fileInfo.format.bit_rate) / 1000).toFixed(0)} kb/s)`
  }
  return 'N/A'
})

// --- Helper Functions ---
const calculateFrameRate = (rateString: string): number => {
  if (!rateString || !rateString.includes('/')) return 0
  const parts = rateString.split('/')
  const numerator = parseInt(parts[0], 10)
  const denominator = parseInt(parts[1], 10)
  if (isNaN(numerator) || isNaN(denominator) || denominator === 0) return 0
  return numerator / denominator
}

const formatTime = (seconds: number | null): string => {
  if (seconds === null || isNaN(seconds)) return '00:00:00.000'
  const h = Math.floor(seconds / 3600).toString().padStart(2, '0')
  const m = Math.floor((seconds % 3600) / 60).toString().padStart(2, '0')
  const s = Math.floor(seconds % 60).toString().padStart(2, '0')
  const ms = (seconds % 1).toFixed(3).substring(2).padEnd(3, '0')
  return `${h}:${m}:${s}.${ms}`
}

// --- Lifecycle Hooks for Responsive Columns ---
const setupResizeObserver = () => {
  if (workspaceRef.value) {
    observer = new ResizeObserver((entries) => {
      const contentWidth = entries[0].contentRect.width
      descriptionColumns.value = contentWidth < 620 ? 1 : 2
    })
    observer.observe(workspaceRef.value)
  }
}

watch(() => fileStore.fileInfo, (newFileInfo) => {
  if (observer) {
    observer.disconnect()
    observer = null
  }
  if (newFileInfo) {
    nextTick(() => {
      setupResizeObserver()
    })
  }
}, { deep: true });

onMounted(() => {
  if (fileStore.fileInfo) {
    setupResizeObserver()
  }
});

onBeforeUnmount(() => {
  if (observer) {
    observer.disconnect()
  }
});

</script>

<style scoped>
.workspace-container {
  height: 100%;
  overflow-y: auto; /* 允许内容超出时滚动 */
  background-color: transparent; /* 交由外层 .panel-card 控制背景 */
}

.placeholder,
.loading-spinner,
.error-message {
  width: 100%;
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 24px;
  box-sizing: border-box;
}

.file-workspace {
  padding: 2px; /* 由 .panel-card 提供统一内边距 */
  box-sizing: border-box;
}

.operation-section {
  margin-top: 16px;
  padding-right: 2px;
  padding-left: 2px;
}

.time-input-grid {
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 12px;
  align-items: center;
  margin-top: 16px;
  max-width: 600px;
}

.time-display {
  font-family: 'Courier New', Courier, monospace;
  background-color: #f0f2f5;
  padding: 4px 8px;
  border-radius: 4px;
  border: 1px solid #d9d9d9;
}

.bottom-spacer {
  height: 40px; /* 预留给左下角浮动按钮的空间 */
}
</style>
