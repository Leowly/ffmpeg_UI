<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { useFileStore, type FFProbeResult, type Task } from '@/stores/fileStore'
import { API_ENDPOINTS } from '@/api'
import { message } from 'ant-design-vue'
import { ThunderboltOutlined } from '@ant-design/icons-vue'
import axios, { isAxiosError } from 'axios'

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
  useHardwareAcceleration: boolean // 新增
  preset: string // 新增
}

const props = defineProps<{
  visible: boolean
  initialStartTime: number
  initialEndTime: number
}>()
const emit = defineEmits(['update:visible'])

const fileStore = useFileStore()
const isProcessing = ref(false)
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
  useHardwareAcceleration: false, // 新增：默认为 false
  preset: 'balanced', // 新增：默认为平衡
})

const originalValues = reactive({
  videoCodec: 'libx264',
  videoBitrate: 2000,
  width: 1920,
  height: 1080,
  audioCodec: 'aac',
  audioBitrate: 192,
})

const handleWidthChange = (newWidth: number | null) => {
  if (
    formState.resolution.keepAspectRatio &&
    originalValues.width > 0 &&
    typeof newWidth === 'number'
  ) {
    const ratio = originalValues.height / originalValues.width
    formState.resolution.height = Math.round(newWidth * ratio)
  }
  // 触发编码器切换检查
  handleVideoParamChange()
}

const handleHeightChange = (newHeight: number | null) => {
  if (
    formState.resolution.keepAspectRatio &&
    originalValues.height > 0 &&
    typeof newHeight === 'number'
  ) {
    const ratio = originalValues.width / originalValues.height
    formState.resolution.width = Math.round(newHeight * ratio)
  }
  // 触发编码器切换检查
  handleVideoParamChange()
}

const getFileType = (filename: string): 'video' | 'audio' | 'unknown' => {
  if (filename.match(/\.(mp4|mov|mkv|avi|webm|flv)$/i)) return 'video'
  if (filename.match(/\.(mp3|wav|flac|aac|ogg)$/i)) return 'audio'
  return 'unknown'
}

const selectionMode = computed<'video' | 'audio' | 'mixed' | 'none'>(() => {
  if (formState.selectedFiles.length === 0) return 'none'

  let hasVideo = false
  let hasAudio = false

  for (const fileId of formState.selectedFiles) {
    const file = fileStore.fileList.find((f) => f.id === fileId)
    if (file) {
      const type = getFileType(file.name)
      if (type === 'video') hasVideo = true
      if (type === 'audio') hasAudio = true
    }
  }

  if (hasVideo && hasAudio) return 'mixed'
  if (hasVideo) return 'video'
  if (hasAudio) return 'audio'
  return 'none'
})

const availableContainers = computed(() => {
  if (selectionMode.value === 'video') {
    return [
      { value: 'mp4', label: 'MPEG-4 (mp4)' },
      { value: 'mkv', label: 'Matroska (mkv)' },
      { value: 'mov', label: 'QuickTime MOV (mov)' },
      { value: 'webm', label: 'WebM for Web' },
    ]
  }
  if (selectionMode.value === 'audio') {
    return [
      { value: 'mp3', label: 'MPEG Audio Layer 3 (mp3)' },
      { value: 'flac', label: 'Free Lossless Audio Codec (flac)' },
      { value: 'wav', label: 'Waveform Audio (wav)' },
      { value: 'aac', label: 'Advanced Audio Coding (aac)' },
    ]
  }
  return []
})

watch(selectionMode, (newMode) => {
  if (newMode === 'video') {
    formState.container = 'mp4'
  } else if (newMode === 'audio') {
    formState.container = 'mp3'
  }
})

// 3. 监听文件类型变化，智能开启硬件加速
// 当检测到有视频且系统支持硬件加速时，自动勾选（可选，提升体验）
watch(selectionMode, (newMode) => {
  if (newMode === 'video' && fileStore.systemCapabilities.has_hardware_acceleration) {
    formState.useHardwareAcceleration = true
  }
})

let currentRequestId = 0

const getPreviewInfo = async (fileId: string) => {
  isPreviewLoading.value = true

  // 生成本次请求的唯一标识
  const requestId = ++currentRequestId

  try {
    const response = await axios.get<FFProbeResult>(API_ENDPOINTS.FILE_INFO(fileId))

    // 核心修复：只有当这是最后一次发出的请求时，才更新 UI
    if (requestId === currentRequestId) {
        previewFileInfo.value = response.data
    }
  } catch {
    if (requestId === currentRequestId) {
        message.error('加载预览文件信息失败')
        previewFileInfo.value = null
    }
  } finally {
    if (requestId === currentRequestId) {
        isPreviewLoading.value = false
    }
  }
}

const handleVideoParamChange = () => {
  if (formState.videoCodec === 'copy') {
    formState.videoCodec = originalValues.videoCodec || 'libx264'
    message.info('视频参数已更改，编码器已自动切换为重编码模式。')
  }
}

const handleAudioParamChange = () => {
  if (formState.audioCodec === 'copy') {
    formState.audioCodec = originalValues.audioCodec || 'aac'
    message.info('音频参数已更改，编码器已自动切换为重编码模式。')
  }
}

const mapCodecNameToLib = (codecName: string, type: 'video' | 'audio'): string => {
  const videoMap: Record<string, string> = { h264: 'libx264', hevc: 'libx265', av1: 'libaom-av1' }
  const audioMap: Record<string, string> = { aac: 'aac', opus: 'opus', mp3: 'mp3' }
  if (type === 'video') return videoMap[codecName] || 'libx264'
  return audioMap[codecName] || 'aac'
}

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
      modalStartTime.value = props.initialStartTime
      modalEndTime.value = props.initialEndTime
    }
  },
)

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

watch(previewFileInfo, (fileInfo) => {
  if (!fileInfo) {
    modalStartTime.value = 0
    modalEndTime.value = 0
    return
  }

  const duration = parseFloat(fileInfo.format.duration)
  const newFileId = formState.selectedFiles[0]

  if (newFileId !== fileStore.selectedFileId) {
    modalStartTime.value = 0
    modalEndTime.value = isNaN(duration) ? 0 : duration
  } else {
    modalStartTime.value = props.initialStartTime
    modalEndTime.value = props.initialEndTime
  }

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

const previewFileName = computed<string | null>(() => {
  if (formState.selectedFiles.length === 0) return null
  const file = fileStore.fileList.find((f) => f.id === formState.selectedFiles[0])
  return file?.name || null
})

const totalDuration = computed(() => {
  return previewFileInfo.value ? parseFloat(previewFileInfo.value.format.duration) : 0
})

const copyPreview = async () => {
  const text = ffmpegCommandPreview.value || ''
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text)
      message.success('已复制')
    } else {
      const ta = document.createElement('textarea')
      ta.value = text
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
      message.success('已复制')
    }
  } catch {
    //
  }
}

const ffmpegCommandPreview = computed(() => {
  if (!previewFileInfo.value || !previewFileName.value) return '请选择文件以生成预览...'
  if (selectionMode.value === 'mixed') return '不支持混合处理视频和音频文件。'

  let cmd = `ffmpeg -i "${previewFileName.value}"`
  if (modalStartTime.value > 0 || modalEndTime.value < totalDuration.value) {
    cmd += ` -ss ${modalStartTime.value.toFixed(3)} -to ${modalEndTime.value.toFixed(3)}`
  }

  const vs = previewFileInfo.value.streams?.find((s) => s.codec_type === 'video')
  if (selectionMode.value === 'video' && vs) {
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

const validateAudioOnlyConversion = async () => {
  if (formState.container in ['mp3', 'flac', 'wav', 'aac', 'ogg']) {
    for (const fileId of formState.selectedFiles) {
      // 检查是否有音轨
      try {
        const response = await axios.get<FFProbeResult>(API_ENDPOINTS.FILE_INFO(fileId));
        const hasAudio = response.data.streams?.some(s => s.codec_type === 'audio');

        if (!hasAudio) {
          const fileName = fileStore.fileList.find(f => f.id === fileId)?.name || fileId;
          message.warning(`文件 ${fileName} 无音频流，无法转换为音频格式。`);
          return false;
        }
      } catch (error) {
        console.error(`无法检查文件 ${fileId} 的音轨信息：`, error);
        // 如果无法检查，继续尝试（避免阻止用户操作）
      }
    }
  }
  return true;
};

const handleOk = async () => {
  if (formState.selectedFiles.length === 0) {
    message.error('请至少选择一个要处理的文件！')
    return
  }
  if (selectionMode.value === 'mixed') {
    message.error('无法处理，请不要混合选择视频和音频文件。')
    return
  }

  // 预检查纯音频转换
  if (!await validateAudioOnlyConversion()) {
    return;
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
      useHardwareAcceleration: formState.useHardwareAcceleration, // 传递参数
      preset: formState.preset, // 传递参数
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

    // 1. 本地乐观更新
    fileStore.addTasks(response.data)

    // 🟢 【修改】新增下面这一行：立即从后端同步最新状态
    await fileStore.fetchTaskList()

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
    width="100%"
    style="max-width: 800px;"
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
          <a-button
            key="submit"
            type="primary"
            :loading="isProcessing"
            :disabled="selectionMode === 'mixed' || selectionMode === 'none'"
            @click="handleOk"
          >
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

      <a-alert
        v-if="selectionMode === 'mixed'"
        message="检测到混合文件类型"
        description="请仅选择视频文件或仅选择音频文件进行批量处理，不要混合选择。"
        type="warning"
        show-icon
        style="margin-bottom: 16px"
      />

      <!-- === 新增：硬件加速开关 === -->
      <div
        v-if="selectionMode === 'video' && fileStore.systemCapabilities.has_hardware_acceleration"
        class="hw-accel-section"
        style="margin-bottom: 16px;"
      >
        <a-alert type="success" show-icon>
          <template #message>
            <span style="font-weight: bold">检测到硬件加速可用 ({{ fileStore.systemCapabilities.hardware_type?.toUpperCase() }})</span>
          </template>
          <template #description>
            <a-checkbox v-model:checked="formState.useHardwareAcceleration">
              启用硬件编码加速 (大幅提升速度，但可能略微影响画质)
            </a-checkbox>
          </template>
          <template #icon><ThunderboltOutlined /></template>
        </a-alert>
      </div>
      <!-- ======================== -->

      <div
        v-if="!previewFileInfo && formState.selectedFiles.length > 0"
        class="settings-placeholder"
      >
        <a-spin tip="正在加载文件信息以生成设置选项..."></a-spin>
      </div>

      <fieldset :disabled="isPreviewLoading || selectionMode === 'mixed' || selectionMode === 'none'">
        <div v-if="previewFileInfo">
          <a-form-item label="容器格式">
            <a-select v-model:value="formState.container" :options="availableContainers" />
          </a-form-item>

          <div v-if="selectionMode === 'video' && previewFileInfo.streams?.find((s) => s.codec_type === 'video')">
            <a-divider>视频设置</a-divider>
            <a-form-item label="视频编码">
              <a-select v-model:value="formState.videoCodec">
                <a-select-option value="copy">复制原始视频流 (最快)</a-select-option>
                <a-select-option value="libx264">H.264 (libx264)</a-select-option>
                <a-select-option value="libx265">H.265 (libhevc)</a-select-option>
                <a-select-option value="libaom-av1">AV1 (libaom-av1)</a-select-option>
              </a-select>
              <!-- 添加提示 -->
              <div v-if="formState.useHardwareAcceleration && formState.videoCodec !== 'copy'" class="ant-form-item-explain ant-form-item-explain-connected">
                <small style="color: #1890ff">
                  将自动使用 {{ fileStore.systemCapabilities.hardware_type }} 对应的硬件编码器
                </small>
              </div>
            </a-form-item>

            <a-form-item label="视频比特率 (kbps)">
              <a-input-number
                v-model:value="formState.videoBitrate"
                :min="100"
                style="width: 100%"
                @change="handleVideoParamChange"
              />
            </a-form-item>

            <!-- 性能预设 (速度 vs 画质) -->
            <a-form-item label="性能预设 (速度 vs 画质)">
              <a-radio-group v-model:value="formState.preset" button-style="solid">
                <a-radio-button value="fast">速度优先</a-radio-button>
                <a-radio-button value="balanced">平衡</a-radio-button>
                <a-radio-button value="quality">画质优先</a-radio-button>
              </a-radio-group>

              <!-- 动态提示文案 -->
              <div class="ant-form-item-explain ant-form-item-explain-connected" style="margin-top: 6px; font-size: 12px; color: #888;">
                <span v-if="formState.useHardwareAcceleration && fileStore.systemCapabilities.hardware_type === 'nvidia'">
                  <template v-if="formState.preset === 'fast'">NVENC P1: 极速转码，适合预览。</template>
                  <template v-if="formState.preset === 'balanced'">NVENC P4: 推荐，速度与画质的最佳平衡。</template>
                  <template v-if="formState.preset === 'quality'">NVENC P7: 极致画质，速度较慢，适合存档。</template>
                </span>
                <span v-else-if="!formState.useHardwareAcceleration">
                  <template v-if="formState.preset === 'fast'">CPU Superfast: 文件积大，画质一般。</template>
                  <template v-if="formState.preset === 'balanced'">CPU Medium: 标准设置。</template>
                  <template v-if="formState.preset === 'quality'">CPU Slow: 压缩率高，画质好，但在老旧CPU上极慢。</template>
                </span>
              </div>
            </a-form-item>

            <a-form-item label="分辨率">
              <a-row :gutter="8">
                <a-col :span="10">
                  <a-input-number
                    v-model:value="formState.resolution.width"
                    :min="1"
                    addon-after="宽"
                    style="width: 100%"
                    @change="handleWidthChange"
                  />
                </a-col>
                <a-col :span="10">
                  <a-input-number
                    v-model:value="formState.resolution.height"
                    :min="1"
                    addon-after="高"
                    style="width: 100%"
                    @change="handleHeightChange"
                  />
                </a-col>
                <a-col :span="4" style="display: flex; align-items: center">
                  <a-checkbox v-model:checked="formState.resolution.keepAspectRatio"
                    >锁定比例</a-checkbox
                  >
                </a-col>
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
                @change="handleAudioParamChange"
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
  gap: 8px;
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
