<template>
  <div class="auth-container">
    <a-card
      :title="currentMode === 'login' ? '登录' : '注册'"
      :bordered="false"
      style="width: 400px"
    >
      <a-form
        v-if="currentMode === 'login'"
        :model="loginFormState"
        @finish="handleLogin"
        layout="vertical"
      >
        <a-form-item
          label="用户名"
          name="username"
          :rules="[
            { required: true, message: '请输入用户名!' },
            { min: 1, message: '用户名至少1个字符' },
            { max: 50, message: '用户名最多50个字符' },
            { pattern: /^[a-zA-Z0-9_]+$/, message: '用户名只能包含字母、数字和下划线' },
          ]"
        >
          <a-input v-model:value="loginFormState.username" />
        </a-form-item>

        <a-form-item
          label="密码"
          name="password"
          :rules="[
            { required: true, message: '请输入密码!' },
          ]"
        >
          <a-input-password v-model:value="loginFormState.password" />
        </a-form-item>

        <a-form-item>
          <a-button type="primary" html-type="submit" :loading="loading" block> 登录 </a-button>
        </a-form-item>
        <a-form-item>
          <a-button type="link" @click="currentMode = 'register'" block>
            没有账号？立即注册
          </a-button>
        </a-form-item>
      </a-form>

      <a-form v-else :model="registerFormState" @finish="handleRegister" layout="vertical">
        <a-form-item
          label="用户名"
          name="username"
          :rules="[
            { required: true, message: '请输入用户名!' },
            { min: 1, message: '用户名至少1个字符' },
            { max: 50, message: '用户名最多50个字符' },
            { pattern: /^[a-zA-Z0-9_]+$/, message: '用户名只能包含字母、数字和下划线' },
          ]"
        >
          <a-input v-model:value="registerFormState.username" />
        </a-form-item>

        <a-form-item
          label="密码"
          name="password"
          :rules="[
            { required: true, message: '请输入密码!' },
            { min: 8, message: '密码至少8个字符' },
            { max: 72, message: '密码最多72个字符' },
            {
              pattern: /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$/,
              message: '密码必须包含大小写字母和数字',
            },
          ]"
        >
          <a-input-password v-model:value="registerFormState.password" />
        </a-form-item>

        <a-form-item
          label="确认密码"
          name="confirmPassword"
          :rules="[
            { required: true, message: '请确认密码!' },
            { validator: validateConfirmPassword, trigger: 'change' },
          ]"
        >
          <a-input-password v-model:value="registerFormState.confirmPassword" />
        </a-form-item>

        <a-form-item>
          <a-button type="primary" html-type="submit" :loading="loading" block> 注册 </a-button>
        </a-form-item>
        <a-form-item>
          <a-button type="link" @click="currentMode = 'login'" block> 已有账号？立即登录 </a-button>
        </a-form-item>
      </a-form>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useAuthStore } from '@/stores/authStore'
import { message } from 'ant-design-vue'
import type { RuleObject } from 'ant-design-vue/es/form/interface'

const authStore = useAuthStore()
const loading = ref(false)
const currentMode = ref<'login' | 'register'>('login')

const loginFormState = reactive({
  username: '',
  password: '',
})

const registerFormState = reactive({
  username: '',
  password: '',
  confirmPassword: '',
})

const handleLogin = async () => {
  loading.value = true
  await authStore.login(loginFormState.username, loginFormState.password)
  loading.value = false
}

const handleRegister = async () => {
  if (registerFormState.password !== registerFormState.confirmPassword) {
    message.error('两次输入的密码不一致！')
    return
  }
  loading.value = true
  const success = await authStore.register(registerFormState.username, registerFormState.password)
  if (success) {
    currentMode.value = 'login'
    registerFormState.username = ''
    registerFormState.password = ''
    registerFormState.confirmPassword = ''
  }
  loading.value = false
}

const validateConfirmPassword = (_rule: RuleObject, value: string) => {
  if (currentMode.value === 'register' && value !== registerFormState.password) {
    return Promise.reject('两次输入的密码不一致！')
  }
  return Promise.resolve()
}
</script>

<style scoped>
.auth-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background-color: #f0f2f5;
}
</style>
