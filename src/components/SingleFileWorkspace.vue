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
      <a-alert message="加载失败" :description="error" type="error" show-icon />
    </div>

    <!-- 成功加载文件信息 -->
    <div v-else-if="fileInfo" class="file-workspace" ref="workspaceRef">
      <a-page-header
        :title="extractFilename(fileInfo.format.filename)"
        :sub-title="mediaTypeDisplay"
      />

      <!-- ======================================================= -->
      <!-- =========== 唯一的、智能且响应式的描述列表 ============ -->
      <!-- ======================================================= -->
      <a-descriptions bordered :column="descriptionColumns">
        <!-- 1. 通用信息 (总是显示) -->
        <a-descriptions-item label="容器格式" :span="2">{{
          fileInfo.format.format_long_name
        }}</a-descriptions-item>
        <a-descriptions-item label="时长"
          >{{ parseFloat(fileInfo.format.duration).toFixed(2) }} 秒</a-descriptions-item
        >
        <a-descriptions-item label="文件大小"
          >{{ (parseInt(fileInfo.format.size) / 1024 / 1024).toFixed(2) }} MB</a-descriptions-item
        >
        <a-descriptions-item label="总比特率"
          >{{ (parseInt(fileInfo.format.bit_rate) / 1000).toFixed(0) }} kb/s</a-descriptions-item
        >

        <!-- 视频专属信息 -->
        <template v-if="mediaType === 'video' && videoStream">
          <a-descriptions-item label="总比特率"
            >{{ (parseInt(fileInfo.format.bit_rate) / 1000).toFixed(0) }} kb/s</a-descriptions-item
          >
          <a-descriptions-item label="分辨率"
            >{{ videoStream.width }} x {{ videoStream.height }}</a-descriptions-item
          >
          <a-descriptions-item label="视频编码"
            >{{ videoStream.codec_name }} ({{ videoStream.codec_long_name }})</a-descriptions-item
          >
          <a-descriptions-item label="帧率"
            >{{ calculateFrameRate(videoStream.r_frame_rate).toFixed(2) }} fps</a-descriptions-item
          >
        </template>

        <!-- 音频专属信息 -->
        <template v-if="mediaType === 'audio' && audioStream">
          <!-- 👇 3. 使用 audioBitrate 并调整显示逻辑 -->
          <a-descriptions-item label="音频比特率">{{ audioBitrate }}</a-descriptions-item>
        </template>

        <!-- 音频流通用信息 (视频和音频文件都可能有) -->
        <template v-if="audioStream">
          <a-descriptions-item label="音频编码"
            >{{ audioStream.codec_name }} ({{ audioStream.codec_long_name }})</a-descriptions-item
          >
          <a-descriptions-item label="采样率">{{ audioStream.sample_rate }} Hz</a-descriptions-item>
          <a-descriptions-item label="声道"
            >{{ audioStream.channels }} ({{ audioStream.channel_layout }})</a-descriptions-item
          >
        </template>

        <!-- 4. 封面专属信息 (仅当 mediaType 为 'audio' 且存在封面时显示) -->
        <template v-if="mediaType === 'audio' && videoStream">
          <a-descriptions-item label="内嵌封面尺寸"
            >{{ videoStream.width }} x {{ videoStream.height }}</a-descriptions-item
          >
          <a-descriptions-item label="内嵌封面格式">{{
            videoStream.codec_name
          }}</a-descriptions-item>
        </template>
      </a-descriptions>

      <a-divider>裁剪与其他操作</a-divider>
      <div class="operation-section">
        <h3>视频/音频裁剪</h3>

        <!-- 1. 可视化范围滑块 -->
        <a-slider
          v-model:value="trimRange"
          range
          :min="0"
          :max="totalDuration"
          :step="0.01"
          :tip-formatter="formatTime"
        />

        <!-- 2. 增强型时间输入 -->
        <div class="time-input-grid">
          <span>开始时间:</span>
          <a-input-number
            v-model:value="startTime"
            :min="0"
            :max="endTime"
            :step="0.1"
            string-mode
          />
          <span class="time-display">{{ formatTime(startTime) }}</span>

          <span>结束时间:</span>
          <a-input-number
            v-model:value="endTime"
            :min="startTime"
            :max="totalDuration"
            :step="0.1"
            string-mode
          />
          <span class="time-display">{{ formatTime(endTime) }}</span>
        </div>
      </div>

      <a-divider />

      <a-divider />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed, nextTick } from 'vue'
import axios, { isAxiosError } from 'axios'
import { useFileStore } from '@/stores/fileStore'
import { API_ENDPOINTS } from '@/api'
import { message } from 'ant-design-vue'

// --- 修正: 为 ffprobe 的输出定义类型接口 ---
interface StreamInfo {
  codec_type: 'video' | 'audio'
  width?: number
  height?: number
  codec_name: string
  codec_long_name: string
  r_frame_rate: string
  sample_rate?: string
  channels?: number
  channel_layout?: string
  bit_rate?: string
}
interface FormatInfo {
  filename: string
  format_long_name: string
  duration: string
  size: string
  bit_rate: string
}

interface FFProbeResult {
  streams: StreamInfo[]
  format: FormatInfo
}

const fileStore = useFileStore()

// --- Reactive State ---
const isLoading = ref(false)
// 修正: 使用我们定义的接口代替 'any'
const fileInfo = ref<FFProbeResult | null>(null)
const error = ref<string | null>(null)
// 新增：为滑块创建一个 ref，它是一个包含两个数字的数组
const trimRange = ref<[number, number]>([0, 0])

// --- Operation State ---
const startTime = ref(0)
const endTime = ref(0)
const workspaceRef = ref<HTMLElement | null>(null)
const descriptionColumns = ref(2) // 默认是 2 列
const totalDuration = computed(() => {
  return fileInfo.value ? parseFloat(fileInfo.value.format.duration) : 0
})
let observer: ResizeObserver | null = null

watch(fileInfo, (newFileInfo) => {
  // 步骤 1: 无论如何，先清理旧的观察者
  if (observer) {
    observer.disconnect();
    observer = null;
  }

  // 步骤 2: 根据新数据，立即更新状态
  if (newFileInfo) {
    const duration = parseFloat(newFileInfo.format.duration);
    startTime.value = 0;
    endTime.value = duration;
    trimRange.value = [0, duration];

    // 步骤 3: 在 DOM 更新后，再处理依赖于 DOM 的事情
    nextTick(() => {
      if (workspaceRef.value) {
        observer = new ResizeObserver((entries) => {
          const contentWidth = entries[0].contentRect.width;
          descriptionColumns.value = contentWidth < 620 ? 1 : 2;
        });
        observer.observe(workspaceRef.value);
      }
    });
  } else {
    // 新增：当文件被取消选择时 (newFileInfo 为 null)，重置时间状态
    startTime.value = 0;
    endTime.value = 0;
    trimRange.value = [0, 0];
  }
});

// 's' 的类型现在会被正确推断为 StreamInfo
const videoStream = computed(() => fileInfo.value?.streams.find((s) => s.codec_type === 'video'))
const audioStream = computed(() => fileInfo.value?.streams.find((s) => s.codec_type === 'audio'))

const mediaType = computed<'video' | 'audio' | 'unknown'>(() => {
  if (!fileInfo.value) return 'unknown'

  const vs = videoStream.value
  const as = audioStream.value

  // 规则：如果存在视频流，且不是封面(mjpeg/png)，则判定为视频文件
  if (vs && !['mjpeg', 'png'].includes(vs.codec_name)) {
    return 'video'
  }
  // 否则，如果存在音频流，则判定为音频文件
  if (as) {
    return 'audio'
  }
  // 备用情况
  return 'unknown'
})

const mediaTypeDisplay = computed(() => {
  if (mediaType.value === 'video') return '视频文件'
  if (mediaType.value === 'audio') return '音频文件'
  return '媒体文件'
})

// 为音频文件单独计算比特率，更精确
const audioBitrate = computed(() => {
  // 现在 audioStream.value.bit_rate 不会报错
  if (audioStream.value && audioStream.value.bit_rate) {
    return `${(parseInt(audioStream.value.bit_rate) / 1000).toFixed(0)} kb/s`
  }
  if (audioStream.value && fileInfo.value?.format) {
    const calculatedBps =
      (parseInt(fileInfo.value.format.size) * 8) / parseFloat(fileInfo.value.format.duration)
    // 如果文件只有一个音频流，这个计算值比较准
    if (
      fileInfo.value.streams.length === 1 ||
      (fileInfo.value.streams.length === 2 && videoStream.value?.codec_name.match(/mjpeg|png/))
    ) {
      return `${(calculatedBps / 1000).toFixed(0)} kb/s (计算值)`
    }
    return `(总比特率: ${(parseInt(fileInfo.value.format.bit_rate) / 1000).toFixed(0)} kb/s)`
  }
  return 'N/A'
})

// --- Helper Functions ---
/**
 * 修正: 安全地计算帧率，替代 eval
 * @param rateString - ffprobe 返回的帧率字符串 (例如 "30000/1001" or "25/1")
 */
const calculateFrameRate = (rateString: string): number => {
  if (!rateString || !rateString.includes('/')) return 0
  const parts = rateString.split('/')
  const numerator = parseInt(parts[0], 10)
  const denominator = parseInt(parts[1], 10)
  if (isNaN(numerator) || isNaN(denominator) || denominator === 0) return 0
  return numerator / denominator
}

/**
 * 从完整路径中提取文件名
 * @param fullPath - ffprobe 返回的文件路径
 */
const extractFilename = (fullPath: string): string => {
  // 兼容 Windows (\) 和 Linux (/) 的路径分隔符
  return fullPath.replace(/^.*[\\\/]/, '')
}

/**
 * 新增：将秒数格式化为 HH:MM:SS.sss 格式
 * @param seconds - 秒数
 */
const formatTime = (seconds: number | null): string => {
  if (seconds === null || isNaN(seconds)) return '00:00:00.000'

  const h = Math.floor(seconds / 3600)
    .toString()
    .padStart(2, '0')
  const m = Math.floor((seconds % 3600) / 60)
    .toString()
    .padStart(2, '0')
  const s = Math.floor(seconds % 60)
    .toString()
    .padStart(2, '0')
  const ms = (seconds % 1).toFixed(3).substring(2).padEnd(3, '0')

  return `${h}:${m}:${s}.${ms}`
}
// --- Logic ---
const fetchFileInfo = async (fileId: string) => {
  isLoading.value = true
  error.value = null
  fileInfo.value = null

  try {
    const response = await axios.get<FFProbeResult>(API_ENDPOINTS.FILE_INFO(fileId))
    fileInfo.value = response.data
    // 设置默认的结束时间为视频总时长
    if (fileInfo.value?.format?.duration) {
      endTime.value = Math.floor(parseFloat(fileInfo.value.format.duration))
    }
  } catch (err: unknown) {
    // 修正: 使用 'unknown' 代替 'any'
    let errorMessage = '无法连接到服务器或发生未知错误'
    // 修正: 类型守卫，安全地处理错误
    if (isAxiosError(err)) {
      errorMessage = err.response?.data?.error || err.message
    } else if (err instanceof Error) {
      errorMessage = err.message
    }
    error.value = errorMessage
    message.error(`加载文件信息失败: ${errorMessage}`)
  } finally {
    isLoading.value = false
  }
}

// --- Watcher ---
watch(
  () => fileStore.selectedFileId,
  (newId) => {
    // 修正: 将未使用的 'oldId' 重命名为 '_oldId'
    if (newId) {
      fetchFileInfo(newId)
    } else {
      // 如果ID被清空，重置所有状态
      fileInfo.value = null
      error.value = null
      startTime.value = 0
      endTime.value = 0
    }
  },
  { immediate: true }, // 立即执行一次，处理初始状态
)

watch(trimRange, (newRange) => {
  startTime.value = newRange[0];
  endTime.value = newRange[1];
});

// 3. 监听数字输入框的变化，更新滑块
watch([startTime, endTime], (newTimes) => {
  trimRange.value = [newTimes[0], newTimes[1]];
});

</script>

<style scoped>
.workspace-container,
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
  width: 100%;
  height: 100%;
  display: block;
  text-align: left;
}
.operation-section {
  margin-top: 16px;
}

/* 新增：为时间输入区添加 Grid 布局，使其对齐美观 */
.time-input-grid {
  display: grid;
  grid-template-columns: auto 1fr auto; /* 标签 | 输入框 | 格式化时间 */
  gap: 12px; /* 元素间的间距 */
  align-items: center; /* 垂直居中对齐 */
  margin-top: 16px;
  max-width: 500px; /* 限制最大宽度，防止在大屏上过于拉伸 */
}

.time-display {
  font-family: 'Courier New', Courier, monospace; /* 使用等宽字体，防止数字跳动 */
  background-color: #f5f5f5;
  padding: 4px 8px;
  border-radius: 4px;
}
</style>
