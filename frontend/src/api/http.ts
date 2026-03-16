import axios from 'axios';

const defaultBaseURL = '/api/v1';
const baseURL = (import.meta.env.VITE_API_BASE || defaultBaseURL).trim().replace(/\/$/, '');

export const http = axios.create({
  baseURL,
  timeout: 15000,
  withCredentials: true
});

export const authApi = {
  status: () => http.get('/auth/session'),
  login: (token: string) => http.post('/auth/session', { token }),
  logout: () => http.delete('/auth/session')
};
