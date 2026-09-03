# UX-flow rules — сокращение целевого пути пользователя

**Цель:** не плодить промежуточные экраны, не увеличивать число кликов до целевого
действия. Каждый дополнительный экран — это проигранная конверсия.

**Применяется к skills:** `executor-pro`, `executor-lite`, `qa-fix`, `qa-design-review`,
`plan-design-review`, `tech-spec-composer`, `change-plan-architect`, всех Frontend-related.

---

## R1. Auto-progression after action

**Правило.** После завершающего действия (submit, complete, save, confirm) система
**автоматически** ведёт пользователя на логически-следующий шаг. Промежуточные
экраны «успех + кнопка продолжить» — anti-pattern.

**Почему.** В TG-боте студ-флоу спроектирован как линейный chain: ответил → next
question. В web лишний клик «К следующему шагу» удваивает целевой путь без
информационной выгоды.

**Конкретно:**
- ✅ Inline-баннер «Правильно ✓» 1.2с → auto `router.push(next)`.
- ❌ Полноэкранный success page → user manually clicks «Continue».
- ❌ Redirect на родительскую страницу (course home) когда известен `next-item`.

**Исключение:** разрушительные действия (logout, delete, payment) — confirm-screen
обязателен. Учебные действия — нет.

**Реализация:**
```tsx
// performSubmit (учебная задача, correct)
setLastResult(r);
const next = await refetchNext();
const target = computeTarget(next.data);
setTimeout(() => router.push(target), 1200); // auto
```

---

## R2. Click-budget per task

**Правило.** Максимум **1 клик** между действием и следующим целевым экраном.
2 и более — review/refactor.

**Аудит:** прежде чем добавлять CTA-button «Продолжить» / «Далее» / «Открыть» —
спросить: «Можно ли сделать это автоматически?»

**Pattern violations:**
- «Прошёл материал» → /courses/PY (видит ContinueWidget) → клик «Вернуться к
  материалу» → next material. **3 клика вместо 1.**
- Login → /me (видит баннер «Welcome») → клик «К курсам» → /courses. **2 вместо 1.**

**Fix:** complete material → router.push прямо на next material/task; login → router.push
на /courses (или сохранённый redirect).

---

## R3. ContinueWidget = entry point, не пост-action transition

**Правило.** ContinueWidget («Продолжить с прерванного шага») показывается только
при **возврате** в систему — не как промежуточный шаг после завершённого действия.

**Detection.** Если after-action redirect ведёт на главную курса с показом
ContinueWidget — это R1 violation.

---

## R4. Forms: не вызывать parent setState из child callback synchronously

**Правило.** В контролируемых формах child компонент НЕ должен вызывать parent
setState синхронно во время render-фазы. React 18+ выкидывает warning «Cannot
update a component while rendering a different one».

**Pattern (правильный):**
```tsx
// child component
function toggle(id) {
  setSelected(prev => ...);          // child setState
  queueMicrotask(() => onChange?.(...)); // parent setState — отложен
}
```

**Anti-pattern (любая из этих):**
```tsx
// 1. setState внутри updater
setSelected(prev => {
  onChange?.(...);  // ❌ parent setState во время child updater
  return next;
});

// 2. useEffect с onChange в deps
useEffect(() => {
  onChange?.(...);
}, [selected, onChange]); // ❌ inline-arrow onChange = infinite loop
```

**Когда обязательно использовать `queueMicrotask`:**
- Parent передаёт inline-arrow в onChange (нет useCallback стабилизации)
- Child обрабатывает событие пользователя (click, change, input)
- Child вызывает onChange с derived data из своего state

**Альтернативы:**
- `useCallback` в parent — стабилизирует identity, но не решает «setState during
  render» если parent setState синхронный.
- `useDeferredValue` / `startTransition` — overkill для типового onChange.

---

## R5. Loading states вместо blocking modals

**Правило.** Длинные операции (≥300ms) показываются inline-spinner / skeleton, не
модальным окном «Loading…». Модал останавливает workflow; inline — нет.

**Исключение:** действие должно быть атомарным (file upload, payment) — модал-progress
с cancel-кнопкой OK.

---

## R6. Empty states ≠ error states

**Правило.** Пустой список («У вас нет курсов», «Нет уведомлений») — показываем
warm message + primary CTA на действие, чтобы заполнить пустоту. Не показываем
как «Error: no data».

**Шаблон:**
```tsx
{list.length === 0 ? (
  <div data-testid="empty">
    <p>{messageWhy}</p>     {/* «Здесь появятся ваши попытки…» */}
    <Link href={ctaPath}>{ctaLabel} →</Link>  {/* «К моим курсам» */}
  </div>
) : ...}
```

---

## R7. Auto-resolve over manual choice

**Правило.** Когда системе известен default/next → выполнить автоматически. Не
просить пользователя выбирать «Куда вы хотите перейти?» если ответ очевиден из
контекста.

**Examples:**
- `/me/continue` → auto-resolve next-item → `router.replace(target)`. Без UI-выбора.
- After-correct task → next via `useLearningLoop` → `router.push`. Без CTA.
- After complete material → next material → `router.push`. Без курса-главной.

---

## R8. Single source of truth для navigation

**Правило.** Если у системы есть `next-item` API (LMS `/learning/next-item`) —
он — единственный источник для after-action navigation. Не дублировать через
`useLastPosition`, `useCoursesWithProgress`, manually computed paths.

---

## Audit-checklist (применяется при review UX)

Перед merge'ем UI-changes / новой страницы — пройти:

- [ ] **R1.** Каждое action завершается auto-progression на logical next? Если нет — есть ли причина (R1 exception)?
- [ ] **R2.** Click-budget: от старта до целевого экрана ≤ 1 клик после действия?
- [ ] **R3.** ContinueWidget показывается только entry-point flow?
- [ ] **R4.** Контролируемые формы используют `queueMicrotask` для parent setState?
- [ ] **R5.** Loading states inline, не блокируют workflow?
- [ ] **R6.** Empty states warm + actionable?
- [ ] **R7.** Default/next auto-resolved где возможно?
- [ ] **R8.** Navigation source-of-truth единый?

Если найдено ≥1 нарушение — block-merge до исправления.

---

## Telemetry для measurment

**Метрика «pages-per-action»**: после X (submit, complete, login) — сколько pages
видит user до целевого state? Цель — 1 или 2 (включая текущий).

**Метрика «clicks-per-task»**: от homepage до finished-task — сколько кликов?
Бенчмарк (типовой ученик решает 1 задачу): 3-4 клика максимум.

---

**Конец ux-flow-rules.md.**

Updated: 2026-05-02 (Y-5.2 SPW: интегрирован после feedback оператора «не плодить лишние экраны»).
