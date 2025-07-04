import { createApp } from 'vue'
import { createPinia } from "pinia";
import router from "./router";
import './style.css'
import { createGtm } from '@gtm-support/vue-gtm'
import apiService from '@/services/apiService.js';

import App from './App.vue'

// Initialize authentication
(async () => {
  await apiService.initAuth();
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
