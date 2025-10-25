// src/stores/authStore.ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'
import { message } from 'ant-design-vue'
import { API_ENDPOINTS } from '@/api'

// 定义用户接口
interface User {
  id: number
  username: string
}

export const useAuthStore = defineStore('auth', () => {
  // 状态
  const token = ref<string | null>(localStorage.getItem('access_token'))
  const user = ref<User | null>(null)
  const isLoggedIn = computed(() => !!token.value)

  // Actions
  async function login(username: string, password: string): Promise<boolean> {
    try {
      const response = await axios.post(
        API_ENDPOINTS.TOKEN,
        new URLSearchParams({
          username: username,
          password: password,
        }),
        {
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
          },
        },
      )
      token.value = response.data.access_token
      localStorage.setItem('access_token', token.value!)
      axios.defaults.headers.common['Authorization'] = `Bearer ${token.value}`
      await fetchCurrentUser(); // 登录成功后立即获取用户信息
      message.success('登录成功！')
      return true
    } catch (error: unknown) {
      console.error('登录失败:', error)
      if (axios.isAxiosError(error)) {
        message.error(error.response?.data?.detail || '登录失败，请检查用户名和密码。')
      } else {
        message.error('登录失败，请检查用户名和密码。')
      }
      return false
    }
  }

  async function register(username: string, password: string): Promise<boolean> {
    try {
      await axios.post(API_ENDPOINTS.CREATE_USER, { username, password })
      message.success('注册成功！请登录。')
      return true
    } catch (error: unknown) {
      console.error('注册失败:', error)
      if (axios.isAxiosError(error)) {
        message.error(error.response?.data?.detail || '注册失败，请稍后再试。')
      } else {
        message.error('注册失败，请稍后再试。')
      }
      return false
    }
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem('access_token')
    delete axios.defaults.headers.common['Authorization']
    message.info('您已退出登录。')
  }

  async function fetchCurrentUser() {
    if (!token.value) {
      user.value = null
      return
    }
    try {
      axios.defaults.headers.common['Authorization'] = `Bearer ${token.value}`
      const response = await axios.get<User>(API_ENDPOINTS.CURRENT_USER)
      user.value = response.data
    } catch (error) {
      console.error('获取当前用户失败:', error)
      // 仅当错误是 401 未授权时，才执行登出
      if (axios.isAxiosError(error) && error.response?.status === 401) {
        logout()
      } else {
        // 对于其他错误 (如网络问题)，只提示，不登出
        message.error('无法获取用户信息，请检查网络连接。')
      }
    }
  }

  // 验证token是否有效
  async function validateToken() {
    if (!token.value) {
      return false
    }
    try {
      await axios.get<User>(API_ENDPOINTS.CURRENT_USER)
      return true
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 401) {
        logout() // token无效，自动登出
      }
      return false
    }
  }

  return {
    token,
    user,
    isLoggedIn,
    login,
    register,
    logout,
    fetchCurrentUser,
    validateToken,
  }
})
