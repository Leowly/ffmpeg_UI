// src/types/capacitor.d.ts

declare global {
  interface Window {
    Capacitor: {
      getServerUrl?: () => string | null;
      [key: string]: unknown;
    };
  }
}

export {};
