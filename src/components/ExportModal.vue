<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { useFileStore, type UserFile } from '@/stores/fileStore'
import { API_ENDPOINTS } from '@/api'
import { message } from 'ant-design-vue'
import axios from 'axios'

// --- Props and Emits ---
const props = defineProps<{
  visible: boolean
  fileInfo: any
  initialStartTime: number
  initialEndTime: number
}>()

const emit = defineEmits(['update:visible'])

// --- State ---
const fileStore = useFileStore()
const isProcessing = ref(false)

const formState = reactive({
  selectedFiles: [] as string[],
  container: 'mp4',
  videoCodec: 'copy',
  videoBitrate: 1000,
  resolution: {
    width: 1920,
    height: 1080,
    keepAspectRatio: true,
  },
  audioCodec: 'copy',
  audioBitrate: 128,
})

// --- Computed Properties ---
const videoStream = computed(() => props.fileInfo?.streams.find((s: any) => s.codec_type === 'video'))
const audioStream = computed(() => props.fileInfo?.streams.find((s: any) => s.codec_type === 'audio'))
const originalAspectRatio = computed(() => {
  if (videoStream.value) {
    return videoStream.value.width / videoStream.value.height
  }
  return 16 / 9
})

const isVideoContainer = computed(() => {
  const videoFormats = ['mp4', 'mkv', 'mov', 'webm', 'avi', 'flv']
  return videoFormats.includes(formState.container)
})

// --- Watchers to update form defaults when modal opens ---
watch(() => props.visible, (isVisible) => {
  if (isVisible && props.fileInfo) {
    // Reset form state based on the current file
    const format = props.fileInfo.format.format_name.split(',')[0]
    formState.container = format || 'mp4'
    formState.selectedFiles = [fileStore.selectedFileId!]

    if (videoStream.value) {
      formState.videoCodec = 'copy'
      formState.videoBitrate = Math.round((parseInt(videoStream.value.bit_rate || props.fileInfo.format.bit_rate) || 2000000) / 1000)
      formState.resolution.width = videoStream.value.width
      formState.resolution.height = videoStream.value.height
    }

    if (audioStream.value) {
      formState.audioCodec = 'copy'
      formState.audioBitrate = Math.round((parseInt(audioStream.value.bit_rate) || 128000) / 1000)
    }
  }
})

watch(() => formState.resolution.width, (newWidth) => {
  if (formState.resolution.keepAspectRatio) {
    formState.resolution.height = Math.round(newWidth / originalAspectRatio.value)
  }
})

watch(() => formState.resolution.height, (newHeight) => {
  if (formState.resolution.keepAspectRatio) {
    formState.resolution.width = Math.round(newHeight * originalAspectRatio.value)
  }
})

// --- Methods ---
const handleCancel = () => {
  emit('update:visible', false)
}

const handleOk = async () => {
  if (formState.selectedFiles.length === 0) {
    message.error('请至少选择一个要处理的文件！')
    return
  }

  isProcessing.value = true
  try {
    const payload = {
      ...formState,
      startTime: props.initialStartTime,
      endTime: props.initialEndTime,
      // 只传递需要的信息
      files: formState.selectedFiles,
      totalDuration: parseFloat(props.fileInfo.format.duration),
    }
    const response = await axios.post(API_ENDPOINTS.PROCESS_FILE, payload)
    message.success(`任务已创建 (ID: ${response.data.task_id})，正在后台处理...`)
    // TODO: Can start polling for status here or show progress in another component
    emit('update:visible', false)
  } catch (error: any) {
    message.error(error.response?.data?.error || '创建任务失败')
  } finally {
    isProcessing.value = false
  }
}

// Generates the FFmpeg command for preview
const ffmpegCommand = computed(() => {
  let cmd = `ffmpeg -i "INPUT_FILE"`

  // Cropping
  if (props.initialStartTime > 0 || props.initialEndTime < parseFloat(props.fileInfo.format.duration)) {
    cmd += ` -ss ${props.initialStartTime.toFixed(3)} -to ${props.initialEndTime.toFixed(3)}`
  }

  // Video
  if (isVideoContainer.value && videoStream.value) {
    if (formState.videoCodec === 'copy') {
      cmd += ` -c:v copy`
    } else {
      cmd += ` -c:v ${formState.videoCodec} -b:v ${formState.videoBitrate}k`
      if (formState.resolution.width !== videoStream.value.width || formState.resolution.height !== videoStream.value.height) {
        cmd += ` -s ${formState.resolution.width}x${formState.resolution.height}`
      }
    }
  } else {
    cmd += ` -vn` // No video
  }

  // Audio
  if (audioStream.value) {
    if (formState.audioCodec === 'copy') {
      cmd += ` -c:a copy`
    } else {
      cmd += ` -c:a ${formState.audioCodec} -b:a ${formState.audioBitrate}k`
    }
  } else {
    cmd += ` -an` // No audio
  }

  cmd += ` "OUTPUT_FILE.${formState.container}"`
  return cmd
})
</script>

<template>
  <a-modal
    :open="visible"
    title="导出设置"
    width="800px"
    @cancel="handleCancel"
    :confirm-loading="isProcessing"
    @ok="handleOk"
  >
    <template #footer>
       <div class="modal-footer-grid">
        <div class="ffmpeg-command-preview">
          <a-typography-text code>{{ ffmpegCommand }}</a-typography-text>
        </div>
        <div>
          <a-button key="back" @click="handleCancel">取消</a-button>
          <a-button key="submit" type="primary" :loading="isProcessing" @click="handleOk">
            开始处理
          </a-button>
        </div>
      </div>
    </template>

    <a-form layout="vertical">
      <!-- File Selection -->
      <a-form-item label="待处理文件">
        <a-checkbox-group v-model:value="formState.selectedFiles" style="width: 100%">
          <a-row>
            <a-col v-for="file in fileStore.fileList" :key="file.id" :span="24">
              <a-checkbox :value="file.id">{{ file.name }}</a-checkbox>
            </a-col>
          </a-row>
        </a-checkbox-group>
      </a-form-item>

      <!-- Container -->
      <a-form-item label="容器格式">
        <a-select v-model:value="formState.container" placeholder="选择或输入格式">
          <a-select-option value="mp4">MP4</a-select-option>
          <a-select-option value="mkv">MKV</a-select-option>
          <a-select-option value="mov">MOV</a-select-option>
          <a-select-option value="mp3">MP3</a-select-option>
          <a-select-option value="flac">FLAC</a-select-option>
          <a-select-option value="wav">WAV</a-select-option>
        </a-select>
      </a-form-item>

      <div v-if="isVideoContainer && videoStream">
        <a-divider>视频设置</a-divider>
        <!-- Video Codec -->
        <a-form-item label="视频编码">
          <a-select v-model:value="formState.videoCodec">
            <a-select-option value="copy">复制原始视频流 (默认)</a-select-option>
            <a-select-option value="libx264">H.264 (libx264)</a-select-option>
            <a-select-option value="libx265">H.265 (libhevc)</a-select-option>
            <a-select-option value="libaom-av1">AV1 (libaom-av1)</a-select-option>
          </a-select>
        </a-form-item>

        <!-- Video Bitrate -->
        <a-form-item v-if="formState.videoCodec !== 'copy'" label="视频比特率 (kbps)">
          <a-input-number v-model:value="formState.videoBitrate" :min="100" :step="100" style="width: 100%" />
        </a-form-item>

        <!-- Resolution -->
        <a-form-item v-if="formState.videoCodec !== 'copy'" label="分辨率">
           <a-row :gutter="8">
            <a-col :span="10"><a-input-number v-model:value="formState.resolution.width" :min="1" addon-after="宽" style="width: 100%"/></a-col>
            <a-col :span="10"><a-input-number v-model:value="formState.resolution.height" :min="1" addon-after="高" style="width: 100%"/></a-col>
            <a-col :span="4"><a-checkbox v-model:checked="formState.resolution.keepAspectRatio">锁定比例</a-checkbox></a-col>
          </a-row>
        </a-form-item>
      </div>

      <div v-if="audioStream">
        <a-divider>音频设置</a-divider>
         <!-- Audio Codec -->
        <a-form-item label="音频编码">
          <a-select v-model:value="formState.audioCodec">
            <a-select-option value="copy">复制原始音频流 (默认)</a-select-option>
            <a-select-option value="aac">AAC</a-select-option>
            <a-select-option value="opus">Opus</a-select-option>
            <a-select-option value="mp3">MP3</a-select-option>
          </a-select>
        </a-form-item>

        <!-- Audio Bitrate -->
        <a-form-item v-if="formState.audioCodec !== 'copy'" label="音频比特率 (kbps)">
          <a-input-number v-model:value="formState.audioBitrate" :min="32" :step="16" style="width: 100%" />
        </a-form-item>
      </div>
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
</style>
