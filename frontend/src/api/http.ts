import axios from 'axios';

const defaultBaseURL = '/api/v1';
const baseURL = (import.meta.env.VITE_API_BASE || defaultBaseURL).trim().replace(/\/$/, '');

export const http = axios.create({
  baseURL,
  timeout: 15000,
  withCredentials: true
});

http.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error?.response?.status;
    if (status === 401 || status === 403) {
      window.dispatchEvent(new CustomEvent('rsr-auth-expired'));
    }
    return Promise.reject(error);
  }
);

export const authApi = {
  status: () => http.get('/auth/session'),
  login: (token: string) => http.post('/auth/session', { token }),
  logout: () => http.delete('/auth/session')
};
