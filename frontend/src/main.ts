import { createApp } from 'vue'
import { createPinia } from "pinia";
import router from "./router";
import './style.css';
import { createGtm } from '@gtm-support/vue-gtm';
import clarity from '@microsoft/clarity';
import 'element-plus/theme-chalk/dark/css-vars.css'
import vue3GoogleLogin from 'vue3-google-login'
import App from './App.vue'
import i18n from './i18n';

const app = createApp(App);
const pinia = createPinia();
app.use(pinia);
app.use(router);
app.use(i18n);

app.use(vue3GoogleLogin, {
  clientId: `${import.meta.env.VITE_GOOGLE_CLIENT_ID}`,
})

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

// Microsoft Clarity
const clarityId = import.meta.env.VITE_CLARITY_ID;
if (clarityId) {
  clarity.init(clarityId);
}

app.mount('#app')
