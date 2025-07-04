import { createApp } from 'vue'
import { createPinia } from "pinia";
import router from "./router";
import './style.css'
import { createGtag } from "vue-gtag";

import App from './App.vue'

const gtag = createGtag({
  tagId: `${import.meta.env.VITE_ANALYTICS_ID}`
})

const app = createApp(App);
const pinia = createPinia();
app.use(pinia);
app.use(router);
app.use(gtag)
app.mount('#app')
