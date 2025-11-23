import type { CapacitorConfig } from '@capacitor/cli';
import { config as dotenvConfig } from 'dotenv';
import { resolve } from 'path';

// 核心修改：指向上一级目录的 .env 文件
dotenvConfig({ path: resolve(__dirname, '../.env') });

const backendServerUrl = process.env.VITE_API_BASE_URL;

if (!backendServerUrl) {
  // 修改报错提示，指明是根目录的 .env
  throw new Error('VITE_API_BASE_URL is not defined in the root .env file.');
}

const config: CapacitorConfig = {
  appId: 'com.leowly.ffmpegui',
  appName: 'ffmpeg studio',
  webDir: 'dist',
  server: {
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
