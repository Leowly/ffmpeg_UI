// src/stores/fileStore.ts
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useFileStore = defineStore('file', () => {
  // state: 当前选中的文件ID
  const selectedFileId = ref<string | null>(null)

  // actions: 修改 state 的方法
  function selectFile(fileId: string | null) {
    selectedFileId.value = fileId
  }

  return { selectedFileId, selectFile }
})
