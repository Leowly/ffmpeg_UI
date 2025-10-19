// src/api/index.ts

const BASE_URL = import.meta.env.VITE_API_BASE_URL

export const API_ENDPOINTS = {
  TOKEN: `${BASE_URL}/token`,
  CREATE_USER: `${BASE_URL}/users/`,
  CURRENT_USER: `${BASE_URL}/users/me`,
  FILE_LIST: `${BASE_URL}/api/files`,
  UPLOAD_FILE: `${BASE_URL}/api/upload`,
  DELETE_FILE: `${BASE_URL}/api/delete-file`,
  FILE_INFO: (fileId: string) => `${BASE_URL}/api/file-info?filename=${fileId}`,
  PROCESS_FILE: `${BASE_URL}/api/process`,
  TASK_LIST: `${BASE_URL}/api/tasks`,
  DELETE_TASK: (taskId: number) => `${BASE_URL}/api/tasks/${taskId}`,
  DOWNLOAD_TASK: (taskId: number) => `${BASE_URL}/api/download-task/${taskId}`, // 示例，可能需要实现
}
