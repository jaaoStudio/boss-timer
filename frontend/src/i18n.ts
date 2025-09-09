import { createI18n } from 'vue-i18n';
import en from './locales/en.json';
import zh from './locales/zh.json';

const i18n = createI18n({
  legacy: false, // Must be set to false to use Composition API
  locale: localStorage.getItem('language') || 'zh', // Default to Chinese, or load from localStorage
  fallbackLocale: 'en', // Fallback to English if translation is missing
  messages: {
    en,
    zh
  }
});

export default i18n;
