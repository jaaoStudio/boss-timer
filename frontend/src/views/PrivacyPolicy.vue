<template>
  <div class="max-w-4xl mx-auto p-4 sm:p-6 md:p-8">
    <h1 class="text-4xl font-bold text-white mb-6 border-b border-gray-700 pb-4">
      Legal Disclaimer
    </h1>
    <h2 class="text-2xl font-semibold text-teal-400 mb-4">隱私權政策 (Privacy Policy)</h2>
    <div class="text-gray-400 space-y-4">
      <p>非常歡迎您光臨「Boss Timer」(以下簡稱本網站)，為了讓您能夠安心的使用本網站的各項服務與資訊，特此向您說明本網站的隱私權保護政策，以保障您的權益，請您詳閱下列內容：</p>
      <h3 class="text-xl font-semibold text-teal-500 pt-2">一、隱私權保護政策的適用範圍</h3>
      <p>隱私權保護政策內容，包括本網站如何處理在您使用網站服務時收集到的個人識別資料。隱私權保護政策不適用於本網站以外的相關連結網站，也不適用於非本網站所委託或參與管理的人員。</p>
      <h3 class="text-xl font-semibold text-teal-500 pt-2">二、個人資料的蒐集、處理及利用方式</h3>
      <p>當您透過 Google 登入或參與本網站活動時，我們會請您提供必要的個人資料，並在該特定目的範圍內處理及利用您的個人資料。本網站蒐集的個人資料包括：</p>
      <ul class="list-disc list-inside pl-4">
        <li><strong>來自 Google 的公開資料：</strong> 您的姓名、電子郵件地址、以及頭像 URL。</li>
        <li><strong>您產生的資料：</strong> 您在應用程式中建立的房間資訊、Boss 計時紀錄等。</li>
      </ul>
      <p>這些資料僅供本網站於其內部、依照蒐集之目的進行處理和利用（例如用於身份驗證、個人化您的體驗、顯示您的使用者名稱與頭像），或為完成提供服務或履行合約義務之必要。除非取得您的同意、或依據相關法令規定，否則本網站不會將您的個人資料提供給第三方、或移作蒐集目的以外之使用。</p>
      <h3 class="text-xl font-semibold text-teal-500 pt-2">三、資料之保護</h3>
      <p>本網站主機均設有防火牆、防毒系統等相關的各項資訊安全設備及必要的安全防護措施，加以保護網站及您的個人資料。我們採取嚴格的保護措施，只由經過授權的人員才能接觸您的個人資料。</p>
      <h3 class="text-xl font-semibold text-teal-500 pt-2">四、網站對外的相關連結</h3>
      <p>本網站的網頁提供其他網站的網路連結。當您經由本網站所提供的連結，點選進入其他網站時，該連結網站不適用本網站的隱私權保護政策，您必須參考該連結網站中的隱私權保護政策。</p>
      <h3 class="text-xl font-semibold text-teal-500 pt-2">五、與第三人共用個人資料之政策</h3>
      <p>本網站絕不會提供、交換、出租或出售任何您的個人資料給其他個人、團體、私人企業或公務機關，但有法律依據或合約義務者，不在此限。</p>
      <h3 class="text-xl font-semibold text-teal-500 pt-2">六、Cookie 之使用</h3>
      <p>為了提供您最佳的服務，本網站會在您的電腦中放置並取用我們的 Cookie。若您不願接受 Cookie 的寫入，您可在您使用的瀏覽器功能項中設定隱私權等級為高，即可拒絕 Cookie 的寫入，但可能會導致網站某些功能無法正常執行。</p>
      <h3 class="text-xl font-semibold text-teal-500 pt-2">七、隱私權保護政策之修正</h3>
      <p>本網站隱私權保護政策將因應需求隨時進行修正，修正後的條款將更新於本網站上。</p>
      <h3 class="text-xl font-semibold text-teal-500 pt-2">八、聯絡我們</h3>
      <p>若您對於您的個人資料有任何疑問、或希望請求刪除，請透過電子郵件聯繫我們：<a href="mailto:boss-timer@jaao.tw" class="text-blue-400 hover:underline">boss-timer@jaao.tw</a>。</p>
    </div>

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
