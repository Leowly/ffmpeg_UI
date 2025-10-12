// src/stores/authStore.ts
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import axios from 'axios';
import { message } from 'ant-design-vue';

// 定义用户接口
interface User {
  id: number;
  username: string;
}

export const useAuthStore = defineStore('auth', () => {
  // 状态
  const token = ref<string | null>(localStorage.getItem('access_token'));
  const user = ref<User | null>(null);
  const isLoggedIn = computed(() => !!token.value);

  // Actions
  async function login(username: string, password: string): Promise<boolean> {
    try {
      const response = await axios.post('http://127.0.0.1:8000/token', new URLSearchParams({
        username: username,
        password: password,
      }), {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded'
        }
      });
      token.value = response.data.access_token;
      localStorage.setItem('access_token', token.value!);
      axios.defaults.headers.common['Authorization'] = `Bearer ${token.value}`;
      await fetchCurrentUser();
      message.success('登录成功！');
      return true;
    } catch (error: unknown) {
      console.error('登录失败:', error);
      if (axios.isAxiosError(error)) {
        message.error(error.response?.data?.detail || '登录失败，请检查用户名和密码。');
      } else {
        message.error('登录失败，请检查用户名和密码。');
      }
      return false;
    }
  }

  async function register(username: string, password: string): Promise<boolean> {
    try {
      await axios.post('http://127.0.0.1:8000/users/', { username, password });
      message.success('注册成功！请登录。');
      return true;
    } catch (error: unknown) {
      console.error('注册失败:', error);
      if (axios.isAxiosError(error)) {
        message.error(error.response?.data?.detail || '注册失败，请稍后再试。');
      } else {
        message.error('注册失败，请稍后再试。');
      }
      return false;
    }
  }

  function logout() {
    token.value = null;
    user.value = null;
    localStorage.removeItem('access_token');
    delete axios.defaults.headers.common['Authorization'];
    message.info('您已退出登录。');
  }

  async function fetchCurrentUser() {
    if (!token.value) {
      user.value = null;
      return;
    }
    try {
      axios.defaults.headers.common['Authorization'] = `Bearer ${token.value}`;
      const response = await axios.get<User>('http://127.0.0.1:8000/users/me');
      user.value = response.data;
    } catch (error) {
      console.error('获取当前用户失败:', error);
      // 如果获取用户失败，可能是token过期或无效，强制登出
      logout();
    }
  }

  // 初始化时检查token并获取用户信息
  if (token.value) {
    fetchCurrentUser();
  }

  return {
    token,
    user,
    isLoggedIn,
    login,
    register,
    logout,
    fetchCurrentUser,
  };
});
