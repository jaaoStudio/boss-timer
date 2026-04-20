<template>
  <div v-if="isVisible" class="ad-banner-wrapper flex flex-col items-center">
    <ins
      ref="adRef"
      class="adsbygoogle"
      style="display:block"
      :data-ad-client="adClient"
      :data-ad-slot="adSlot"
      data-ad-format="vertical"
      data-full-width-responsive="false"
    ></ins>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'

defineProps<{
  adSlot: string
}>()

const adClient = 'ca-pub-8035851123300328'
const adRef = ref<HTMLElement | null>(null)
// 只在螢幕夠寬時顯示（側邊欄需要足夠空間）
const isVisible = ref(window.innerWidth >= 1280)

onMounted(() => {
  if (!isVisible.value) return
  try {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    ;(window as any).adsbygoogle = (window as any).adsbygoogle || []
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    ;(window as any).adsbygoogle.push({})
  } catch (e) {
    console.error('AdSense error:', e)
  }
})
</script>