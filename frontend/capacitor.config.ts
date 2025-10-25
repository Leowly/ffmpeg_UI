import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.leowly.ffmpegui',
  appName: 'ffmpeg studio',
  webDir: 'dist',
  server: {
    url: 'https://ffmpeg.0426233.xyz',  // 您的后端服务器地址
    cleartext: true  // 允许非HTTPS请求（如果需要的话）
  },
  android: {
    allowMixedContent: true,
    captureInput: true,
    webContentsDebuggingEnabled: true
  }
};

export default config;
