<template>
  <a-dropdown placement="top" :trigger="['click']">
    <a-button type="primary" shape="round" size="large">
      <template #icon><UserOutlined /></template>
      <span>{{ authStore.user?.username }}</span>
    </a-button>

    <template #overlay>
      <a-menu>
        <div class="user-id-display">
          id: {{ authStore.user?.id }}
        </div>
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

const authStore = useAuthStore();

const handleLogout = () => {
  authStore.logout();
};
</script>

<style scoped>
/* 3. 为我们的 div 添加样式 */
.user-id-display {
  /* 文本居中 */
  text-align: center;
  /* 设置一个柔和的文本颜色，表示这是信息文本 */
  color: rgb(70, 70, 70);

  /* 设置字体大小与菜单项一致 */
  font-size: 14px;
}
</style>
