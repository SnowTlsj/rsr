import { defineStore } from 'pinia';
import { authApi } from '@/api/http';

export const useAuthStore = defineStore('auth', {
  state: () => ({
    authenticated: false,
    checking: true,
    submitting: false,
    error: ''
  }),
  actions: {
    async checkSession() {
      this.checking = true;
      this.error = '';
      try {
        const response = await authApi.status();
        this.authenticated = !!response.data?.authenticated;
      } catch {
        this.authenticated = false;
      } finally {
        this.checking = false;
      }
    },
    async login(token: string) {
      this.submitting = true;
      this.error = '';
      try {
        await authApi.login(token);
        this.authenticated = true;
      } catch {
        this.authenticated = false;
        this.error = '管理会话验证失败，请检查输入后重试';
      } finally {
        this.submitting = false;
      }
    },
    async logout() {
      try {
        await authApi.logout();
      } finally {
        this.authenticated = false;
      }
    }
  }
});
