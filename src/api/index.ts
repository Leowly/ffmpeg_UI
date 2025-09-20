// src/api/index.ts

// 1. 获取基础 URL
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

// 2. 定义并导出所有的 API 端点
export const API_ENDPOINTS = {
  // 文件上传地址
  FILE_UPLOAD: `${API_BASE_URL}/api/upload`,
  FILE_DELETE: (fileId: string) => `${API_BASE_URL}/api/delete-file/${fileId}`,
  FILE_LIST: `${API_BASE_URL}/api/files`,
}
