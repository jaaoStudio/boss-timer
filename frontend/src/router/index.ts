import { createRouter, createWebHistory } from "vue-router";
import type { Router } from 'vue-router';

const router: Router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'RoomSelection',
      component: () => import('../views/RoomSelection.vue'),
    },
    {
      path: '/room/:roomId',
      name: 'BossTracker',
      component: () => import('../views/BossTracker.vue'),
      props: true,
    },
    {
      path: '/credits',
      name: 'Credits',
      component: () => import('../views/Credits.vue'),
    },
    {
      // Redirect to home if no other route matches
      path: '/:pathMatch(.*)*',
      redirect: '/',
    },
  ],
});

export default router;
