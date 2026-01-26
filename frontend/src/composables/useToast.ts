import { ref } from 'vue';

interface ToastOptions {
  message: string;
  type?: 'success' | 'error' | 'warning' | 'info';
  duration?: number;
}

const toastMessage = ref('');
const toastType = ref<'success' | 'error' | 'warning' | 'info'>('info');
const toastVisible = ref(false);

let timer: number | null = null;

export function useToast() {
  const show = (options: ToastOptions) => {
    toastMessage.value = options.message;
    toastType.value = options.type || 'info';
    toastVisible.value = true;

    if (timer) clearTimeout(timer);
    timer = window.setTimeout(() => {
      toastVisible.value = false;
    }, options.duration || 3000);
  };

  const success = (message: string, duration?: number) => {
    show({ message, type: 'success', duration });
  };

  const error = (message: string, duration?: number) => {
    show({ message, type: 'error', duration });
  };

  const warning = (message: string, duration?: number) => {
    show({ message, type: 'warning', duration });
  };

  const info = (message: string, duration?: number) => {
    show({ message, type: 'info', duration });
  };

  return {
    toastMessage,
    toastType,
    toastVisible,
    show,
    success,
    error,
    warning,
    info,
  };
}

