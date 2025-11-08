import type { CapacitorConfig } from '@capacitor/cli';
import { config as dotenvConfig } from 'dotenv';
import { resolve } from 'path';

// 1. 核心修改：加载与当前文件同目录下的 .env.production 文件
// __dirname 在这里就是 'frontend' 目录的绝对路径
dotenvConfig({ path: resolve(__dirname, '.env.production') });

// 2. 从 process.env 中获取 VITE_API_BASE_URL
const backendServerUrl = process.env.VITE_API_BASE_URL;

// 3. (推荐) 添加检查，确保变量已成功加载
if (!backendServerUrl) {
  throw new Error('VITE_API_BASE_URL is not defined in your frontend/.env.production file.');
}

const config: CapacitorConfig = {
  appId: 'com.leowly.ffmpegui',
  appName: 'ffmpeg studio',
  webDir: 'dist',
  server: {
    // 4. 在这里使用从 .env.production 文件读取到的变量
    url: backendServerUrl,
    cleartext: true
  },
  android: {
    allowMixedContent: true,
    captureInput: true,
    webContentsDebuggingEnabled: true
  }
};

export default config;
