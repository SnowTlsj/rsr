export const isAuthError = (error: unknown): boolean => {
  const status = (error as any)?.response?.status;
  return status === 401 || status === 403;
};

export const extractErrorMessage = (error: unknown, fallback: string): string => {
  const detail = (error as any)?.response?.data?.detail;
  if (typeof detail === 'string' && detail.trim()) {
    return detail.trim();
  }
  return fallback;
};

