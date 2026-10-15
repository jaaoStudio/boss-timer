import { QueryClient } from '@tanstack/vue-query'

// 由 main.ts 以 VueQueryPlugin 掛載：掛載後才會在切回分頁時重新查詢
export const queryClient = new QueryClient()
