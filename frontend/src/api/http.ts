import axios from 'axios';

const defaultBaseURL = '/api/v1';
const baseURL = (import.meta.env.VITE_API_BASE || defaultBaseURL).trim().replace(/\/$/, '');
const authToken = (import.meta.env.VITE_AUTH_TOKEN || '').trim();

export const getAuthToken = () => authToken;

export const http = axios.create({
  baseURL,
  timeout: 15000
});

http.interceptors.request.use((config) => {
  if (authToken) {
    if (config.headers && typeof (config.headers as any).set === 'function') {
      if (!(config.headers as any).has('Authorization')) {
        (config.headers as any).set('Authorization', `Bearer ${authToken}`);
      }
    } else {
      config.headers = config.headers || {};
      if (!(config.headers as any).Authorization) {
        (config.headers as any).Authorization = `Bearer ${authToken}`;
      }
    }
  }
  return config;
});
