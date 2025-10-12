// src/api/index.ts

const BASE_URL = 'http://127.0.0.1:8000';

export const API_ENDPOINTS = {
  TOKEN: `${BASE_URL}/token`,
  CURRENT_USER: `${BASE_URL}/users/me`,
  FILE_LIST: `${BASE_URL}/api/files`,
  UPLOAD_FILE: `${BASE_URL}/api/upload`,
  FILE_INFO: (fileId: string) => `${BASE_URL}/api/file-info?filename=${fileId}`,
  PROCESS_FILE: `${BASE_URL}/api/process`,
  TASK_LIST: `${BASE_URL}/api/tasks`,
  DOWNLOAD_TASK: (taskId: number | string) => `${BASE_URL}/api/download-task/${taskId}`,
  DELETE_FILE: (fileId: string) => `${BASE_URL}/api/delete-file?filename=${fileId}`,
};
