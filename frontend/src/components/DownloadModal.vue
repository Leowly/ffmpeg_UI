<script setup lang="ts">
import { ref, watch } from 'vue'
import { useFileStore } from '@/stores/fileStore'
import { message } from 'ant-design-vue'
import { DownloadOutlined } from '@ant-design/icons-vue'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits(['update:visible'])

const fileStore = useFileStore()
const selectedFileIds = ref<string[]>([])

watch(
  () => props.visible,
  (isVisible) => {
    if (isVisible) {
      selectedFileIds.value = []
      if (fileStore.fileList.length === 0) {
        fileStore.fetchFileList()
      }
    }
  },
)

const handleOk = async () => {
  if (selectedFileIds.value.length === 0) {
    message.warning('请选择要下载的文件')
    return
  }

  const delayMs = Number(import.meta.env.VITE_DOWNLOAD_DELAY_MS) || 200

  for (const fileId of selectedFileIds.value) {
    await fileStore.downloadFile(fileId)
    await new Promise((resolve) => setTimeout(resolve, delayMs))
  }

  emit('update:visible', false)
}

const handleCancel = () => {
  emit('update:visible', false)
}
</script>

<template>
  <a-modal
    :open="props.visible"
    title="一键下载"
    :width="500"
    :footer="null"
    @cancel="handleCancel"
  >
    <div class="download-modal-content">
      <a-alert
        message="点击下载后，浏览器将自动管理下载进度"
        type="info"
        show-icon
        style="margin-bottom: 16px"
      />

      <div class="file-list">
        <a-checkbox-group
          v-if="fileStore.fileList.length > 0"
          v-model:value="selectedFileIds"
          style="width: 100%"
        >
          <a-row :gutter="[8, 8]">
            <a-col v-for="file in fileStore.fileList" :key="file.id" :span="24">
              <a-checkbox :value="file.id">
                {{ file.name }}
                <span class="file-size">({{ (file.size / 1024 / 1024).toFixed(2) }} MB)</span>
              </a-checkbox>
            </a-col>
          </a-row>
        </a-checkbox-group>
        <a-empty v-else description="没有可下载的文件" />
      </div>

      <div class="modal-footer">
        <a-button @click="handleCancel">取消</a-button>
        <a-button type="primary" :disabled="selectedFileIds.length === 0" @click="handleOk">
          <DownloadOutlined />
          下载 ({{ selectedFileIds.length }})
        </a-button>
      </div>
    </div>
  </a-modal>
</template>

<style scoped>
.download-modal-content {
  min-height: 300px;
}

.file-list {
  max-height: 400px;
  overflow-y: auto;
  margin-bottom: 16px;
}

.file-size {
  color: #999;
  font-size: 12px;
  margin-left: 8px;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #f0f0f0;
}
</style>
