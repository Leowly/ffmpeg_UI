<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { useFileStore, type FFProbeResult, type Task } from '@/stores/fileStore'
import { API_ENDPOINTS } from '@/api'
import { message } from 'ant-design-vue'
import axios, { isAxiosError } from 'axios'

// --- 类型定义 ---
interface ProcessPayload {
  files: string[]
  container: string
  startTime: number
  endTime: number
  totalDuration: number
  videoCodec: string
  audioCodec: string
  videoBitrate?: number
  resolution?: { width: number; height: number; keepAspectRatio: boolean }
  audioBitrate?: number
}

// --- Props and Emits ---
const props = defineProps<{
  visible: boolean
  initialStartTime: number
  initialEndTime: number
}>()
const emit = defineEmits(['update:visible'])

// --- State ---
const fileStore = useFileStore()
const isProcessing = ref(false)

// 本地状态，用于解耦
const previewFileInfo = ref<FFProbeResult | null>(null)
const isPreviewLoading = ref(false)
const modalStartTime = ref(0)
const modalEndTime = ref(0)

const formState = reactive({
  selectedFiles: [] as string[],
  container: 'mp4',
  videoCodec: 'copy',
  videoBitrate: 2000,
  resolution: { width: 1920, height: 1080, keepAspectRatio: true },
  audioCodec: 'copy',
  audioBitrate: 192,
})

const originalValues = reactive({
  videoCodec: 'libx264',
  videoBitrate: 2000,
  width: 1920,
  height: 1080,
  audioCodec: 'aac',
  audioBitrate: 192,
})

// --- 核心逻辑：获取预览文件信息 ---
const getPreviewInfo = async (fileId: string) => {
  isPreviewLoading.value = true
  try {
    const response = await axios.get<FFProbeResult>(API_ENDPOINTS.FILE_INFO(fileId))
    previewFileInfo.value = response.data
  } catch {
    message.error('加载预览文件信息失败')
    previewFileInfo.value = null
  } finally {
    isPreviewLoading.value = false
  }
}

// --- Helper & Watchers ---
const mapCodecNameToLib = (codecName: string, type: 'video' | 'audio'): string => {
  const videoMap: Record<string, string> = { h264: 'libx264', hevc: 'libx265', av1: 'libaom-av1' }
  const audioMap: Record<string, string> = { aac: 'aac', opus: 'opus', mp3: 'mp3' }
  if (type === 'video') return videoMap[codecName] || 'libx264'
  return audioMap[codecName] || 'aac'
}

// 模态框打开时，同步初始状态
watch(
  () => props.visible,
  (isVisible) => {
    if (isVisible) {
      if (fileStore.fileList.length === 0) {
        fileStore.fetchFileList()
      }
      if (fileStore.selectedFileId && !formState.selectedFiles.includes(fileStore.selectedFileId)) {
        formState.selectedFiles = [fileStore.selectedFileId]
        getPreviewInfo(fileStore.selectedFileId)
      } else if (!fileStore.selectedFileId) {
        formState.selectedFiles = []
        previewFileInfo.value = null
      }
      // 始终同步初始时间
      modalStartTime.value = props.initialStartTime
      modalEndTime.value = props.initialEndTime
    }
  },
)

// 监听模态框内部的文件选择变化
watch(
  () => formState.selectedFiles,
  (newSelection, oldSelection) => {
    const oldPrimary = oldSelection ? oldSelection[0] : null
    const newPrimary = newSelection.length > 0 ? newSelection[0] : null

    if (newPrimary && newPrimary !== oldPrimary) {
      getPreviewInfo(newPrimary)
    } else if (newSelection.length === 0) {
      previewFileInfo.value = null
    }
  },
  { deep: true },
)

// 监听获取的 previewFileInfo，用它来填充表单默认值和时间
watch(previewFileInfo, (fileInfo) => {
  if (!fileInfo) {
    modalStartTime.value = 0
    modalEndTime.value = 0
    return
  }

  const duration = parseFloat(fileInfo.format.duration)
  const newFileId = formState.selectedFiles[0]

  // 如果窗口内选择的文件和主工作区不一致，则重置时间为完整时长
  if (newFileId !== fileStore.selectedFileId) {
    modalStartTime.value = 0
    modalEndTime.value = isNaN(duration) ? 0 : duration
  } else {
    // 如果一致，则使用从 props 传入的（可能被裁剪的）时间
    modalStartTime.value = props.initialStartTime
    modalEndTime.value = props.initialEndTime
  }

  const format = fileInfo.format?.format_name.split(',')[0]
  formState.container = format || 'mp4'
  formState.videoCodec = 'copy'
  formState.audioCodec = 'copy'

  const vs = fileInfo.streams?.find((s) => s.codec_type === 'video')
  if (vs) {
    originalValues.videoCodec = mapCodecNameToLib(vs.codec_name, 'video')
    originalValues.videoBitrate = Math.round(parseInt(vs.bit_rate || '2000000') / 1000)
    originalValues.width = vs.width || 1920
    originalValues.height = vs.height || 1080
    formState.videoBitrate = originalValues.videoBitrate
    formState.resolution.width = originalValues.width
    formState.resolution.height = originalValues.height
  }

  const as = fileInfo.streams?.find((s) => s.codec_type === 'audio')
  if (as) {
    originalValues.audioCodec = mapCodecNameToLib(as.codec_name, 'audio')
    originalValues.audioBitrate = Math.round(parseInt(as.bit_rate || '192000') / 1000)
    formState.audioBitrate = originalValues.audioBitrate
  }
})

// --- 智能预览 ---
const previewFileName = computed<string | null>(() => {
  if (formState.selectedFiles.length === 0) return null
  const file = fileStore.fileList.find((f) => f.id === formState.selectedFiles[0])
  return file?.name || null
})

const totalDuration = computed(() => {
  return previewFileInfo.value ? parseFloat(previewFileInfo.value.format.duration) : 0
})

// 复制预览命令到剪贴板（无提示）
const copyPreview = async () => {
  const text = ffmpegCommandPreview.value || ''
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text)
      message.success('已复制')
    } else {
      // 退回到 textarea 选择复制
      const ta = document.createElement('textarea')
      ta.value = text
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
      message.success('已复制')
    }
  } catch {
    // 忽略错误，不显示提示
  }
}

const ffmpegCommandPreview = computed(() => {
  if (!previewFileInfo.value || !previewFileName.value) return '请选择文件以生成预览...'
  let cmd = `ffmpeg -i "${previewFileName.value}"`
  if (modalStartTime.value > 0 || modalEndTime.value < totalDuration.value) {
    cmd += ` -ss ${modalStartTime.value.toFixed(3)} -to ${modalEndTime.value.toFixed(3)}`
  }
  const vs = previewFileInfo.value.streams?.find((s) => s.codec_type === 'video')
  const isVideoContainer = ['mp4', 'mkv', 'mov'].includes(formState.container)
  if (isVideoContainer && vs) {
    cmd += ` -c:v ${formState.videoCodec}`
    if (formState.videoCodec !== 'copy') {
      if (formState.videoBitrate !== originalValues.videoBitrate)
        cmd += ` -b:v ${formState.videoBitrate}k`
      if (
        formState.resolution.width !== originalValues.width ||
        formState.resolution.height !== originalValues.height
      )
        cmd += ` -s ${formState.resolution.width}x${formState.resolution.height}`
    }
  } else {
    cmd += ` -vn`
  }
  const as = previewFileInfo.value.streams?.find((s) => s.codec_type === 'audio')
  if (as) {
    cmd += ` -c:a ${formState.audioCodec}`
    if (formState.audioCodec !== 'copy' && formState.audioBitrate !== originalValues.audioBitrate) {
      cmd += ` -b:a ${formState.audioBitrate}k`
    }
  } else {
    cmd += ` -an`
  }
  const baseName = previewFileName.value.substring(0, previewFileName.value.lastIndexOf('.'))
  const outputFileName = `${baseName}_processed.${formState.container}`
  cmd += ` "${outputFileName}"`
  return cmd
})

// --- 后端交互 ---
const handleOk = async () => {
  if (formState.selectedFiles.length === 0) {
    message.error('请至少选择一个要处理的文件！')
    return
  }
  isProcessing.value = true
  try {
    const payload: ProcessPayload = {
      files: formState.selectedFiles,
      container: formState.container,
      startTime: modalStartTime.value,
      endTime: modalEndTime.value,
      totalDuration: totalDuration.value,
      videoCodec: formState.videoCodec,
      audioCodec: formState.audioCodec,
    }
    if (formState.videoCodec !== 'copy') {
      if (formState.videoBitrate !== originalValues.videoBitrate)
        payload.videoBitrate = formState.videoBitrate
      if (
        formState.resolution.width !== originalValues.width ||
        formState.resolution.height !== originalValues.height
      )
        payload.resolution = formState.resolution
    }
    if (formState.audioCodec !== 'copy' && formState.audioBitrate !== originalValues.audioBitrate)
      payload.audioBitrate = formState.audioBitrate
    const response = await axios.post<Task[]>(API_ENDPOINTS.PROCESS_FILE, payload)
    fileStore.addTasks(response.data) // 将新创建的任务添加到 store
    message.success(`成功创建 ${response.data.length} 个处理任务，已在后台开始执行。`)
    emit('update:visible', false)
  } catch (error: unknown) {
    let errorMessage = '创建任务失败'
    if (isAxiosError(error)) errorMessage = error.response?.data?.error || error.message
    else if (error instanceof Error) errorMessage = error.message
    message.error(errorMessage)
  } finally {
    isProcessing.value = false
  }
}

const handleCancel = () => {
  emit('update:visible', false)
}
</script>

<template>
  <a-modal
    :open="visible"
    title="导出设置"
    width="800px"
    centered
    @cancel="handleCancel"
    :confirm-loading="isProcessing"
    @ok="handleOk"
  >
    <template #footer>
      <div class="modal-footer-grid">
        <div class="ffmpeg-command-preview" @click="copyPreview">
          <a-typography-text code>
            {{ ffmpegCommandPreview }}
          </a-typography-text>
        </div>
        <div class="footer-actions">
          <a-button key="back" @click="handleCancel">取消</a-button>
          <a-button key="submit" type="primary" :loading="isProcessing" @click="handleOk">
            开始处理 ({{ formState.selectedFiles.length }})
          </a-button>
        </div>
      </div>
    </template>

    <a-form layout="vertical">
      <a-form-item label="待处理文件 (可多选)">
        <a-checkbox-group
          v-if="fileStore.fileList.length > 0"
          v-model:value="formState.selectedFiles"
          style="width: 100%"
        >
          <a-row :gutter="[8, 8]">
            <a-col v-for="file in fileStore.fileList" :key="file.id" :span="24">
              <a-checkbox :value="file.id">{{ file.name }}</a-checkbox>
            </a-col>
          </a-row>
        </a-checkbox-group>
        <a-alert v-else message="没有可用的文件" type="info" />
      </a-form-item>

      <!-- 当没有文件信息时显示占位符 -->
      <div
        v-if="!previewFileInfo && formState.selectedFiles.length > 0"
        class="settings-placeholder"
      >
        <a-spin tip="正在加载文件信息以生成设置选项..."></a-spin>
      </div>

      <!-- 当有文件信息时显示设置 -->
      <fieldset :disabled="isPreviewLoading">
        <div v-if="previewFileInfo">
          <a-form-item label="容器格式">
            <a-select v-model:value="formState.container">
              <a-select-option value="mp4">MP4</a-select-option>
              <a-select-option value="mkv">MKV</a-select-option>
              <a-select-option value="mov">MOV</a-select-option>
              <a-select-option value="mp3">MP3</a-select-option>
              <a-select-option value="flac">FLAC</a-select-option>
              <a-select-option value="wav">WAV</a-select-option>
            </a-select>
          </a-form-item>

          <div v-if="previewFileInfo.streams?.find((s) => s.codec_type === 'video')">
            <a-divider>视频设置</a-divider>
            <a-form-item label="视频编码">
              <a-select v-model:value="formState.videoCodec">
                <a-select-option value="copy">复制原始视频流 (最快)</a-select-option>
                <a-select-option value="libx264">H.264 (libx264)</a-select-option>
                <a-select-option value="libx265">H.265 (libhevc)</a-select-option>
                <a-select-option value="libaom-av1">AV1 (libaom-av1)</a-select-option>
              </a-select>
            </a-form-item>

            <a-form-item label="视频比特率 (kbps)">
              <a-input-number
                v-model:value="formState.videoBitrate"
                :min="100"
                style="width: 100%"
              />
            </a-form-item>

            <a-form-item label="分辨率">
              <a-row :gutter="8">
                <a-col :span="10"
                  ><a-input-number
                    v-model:value="formState.resolution.width"
                    :min="1"
                    addon-after="宽"
                    style="width: 100%"
                /></a-col>
                <a-col :span="10"
                  ><a-input-number
                    v-model:value="formState.resolution.height"
                    :min="1"
                    addon-after="高"
                    style="width: 100%"
                /></a-col>
                <a-col :span="4" style="display: flex; align-items: center"
                  ><a-checkbox v-model:checked="formState.resolution.keepAspectRatio"
                    >锁定比例</a-checkbox
                  ></a-col
                >
              </a-row>
            </a-form-item>
          </div>

          <div v-if="previewFileInfo.streams?.find((s) => s.codec_type === 'audio')">
            <a-divider>音频设置</a-divider>
            <a-form-item label="音频编码">
              <a-select v-model:value="formState.audioCodec">
                <a-select-option value="copy">复制原始音频流 (最快)</a-select-option>
                <a-select-option value="aac">AAC</a-select-option>
                <a-select-option value="opus">Opus</a-select-option>
                <a-select-option value="mp3">MP3</a-select-option>
              </a-select>
            </a-form-item>

            <a-form-item label="音频比特率 (kbps)">
              <a-input-number
                v-model:value="formState.audioBitrate"
                :min="32"
                style="width: 100%"
              />
            </a-form-item>
          </div>
        </div>
      </fieldset>
    </a-form>
  </a-modal>
</template>

<style scoped>
.modal-footer-grid {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}
.ffmpeg-command-preview {
  flex-grow: 1;
  margin-right: 16px;
  overflow-x: auto;
  white-space: nowrap;
  background-color: #f0f2f5;
  padding: 4px 8px;
  border-radius: 4px;
}
.ffmpeg-command-preview {
  cursor: pointer;
}
.footer-actions {
  display: flex;
  gap: 8px; /* 默认按钮间距 */
}
.ffmpeg-command-preview code {
  font-size: 12px;
}
.settings-placeholder {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 200px;
}
</style>
