import type { CapacitorConfig } from '@capacitor/cli';
import { config as dotenvConfig } from 'dotenv';
import { resolve } from 'path';


dotenvConfig({ path: resolve(__dirname, '../.env') });

const backendServerUrl = process.env.VITE_API_BASE_URL;

if (!backendServerUrl) {
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
