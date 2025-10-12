// src/stores/fileStore.ts
import { defineStore } from 'pinia'
import { ref, type Ref } from 'vue'
import axios from 'axios'
import { API_ENDPOINTS } from '@/api'

// 定义文件对象的接口
export interface UserFile {
  uid: string
  id: string
  name: string
  status: 'done' | 'uploading' | 'error'
  size: number
  response: {
    file_id: string
    original_name: string
    temp_path: string
  }
}

export const useFileStore = defineStore('file', () => {
  // state: 当前选中的文件ID
  const selectedFileId = ref<string | null>(null)
  // state: 用户上传的所有文件的列表
  const fileList: Ref<UserFile[]> = ref([])

  // actions: 修改 state 的方法
  function selectFile(fileId: string | null) {
    selectedFileId.value = fileId
  }

  // actions: 从后端获取并更新文件列表
  async function fetchFileList() {
    try {
      const response = await axios.get<UserFile[]>(API_ENDPOINTS.FILE_LIST)
      fileList.value = response.data
    } catch (error) {
      console.error('Failed to fetch file list:', error)
      fileList.value = [] // 出错时清空列表
    }
  }

  // actions: 添加一个文件到列表 (上传成功后调用)
  function addFile(file: UserFile) {
    fileList.value.push(file)
  }

  // actions: 从列表中移除一个文件 (删除成功后调用)
  function removeFile(fileId: string) {
    fileList.value = fileList.value.filter((f) => f.id !== fileId)
    if (selectedFileId.value === fileId) {
      selectedFileId.value = null // 如果删除的是当前选中的文件，则取消选中
    }
  }

  return {
    selectedFileId,
    fileList,
    selectFile,
    fetchFileList,
    addFile,
    removeFile,
  }
})
