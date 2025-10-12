<template>
  <a-dropdown placement="top" :trigger="['click']">
    <!-- 使用 a-button 作为触发器，以实现视觉统一 -->
    <a-button type="primary" shape="round" size="large">
      <template #icon><UserOutlined /></template>
      <!-- 修正：从 authStore.user.username 获取用户名 -->
      <span>{{ authStore.user?.username }}</span>
    </a-button>
    <template #overlay>
      <a-menu>
        <a-menu-item key="logout" @click="handleLogout">
          退出登录
        </a-menu-item>
      </a-menu>
    </template>
  </a-dropdown>
</template>

<script setup lang="ts">
import { useAuthStore } from '@/stores/authStore';
import { UserOutlined } from '@ant-design/icons-vue';
import { useRouter } from 'vue-router';

const authStore = useAuthStore();
const router = useRouter();

const handleLogout = () => {
  authStore.logout();
  // 修正：补全 router.push 的括号
  router.push('/auth');
};
</script>

<style scoped>
/* 移除所有局部样式，因为 a-button 自带样式 */
</style>
