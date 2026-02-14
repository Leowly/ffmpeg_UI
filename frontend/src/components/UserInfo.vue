<template>
  <a-dropdown placement="top" :trigger="['click']">
    <a-button class="user-button">
      <a-avatar class="user-avatar" :size="32">
        <template #icon><UserOutlined /></template>
      </a-avatar>
      <span class="username">{{ authStore.user?.username }}</span>
      <DownOutlined class="dropdown-arrow" />
    </a-button>

    <template #overlay>
      <a-menu class="user-dropdown-menu">
        <div class="user-info-header">
          <a-avatar :size="40" class="menu-avatar">
            <template #icon><UserOutlined /></template>
          </a-avatar>
          <div class="user-details">
            <div class="user-name">{{ authStore.user?.username }}</div>
            <div class="user-id">ID: {{ authStore.user?.id }}</div>
          </div>
        </div>
        <a-menu-divider />
        <a-menu-item key="logout" class="logout-item" @click="handleLogout">
          <LogoutOutlined />
          <span>退出登录</span>
        </a-menu-item>
      </a-menu>
    </template>
  </a-dropdown>
</template>

<script setup lang="ts">
import { useAuthStore } from '@/stores/authStore'
import { UserOutlined, DownOutlined, LogoutOutlined } from '@ant-design/icons-vue'

const authStore = useAuthStore()

const handleLogout = () => {
  authStore.logout()
}
</script>

<style scoped>
.user-button {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 0 16px;
  min-width: 100px;
  height: 40px;
  border-radius: 20px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.35);
  transition: all 0.3s ease;
  color: #fff;
}

.user-button:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.45);
}

.user-button:active {
  transform: translateY(0);
  box-shadow: 0 2px 6px rgba(102, 126, 234, 0.35);
}

.user-avatar {
  background: rgba(255, 255, 255, 0.25);
  color: #fff;
}

.username {
  font-weight: 500;
  font-size: 14px;
  max-width: 80px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dropdown-arrow {
  font-size: 10px;
  opacity: 0.8;
}

.user-dropdown-menu {
  min-width: 180px;
  border-radius: 12px;
  padding: 8px;
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.12);
}

.user-dropdown-menu :deep(.ant-dropdown-menu-item) {
  border-radius: 8px;
  padding: 10px 12px;
}

.user-info-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
}

.menu-avatar {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
}

.user-details {
  display: flex;
  flex-direction: column;
}

.user-name {
  font-weight: 600;
  font-size: 15px;
  color: #1a1a1a;
}

.user-id {
  font-size: 12px;
  color: #888;
  margin-top: 2px;
}

.logout-item {
  color: #ff4d4f;
  display: flex;
  align-items: center;
  gap: 8px;
}

.logout-item:hover {
  background: #fff1f0;
}

@media (max-width: 768px) {
  .user-button {
    min-width: 44px;
    width: 44px;
    height: 44px;
    padding: 0;
    border-radius: 50%;
  }

  .username {
    display: none;
  }

  .dropdown-arrow {
    display: none;
  }
}
</style>
