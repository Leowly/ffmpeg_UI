// src/api/index.ts

// 根据运行环境智能确定API基础URL
let BASE_URL = import.meta.env.VITE_API_BASE_URL;

// 检查是否在Capacitor环境中运行
if (window.Capacitor) {
  // 在Capacitor环境中，使用Capacitor的服务器URL
  // 注意：这需要在Capacitor配置中设置服务器URL
  const capacitorServerUrl = window.Capacitor.getServerUrl ? window.Capacitor.getServerUrl() : null;
  if (capacitorServerUrl) {
    BASE_URL = capacitorServerUrl;
  } else {
    // 如果Capacitor没有配置服务器URL，可以使用默认值或抛出错误
    console.warn('Capacitor server URL is not configured. Please set the server URL in capacitor.config.ts');
  }
}

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
  TASK_PROGRESS: (taskId: number) => `${BASE_URL}/api/tasks/${taskId}/progress`,
  DELETE_TASK: (taskId: number) => `${BASE_URL}/api/tasks/${taskId}`,
  DOWNLOAD_FILE: (fileId: string) => `${BASE_URL}/api/download-file/${fileId}`,
  DOWNLOAD_TASK: (taskId: number) => `${BASE_URL}/api/download-task/${taskId}`, // 示例，可能需要实现
}
