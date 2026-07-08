# Boss Timer 專案指引

## 開發規範 (Skills)

@.agent/skills/frontend/SKILL.md
@.agent/skills/frontend-components/SKILL.md
@.agent/skills/backend/SKILL.md
@.agent/skills/backend-api/SKILL.md
@.agent/skills/backend-database/SKILL.md
@.agent/skills/backend-celery-webhook/SKILL.md
@.agent/skills/infrastructure/SKILL.md

## 強制規則

嚴格禁止在 Vue 模板中使用硬編碼的後備字串（Fallback strings）。任何可見文字的新增或修改，都必須使用 t('key')，並同步更新 zh.json 與 en.json。

## Agent skills

### Issue tracker

Issues live in GitHub Issues (`github.com/jaaoStudio/boss-timer`). See `docs/agents/issue-tracker.md`.

### Triage labels

Five canonical labels using default names. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context repo — one `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.