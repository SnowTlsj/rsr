import { computed, ref, watch } from 'vue';

export type ThemeName = 'paper' | 'landscape' | 'pattern';

const THEME_STORAGE_KEY = 'monitor_theme';
const OPACITY_STORAGE_KEY = 'monitor_theme_opacity';

const themeImageMap: Record<ThemeName, string> = {
  paper: "url('/themes/antique-paper.jpg')",
  landscape: "url('/themes/landscape-ink.jpg')",
  pattern: "url('/themes/cistanche-pattern.webp')"
};

export function useThemeBackground() {
  const bgOpacity = ref(0.38);
  const activeTheme = ref<ThemeName>('paper');

  const containerStyle = computed(() => ({
    '--antique-opacity': `${bgOpacity.value}`
  }));

  const backgroundLayerStyle = computed(() => ({
    opacity: `${bgOpacity.value}`,
    backgroundImage: [
      themeImageMap[activeTheme.value],
      'radial-gradient(circle at 15% 18%, rgba(133, 94, 66, 0.28) 0, rgba(133, 94, 66, 0.05) 28%, transparent 45%)',
      'radial-gradient(circle at 82% 22%, rgba(150, 105, 74, 0.22) 0, rgba(150, 105, 74, 0.04) 30%, transparent 50%)',
      'radial-gradient(circle at 24% 84%, rgba(123, 84, 58, 0.2) 0, rgba(123, 84, 58, 0.03) 25%, transparent 45%)',
      'linear-gradient(135deg, rgba(248, 238, 220, 0.72) 0%, rgba(241, 227, 200, 0.38) 55%, rgba(232, 214, 184, 0.32) 100%)'
    ].join(', ')
  }));

  const hydrate = () => {
    const savedTheme = localStorage.getItem(THEME_STORAGE_KEY);
    if (savedTheme === 'paper' || savedTheme === 'landscape' || savedTheme === 'pattern') {
      activeTheme.value = savedTheme;
    }

    const savedOpacity = localStorage.getItem(OPACITY_STORAGE_KEY);
    if (savedOpacity !== null) {
      const parsed = Number(savedOpacity);
      if (!Number.isNaN(parsed)) {
        bgOpacity.value = Math.max(0, Math.min(1, parsed));
      }
    }
  };

  watch(activeTheme, (value) => {
    localStorage.setItem(THEME_STORAGE_KEY, value);
  });

  watch(bgOpacity, (value) => {
    localStorage.setItem(OPACITY_STORAGE_KEY, String(value));
  });

  return {
    activeTheme,
    bgOpacity,
    containerStyle,
    backgroundLayerStyle,
    hydrate
  };
}
