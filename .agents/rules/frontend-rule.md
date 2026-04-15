---
trigger: always_on
---

嚴格禁止在 Vue 模板中使用硬編碼的後備字串（Fallback strings）。任何可見文字的新增或修改，都必須使用 t('key')，並同步更新 zh.json 與 en.json。