import { createApp } from 'vue'
import { createPinia } from "pinia";
import router from "./router";
import './style.css';
import { createGtm } from '@gtm-support/vue-gtm';
import ApiService from '@/services/apiService.ts';
import 'element-plus/theme-chalk/dark/css-vars.css'

import App from './App.vue'

// Initialize authentication
(async () => {
  await ApiService.initAuth();
})();

const app = createApp(App);
const pinia = createPinia();
app.use(pinia);
app.use(router);
app.use(createGtm({
  id: `${import.meta.env.VITE_GTM_ID}`,
  defer: false,
  compatibility: false,
  enabled: true,
  debug: false,
  loadScript: true,
  vueRouter: router,
  trackOnNextTick: false,
}))
app.mount('#app')
