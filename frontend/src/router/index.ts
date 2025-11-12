import { createRouter, createWebHistory } from "vue-router";
import type { Router } from 'vue-router';
import { useUserStore } from '@/stores/userStore'; // 引入 userStore

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
      path: '/legal',
      name: 'Legal',
      component: () => import('../views/LegalDisclaimer.vue'),
    },
    {
      path: '/privacy-policy',
      name: 'Privacy',
      component: () => import('../views/PrivacyPolicy.vue'),
    },
    {
      path: '/maintenance',
      name: 'Maintenance',
      component: () => import('../views/MaintenancePage.vue'),
    },
    {
      path: '/error',
      name: 'Error',
      component: () => import('../views/ErrorPage500.vue'),
    },
    {
      path: '/admin/maintenance',
      name: 'MaintenanceAdmin',
      component: () => import('../views/MaintenanceAdmin.vue'),
      meta: { requiresAuth: true, requiresAdmin: true } // 需要認證和管理員權限
    },
    {
      // Redirect to home if no other route matches
      path: '/:pathMatch(.*)*',
      redirect: '/',
    },
  ],
});

router.beforeEach(async (to, from, next) => {
  const userStore = useUserStore();
  await userStore.initializeAuth(); // 確保用戶認證狀態已載入

  if (to.meta.requiresAuth && !userStore.isLoggedIn) {
    next({ name: 'RoomSelection' }); // 未登入，導向登入頁
  } else if (to.meta.requiresAdmin && !userStore.isAdmin) {
    next({ name: 'RoomSelection' }); // 非管理員，導向首頁
  } else {
    next();
  }
});

export default router;
