<template>
  <div class="max-w-4xl mx-auto p-4 sm:p-6 md:p-8">
      <h1 class="text-4xl font-bold text-white mb-6 border-b border-gray-700 pb-4">
        Legal Disclaimer
      </h1>
    <h2 class="text-2xl font-semibold text-teal-400 mb-4">法律免責聲明 (Legal Disclaimer)</h2>
    <p class="text-gray-400">
      本軟體依「現況」提供，不含任何明示或暗示的保證，包括但不限於可銷售性、特定用途適用性及未侵權的保證。在任何情況下，作者或版權持有人均不對任何因本軟體、使用本軟體或與本軟體相關的其他交易而產生之任何索賠、損害或其他責任負責，無論是因合約、侵權行為或其他原因而引起。本服務提供的資料僅供參考，不應視為專業建議。
    </p>
          <div class="mt-12 text-center text-gray-500">
        <router-link to="/" class="hover:text-gray-300 underline">Back to Home</router-link>
      </div>
  </div>
</template>
<script setup>
import { onMounted } from 'vue'

onMounted(() => {
  window.scrollTo({
    top: 0,
    behavior: 'smooth' // 平滑滾動
  })
})

</script>
