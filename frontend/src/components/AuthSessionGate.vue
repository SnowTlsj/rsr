<template>
  <div v-if="authStore.checking" class="auth-loading">正在校验管理会话...</div>
  <div v-else-if="authStore.authenticated">
    <slot />
  </div>
  <div v-else class="auth-shell">
    <div class="auth-backdrop" aria-hidden="true"></div>
    <form class="auth-card" @submit.prevent="submit">
      <div class="auth-badge">管理入口</div>
      <h1>肉苁蓉播种监测平台</h1>
      <p>输入管理令牌以建立安全会话。验证成功后，浏览器将保存 HttpOnly Cookie，后续操作无需再次暴露令牌。</p>
      <label class="auth-label" for="admin-token-input">管理令牌</label>
      <input
        id="admin-token-input"
        v-model.trim="token"
        type="password"
        autocomplete="current-password"
        placeholder="请输入 ADMIN_TOKEN"
      />
      <button type="submit" :disabled="authStore.submitting || !token">
        {{ authStore.submitting ? '验证中...' : '进入系统' }}
      </button>
      <div class="auth-tips">
        <span>同源代理已启用</span>
        <span>会话安全存储</span>
        <span>支持移动端访问</span>
      </div>
      <div v-if="authStore.error" class="auth-error">{{ authStore.error }}</div>
    </form>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue';
import { useAuthStore } from '@/stores/authStore';

const authStore = useAuthStore();
const token = ref('');
const handleAuthExpired = () => {
  authStore.authenticated = false;
  authStore.error = '管理会话已失效，请重新输入令牌';
};

const submit = async () => {
  if (!token.value) return;
  await authStore.login(token.value);
  if (authStore.authenticated) {
    token.value = '';
  }
};

onMounted(async () => {
  window.addEventListener('rsr-auth-expired', handleAuthExpired);
  await authStore.checkSession();
});

onBeforeUnmount(() => {
  window.removeEventListener('rsr-auth-expired', handleAuthExpired);
});
</script>

<style scoped>
.auth-loading,
.auth-shell {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    radial-gradient(circle at 18% 20%, rgba(182, 139, 92, 0.18) 0, rgba(182, 139, 92, 0.04) 30%, transparent 48%),
    radial-gradient(circle at 82% 18%, rgba(139, 113, 73, 0.16) 0, rgba(139, 113, 73, 0.03) 28%, transparent 44%),
    linear-gradient(180deg, #f5ecdf 0%, #eadcc6 100%);
  position: relative;
  overflow: hidden;
}

.auth-backdrop {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(rgba(255,255,255,0.18), rgba(255,255,255,0.18)),
    url('/themes/antique-paper.jpg') center/cover no-repeat;
  opacity: 0.45;
  pointer-events: none;
}

.auth-card {
  position: relative;
  z-index: 1;
  width: min(460px, calc(100vw - 32px));
  padding: 30px;
  border-radius: 22px;
  border: 1px solid rgba(164, 122, 81, 0.42);
  background: rgba(255, 250, 244, 0.92);
  box-shadow: 0 24px 54px rgba(73, 47, 24, 0.18), inset 0 1px 0 rgba(255,255,255,0.55);
  backdrop-filter: blur(10px);
}

.auth-badge {
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  border-radius: 999px;
  background: linear-gradient(140deg, #f2e1cc 0%, #e3c7a6 100%);
  color: #5d3f24;
  border: 1px solid #a47a51;
  font-size: 12px;
  font-weight: 700;
  margin-bottom: 12px;
}

.auth-card h1 {
  margin: 0 0 10px;
  font-size: 28px;
  color: #3f2a18;
  letter-spacing: 0.4px;
}

.auth-card p {
  margin: 0 0 18px;
  color: #6b4c2e;
  font-size: 14px;
  line-height: 1.7;
}

.auth-label {
  display: block;
  margin-bottom: 8px;
  color: #5d3f24;
  font-size: 13px;
  font-weight: 700;
}

.auth-card input {
  width: 100%;
  padding: 13px 14px;
  margin-bottom: 14px;
  border: 1px solid #cda982;
  border-radius: 12px;
  font-size: 14px;
  background: rgba(255,255,255,0.84);
  color: #3f2a18;
  box-sizing: border-box;
}

.auth-card button {
  width: 100%;
  padding: 13px 14px;
  border: 1px solid #a47a51;
  border-radius: 999px;
  background: linear-gradient(140deg, #f2e1cc 0%, #e3c7a6 100%);
  color: #5d3f24;
  font-weight: 700;
  cursor: pointer;
  box-shadow: inset 0 -1px 0 rgba(100, 68, 38, 0.18);
}

.auth-card button:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.auth-tips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}

.auth-tips span {
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(255,255,255,0.72);
  border: 1px solid rgba(164, 122, 81, 0.28);
  color: #6b4c2e;
  font-size: 12px;
}

.auth-error {
  margin-top: 12px;
  color: #b91c1c;
  font-size: 13px;
  font-weight: 600;
}
</style>
