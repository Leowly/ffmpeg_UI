// src/stores/authStore.ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios, { isAxiosError } from 'axios'
import { message } from 'ant-design-vue'
import { API_ENDPOINTS } from '@/api'
import { useFileStore } from '@/stores/fileStore'

// 定义用户接口
interface User {
  id: number
  username: string
}

// 定义后端返回的 Token 数据接口
interface TokenData {
  access_token: string
  token_type: string
}

// 定义标准化的 API 响应接口
interface ApiResponse<T> {
  success: boolean
  data: T | null
  message: string
}

export const useAuthStore = defineStore('auth', () => {
  // 状态
  const token = ref<string | null>(localStorage.getItem('access_token'))
  const user = ref<User | null>(null)
  const isLoggedIn = computed(() => !!token.value)

  // Actions
  async function login(username: string, password: string): Promise<boolean> {
    try {
      const response = await axios.post<ApiResponse<TokenData>>(
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

      if (response.data.success && response.data.data) {
        token.value = response.data.data.access_token
        localStorage.setItem('access_token', token.value!)
        axios.defaults.headers.common['Authorization'] = `Bearer ${token.value}`

        await fetchCurrentUser()

        const fileStore = useFileStore()
        await fileStore.initializeStore()

        message.success(response.data.message || '登录成功！')
        return true
      } else {
        message.error(response.data.message || '发生了一个意外的成功响应错误。')
        return false
      }
    } catch (error: unknown) {
      if (isAxiosError(error)) {
        if (error.response) {
          // 处理 429 速率超限错误
          if (error.response.status === 429) {
            message.error('登录尝试过于频繁，请稍后再试。');
            return false; // 明确返回 false
          }

          const data = error.response.data as unknown as Record<string, unknown>
          let msg = '服务器错误'

          if (data.message) {
            msg = data.message as string // 你的 APIResponse 格式
          } else if (data.detail) {
            // FastAPI 默认错误格式
            msg = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
          } else {
            msg = `服务器错误 (状态码: ${error.response.status})`
          }

          message.error(msg)
        } else {
          message.error('无法连接到服务器，请检查网络或确认后端服务已运行。')
        }
      } else {
        message.error('发生未知错误，请检查浏览器控制台。')
        console.error('An unexpected error occurred during login:', error)
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
      if (isAxiosError(error)) {
        if (error.response) {
          message.error(error.response.data?.detail || `注册失败 (状态码: ${error.response.status})`)
        } else {
          message.error('无法连接到服务器，请检查网络或确认后端服务已运行。')
        }
      } else {
        message.error('发生未知错误，请检查浏览器控制台。')
      }
      return false
    }
  }

  function logout() {
    const fileStore = useFileStore()
    fileStore.resetStore() // <--- 核心修复：清理文件和Socket状态

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
      if (isAxiosError(error) && error.response?.status === 401) {
        logout()
      } else {
        message.error('无法获取用户信息，请检查网络连接。')
      }
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
  }
})
