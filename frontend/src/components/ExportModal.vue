<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { useFileStore } from '@/stores/fileStore'
import { API_ENDPOINTS } from '@/api'
import { message } from 'ant-design-vue'
import axios, { isAxiosError } from 'axios'

// --- 类型定义 ---
interface StreamInfo {
  codec_type: 'video' | 'audio';
  codec_name: string;
  bit_rate?: string;
  width?: number;
  height?: number;
}
interface FormatInfo {
  format_name: string;
  duration: string;
}
interface FFProbeResult {
  streams: StreamInfo[];
  format: FormatInfo;
}
// =======================================================
// ============== 这里是关键修复点 =========================
// =======================================================
// 为发送到后端的数据创建一个具体的类型接口
interface ProcessPayload {
  files: string[];
  container: string;
  startTime: number;
  endTime: number;
  totalDuration: number;
  videoCodec: string;
  audioCodec: string;
  videoBitrate?: number; // 设为可选
  resolution?: { // 设为可选
    width: number;
    height: number;
    keepAspectRatio: boolean;
  };
  audioBitrate?: number; // 设为可选
}


// --- Props and Emits ---
const props = defineProps<{
  visible: boolean;
  fileInfo: FFProbeResult | null;
  initialStartTime: number;
  initialEndTime: number;
}>()
const emit = defineEmits(['update:visible'])

// --- State ---
const fileStore = useFileStore()
const isProcessing = ref(false)

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

// --- Helper & Watchers (保持不变) ---
const mapCodecNameToLib = (codecName: string, type: 'video' | 'audio'): string => {
  const videoMap: Record<string, string> = { h264: 'libx264', hevc: 'libx265', av1: 'libaom-av1' };
  const audioMap: Record<string, string> = { aac: 'aac', opus: 'opus', mp3: 'mp3' };
  if (type === 'video') return videoMap[codecName] || 'libx264';
  return audioMap[codecName] || 'aac';
}

watch(() => props.visible, async (isVisible) => {
  if (isVisible && props.fileInfo) {
    if (fileStore.fileList.length === 0) await fileStore.fetchFileList();
    formState.selectedFiles = fileStore.selectedFileId ? [fileStore.selectedFileId] : [];
    const format = props.fileInfo.format.format_name.split(',')[0];
    formState.container = format || 'mp4';
    formState.videoCodec = 'copy';
    formState.audioCodec = 'copy';
    const vs = props.fileInfo.streams.find(s => s.codec_type === 'video');
    if (vs) {
      originalValues.videoCodec = mapCodecNameToLib(vs.codec_name, 'video');
      originalValues.videoBitrate = Math.round(parseInt(vs.bit_rate || '2000000') / 1000);
      originalValues.width = vs.width || 1920;
      originalValues.height = vs.height || 1080;
      formState.videoBitrate = originalValues.videoBitrate;
      formState.resolution.width = originalValues.width;
      formState.resolution.height = originalValues.height;
    }
    const as = props.fileInfo.streams.find(s => s.codec_type === 'audio');
    if (as) {
      originalValues.audioCodec = mapCodecNameToLib(as.codec_name, 'audio');
      originalValues.audioBitrate = Math.round(parseInt(as.bit_rate || '192000') / 1000);
      formState.audioBitrate = originalValues.audioBitrate;
    }
  }
});

watch(() => [formState.videoBitrate, formState.resolution.width, formState.resolution.height], () => {
    if (formState.videoCodec === 'copy') formState.videoCodec = originalValues.videoCodec;
});
watch(() => formState.audioBitrate, () => {
    if (formState.audioCodec === 'copy') formState.audioCodec = originalValues.audioCodec;
});
watch(() => formState.videoCodec, (newCodec) => {
    if (newCodec === 'copy') {
        formState.videoBitrate = originalValues.videoBitrate;
        formState.resolution.width = originalValues.width;
        formState.resolution.height = originalValues.height;
    }
});
watch(() => formState.audioCodec, (newCodec) => {
    if (newCodec === 'copy') formState.audioBitrate = originalValues.audioBitrate;
});


// --- 智能预览 (保持不变) ---
const previewFileName = computed<string | null>(() => {
    if (formState.selectedFiles.length === 0) return null;
    const currentFileIsInSelection = fileStore.selectedFileId && formState.selectedFiles.includes(fileStore.selectedFileId);
    if (currentFileIsInSelection) {
        const file = fileStore.fileList.find(f => f.id === fileStore.selectedFileId);
        return file?.name || formState.selectedFiles[0];
    }
    const firstSelectedFile = fileStore.fileList.find(f => f.id === formState.selectedFiles[0]);
    return firstSelectedFile?.name || null;
});

const previewTooltipText = computed(() => {
    const count = formState.selectedFiles.length;
    if (count <= 1) return "根据当前设置生成的 FFmpeg 命令预览。";
    return `这是一个基于文件 "${previewFileName.value}" 生成的命令预览。相同的参数将应用于所有选中的 ${count} 个文件。`;
});

const ffmpegCommandPreview = computed(() => {
    if (!props.fileInfo || !previewFileName.value) return '请选择文件以生成预览...';
    let cmd = `ffmpeg -i "${previewFileName.value}"`;
    if (props.initialStartTime > 0 || props.initialEndTime < parseFloat(props.fileInfo.format.duration)) {
        cmd += ` -ss ${props.initialStartTime.toFixed(3)} -to ${props.initialEndTime.toFixed(3)}`;
    }
    const vs = props.fileInfo.streams.find(s => s.codec_type === 'video');
    const isVideoContainer = ['mp4', 'mkv', 'mov'].includes(formState.container);
    if (isVideoContainer && vs) {
        cmd += ` -c:v ${formState.videoCodec}`;
        if (formState.videoCodec !== 'copy') {
            if (formState.videoBitrate !== originalValues.videoBitrate) cmd += ` -b:v ${formState.videoBitrate}k`;
            if (formState.resolution.width !== originalValues.width || formState.resolution.height !== originalValues.height) cmd += ` -s ${formState.resolution.width}x${formState.resolution.height}`;
        }
    } else {
        cmd += ` -vn`;
    }
    const as = props.fileInfo.streams.find(s => s.codec_type === 'audio');
    if (as) {
        cmd += ` -c:a ${formState.audioCodec}`;
        if (formState.audioCodec !== 'copy' && formState.audioBitrate !== originalValues.audioBitrate) {
            cmd += ` -b:a ${formState.audioBitrate}k`;
        }
    } else {
        cmd += ` -an`;
    }
    const baseName = previewFileName.value.substring(0, previewFileName.value.lastIndexOf('.'));
    const outputFileName = `${baseName}_processed.${formState.container}`;
    cmd += ` "${outputFileName}"`;
    return cmd;
});

// --- 后端交互 ---
const handleOk = async () => {
    if (formState.selectedFiles.length === 0) {
      message.error('请至少选择一个要处理的文件！')
      return
    }
    isProcessing.value = true
    try {
      // 修正: 使用我们定义的 ProcessPayload 接口代替 'any'
      const payload: ProcessPayload = {
        files: formState.selectedFiles,
        container: formState.container,
        startTime: props.initialStartTime,
        endTime: props.initialEndTime,
        totalDuration: props.fileInfo ? parseFloat(props.fileInfo.format.duration) : 0,
        videoCodec: formState.videoCodec,
        audioCodec: formState.audioCodec,
      }
      if (formState.videoCodec !== 'copy') {
        if (formState.videoBitrate !== originalValues.videoBitrate) payload.videoBitrate = formState.videoBitrate
        if (formState.resolution.width !== originalValues.width || formState.resolution.height !== originalValues.height) payload.resolution = formState.resolution
      }
      if (formState.audioCodec !== 'copy' && formState.audioBitrate !== originalValues.audioBitrate) payload.audioBitrate = formState.audioBitrate
      const response = await axios.post(API_ENDPOINTS.PROCESS_FILE, payload)
      const createdCount = response.data.tasks?.length || 0
      message.success(`成功创建 ${createdCount} 个处理任务，已在后台开始执行。`)
      emit('update:visible', false)
    } catch (error: unknown) {
      let errorMessage = '创建任务失败'
      if (isAxiosError(error)) errorMessage = error.response?.data?.error || error.message
      else if (error instanceof Error) errorMessage = error.message
      message.error(errorMessage)
    } finally {
      isProcessing.value = false
    }
};

const handleCancel = () => { emit('update:visible', false) };

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
     <!-- ======================================================= -->
     <!-- ============== 全新设计的智能 Footer ==================== -->
     <!-- ======================================================= -->
     <template #footer>
      <div class="modal-footer-grid">
        <!-- 智能命令预览，带有动态 Tooltip -->
        <a-tooltip :title="previewTooltipText">
          <div class="ffmpeg-command-preview">
            <a-typography-text code>
              {{ ffmpegCommandPreview }}
            </a-typography-text>
          </div>
        </a-tooltip>

        <!-- 操作按钮 -->
        <div>
          <a-button key="back" @click="handleCancel">取消</a-button>
          <a-button key="submit" type="primary" :loading="isProcessing" @click="handleOk">
            开始处理 ({{ formState.selectedFiles.length }})
          </a-button>
        </div>
      </div>
    </template>

    <!-- 表单内容 (与上一版相同，保持不变) -->
    <a-form layout="vertical">
      <a-form-item label="待处理文件 (可多选)">
        <a-checkbox-group v-if="fileStore.fileList.length > 0" v-model:value="formState.selectedFiles" style="width: 100%">
          <a-row :gutter="[8, 8]">
            <a-col v-for="file in fileStore.fileList" :key="file.id" :span="24">
              <a-checkbox :value="file.id">{{ file.name }}</a-checkbox>
            </a-col>
          </a-row>
        </a-checkbox-group>
        <a-alert v-else message="没有可用的文件" type="info" />
      </a-form-item>

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

      <div v-if="props.fileInfo?.streams.find(s => s.codec_type === 'video')">
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
           <a-input-number v-model:value="formState.videoBitrate" :min="100" style="width: 100%;" />
        </a-form-item>

        <a-form-item label="分辨率">
            <a-row :gutter="8">
              <a-col :span="10"><a-input-number v-model:value="formState.resolution.width" :min="1" addon-after="宽" style="width: 100%"/></a-col>
              <a-col :span="10"><a-input-number v-model:value="formState.resolution.height" :min="1" addon-after="高" style="width: 100%"/></a-col>
              <a-col :span="4" style="display: flex; align-items: center;"><a-checkbox v-model:checked="formState.resolution.keepAspectRatio">锁定比例</a-checkbox></a-col>
            </a-row>
        </a-form-item>
      </div>

      <div v-if="props.fileInfo?.streams.find(s => s.codec_type === 'audio')">
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
           <a-input-number v-model:value="formState.audioBitrate" :min="32" style="width: 100%;" />
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
.ffmpeg-command-preview code {
  font-size: 12px;
}
</style>
