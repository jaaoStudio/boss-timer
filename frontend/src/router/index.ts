import { createRouter, createWebHistory } from "vue-router";
import type { RouteLocationNormalized, Router } from 'vue-router';
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
      path: '/guide',
      name: 'Guide',
      component: () => import('../views/UserGuide.vue'),
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

// 目前的登入狀態能否停在這個頁面：需要登入的頁面要已登入，管理員頁面要是管理員
export function canAccess(route: Pick<RouteLocationNormalized, 'meta'>): boolean {
  const userStore = useUserStore();
  if (route.meta.requiresAuth && !userStore.isLoggedIn) return false;
  if (route.meta.requiresAdmin && !userStore.isAdmin) return false;
  return true;
}

router.beforeEach(async (to, _from, next) => {
  const userStore = useUserStore();
  await userStore.initializeAuth(); // 確保用戶認證狀態已載入
  if (canAccess(to)) next();
  else next({ name: 'RoomSelection' });
});

export default router;
