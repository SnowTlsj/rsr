import axios from 'axios';

const baseURL = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api/v1';

export const http = axios.create({
  baseURL,
  timeout: 15000
});
