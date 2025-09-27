// src/api/index.ts

// 1. 获取基础 URL
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

// 2. 定义并导出所有的 API 端点
export const API_ENDPOINTS = {
  // 文件上传地址
  FILE_UPLOAD: `${API_BASE_URL}/api/upload`,
  // 文件列表
  FILE_LIST: `${API_BASE_URL}/api/files`,
  // 删除文件
  FILE_DELETE: (fileId: string) =>
    `${API_BASE_URL}/api/delete-file?filename=${encodeURIComponent(fileId)}`,
  // 获取文件信息
  FILE_INFO: (fileId: string) =>
    `${API_BASE_URL}/api/file-info?filename=${encodeURIComponent(fileId)}`,

  // --- 新增 ---
  // 创建处理任务
  PROCESS_FILE: `${API_BASE_URL}/api/process`,
  // 获取任务状态
  TASK_STATUS: (taskId: string) => `${API_BASE_URL}/api/task-status/${taskId}`,
}
