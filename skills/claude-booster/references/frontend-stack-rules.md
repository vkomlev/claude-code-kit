# Frontend Stack Rules (Next.js 16 + TypeScript + React)

Единые правила для frontend-проектов на Next.js 16 App Router + TS + React 19. Подключается из `executor-lite`, `executor-pro`, `techlead-code-reviewer`, `qa-fix`, `tech-spec-composer` (для frontend ТЗ).

Источник дефектов: `~/projects/spw\` чаты 27-28.04.2026 (proxy.ts middleware был сломан для TG App, type assertions без validation, useEffect+mutate вместо Server Actions, hotfix без review).

## 1. TypeScript: запрет устаревших приёмов

### Запрещены
- `any` без явного `// eslint-disable-next-line @typescript-eslint/no-explicit-any` + комментария «почему».
- Type assertion `as SomeType` для **внешних** данных (HTTP response, JSON.parse, localStorage, postMessage). Используется только для **внутренних** уже валидированных значений.
- `var` (используем `const` по умолчанию, `let` только если переприсваивается).
- `// @ts-ignore` (только `// @ts-expect-error` с комментарием почему).
- `Function`, `Object`, `{}` в типах (использовать конкретные сигнатуры).

### Обязательно
- Strict mode в `tsconfig.json`: `"strict": true`, `"noUncheckedIndexedAccess": true`.
- Runtime-валидация (`Zod` / `valibot`) для всех данных, приходящих извне: HTTP responses, env, query params, postMessage, localStorage/CloudStorage.
- Generic-типизация HTTP-клиентов: `client.post<Req, Res>(url, body)` с обоими параметрами.
- Discriminated unions для состояний: `{ status: 'loading' } | { status: 'ok'; data: T } | { status: 'error'; error: string }`.

## 2. React 19: запрет устаревших приёмов

### Запрещены
- Class components в новом коде.
- `useEffect` для:
  - синхронного чтения query/path → используется `useSearchParams`/`usePathname` напрямую.
  - выполнения мутации при появлении данных → используется Server Action или `onClick`/`onSubmit`.
  - синхронизации производного state → вычисляется во время рендера.
- `useState` для derived values, которые можно вычислить из props.
- **`useState`, засеянный server-пропом/`initialX`, для состояния, отражённого в URL**
  (фильтр `?type=`, таб `?tab=`, выбор). При клиентской навигации на ту же страницу со
  сменой query компонент **не перемонтируется** → useState держит СТАРОЕ значение, UI
  рассинхронится с URL и подсветкой навигации. Правильно: состояние выводить из
  `useSearchParams` (URL = источник истины), кнопки-переключатели меняют URL (`router.push`),
  список/контент читает URL. `initialType`-проп из server-компонента — антипаттерн для этого
  класса. (Источник: session 2026-07-19 — тип-фильтр help-requests показывал не тот бакет
  при переходах между `?type=`.)
- Prop drilling глубже 2 уровней без обоснования (использовать context или Zustand).
- Manual DOM mutations (`document.querySelector` + `.style`, `.innerHTML`) — только через ref или React state.

### useEffect: anti-pattern примеры

❌ **Плохо** — обход правила через eslint-disable:
```tsx
"use client";
useEffect(() => {
  tgInit();  // мутация при монтировании
}, []);  // eslint-disable-next-line react-hooks/exhaustive-deps
```
Проблемы: пустой dep array + комментарий-обход = скрытое нарушение. Если функция не стабильна, эффект не перевыполнится.

✅ **Хорошо** — Server Action или явная инициализация:
```tsx
// Вариант 1: Server Action на первый рендер
export default async function Page() {
  const initialData = await fetchInitial();  // на сервере, без эффекта
  return <Client initialData={initialData} />;
}
// Вариант 2: явный onClick, не эффект
<Button onClick={() => tgInit()}>Open in Telegram</Button>
```

Если `useEffect` действительно нужен (например, подписка на browser API): обязателен **комментарий с обоснованием** (не `eslint-disable`), стабильные зависимости через `useCallback`/`useMemo`, и cleanup-функция.

### Обязательно
- Server Components по умолчанию; `"use client"` только когда нужен event handler / hooks / browser API.
- Server Actions для мутаций (`'use server'` + form action), если нет требования обходить Next.js layer.
- `useTransition` для не-блокирующих мутаций; `useOptimistic` для оптимистичных UI-обновлений.
- `Suspense` boundary вокруг компонентов, использующих `useSearchParams`/`use(promise)`.
- Error boundary (`error.tsx`) и loading state (`loading.tsx`) на каждом значимом route segment.

## 3. Next.js 16 App Router

### Запрещены
- Pages Router (`pages/*`) в новом коде.
- `getServerSideProps`, `getStaticProps` (это Pages Router).
- Smelly client/server boundary: компонент с `"use client"`, импортирующий server-only утилиту (или наоборот server-component, использующий browser API).
- `fetch` в Client Component без `AbortController` для long-running запросов.

### Обязательно
- `app/` как единственная директория роутов.
- `metadata` или `generateMetadata` для каждого route segment.
- `cache: 'no-store'` или `next: { revalidate }` явно — никогда не полагаться на дефолт.
- Middleware (`middleware.ts`) — **минимальный**, только маршрутизация/редирект; **не** auth-логика, если приложение поддерживает несколько контекстов (web cookies, TG App Bearer, WP-embed iframe).
- `next.config.ts` с `experimental.typedRoutes: true` (если поддерживается версией).

## 4. Multi-Context Auth Awareness

Если приложение поддерживает несколько контекстов запуска (browser web, Telegram Mini App, WP-embed iframe, native shell):

- **Middleware не должен** проверять cookie-based session, если хотя бы один контекст не использует cookies.
- Auth-стратегия выбирается на клиенте по контексту: cookies (web), Bearer + CloudStorage (TG App), postMessage-bridge (iframe).
- `ApiClient` обязан иметь `onAuthRequired` callback, который контекст-специфичен.
- Тесты обязаны покрывать каждый контекст отдельно.

См. инцидент SPW 27.04 (proxy.ts middleware ломал auth в TG App).

## 5. Запрос данных и состояние

- TanStack Query (React Query) для server state — кэширование, инвалидация, оптимистичные обновления.
- Zustand или Context для client-side state (UI, formdata before submit). Запрещён Redux в новом коде без явного обоснования.
- `fetch` в Server Component → нативный `fetch` Next.js (с автоматическим dedupe).
- `fetch` в Client Component → через `ApiClient` слой, с retries, timeouts, AbortSignal.

## 6. Тестирование

- **Vitest** для unit/integration; не Jest в новом коде. Конфиг — `vitest.config.ts`.
- **Playwright** для E2E. `@testing-library/react` для component tests.
- Обязательно: тест на каждый Server Action, обработку ошибок API, контекст-специфичный auth flow.
- Запрет: snapshot tests на сложные DOM-структуры (хрупкие), enzyme (deprecated).
- Mock внешних API через MSW (Mock Service Worker), не через `vi.mock` для fetch напрямую.

## 7. Стиль и инструментарий

- **Package manager**: `pnpm` по умолчанию; `npm`/`yarn` запрещены в SPW-проектах.
- **ESLint**: flat config (`eslint.config.mjs`), не `.eslintrc.*`. `eslint-config-next` обязателен.
- **Prettier** как formatter; не использовать `eslint --fix` для форматирования.
- **Tailwind v4** через `@tailwindcss/postcss`; CSS-in-JS не одобрен в новом коде.

## 8. Безопасность

- Все user inputs валидируются Zod на клиенте (UX) **и** на server (security).
- `dangerouslySetInnerHTML` запрещён без `DOMPurify.sanitize(...)` и явного rationale.
- Cookies: `httpOnly: true`, `secure: true` (prod), `sameSite: 'lax'`/`'strict'`.
- env: `NEXT_PUBLIC_*` только для безопасных публичных значений; секреты — без префикса.
- Никаких credentials/tokens в logs, console.log, error messages.

## 9. Перформанс

- `next/image` для всех изображений, `next/font` для шрифтов.
- Dynamic imports (`next/dynamic`) для тяжёлых клиентских компонентов.
- `React.memo` / `useMemo` / `useCallback` — **только** при доказанном перф-проседании. Преждевременная мемоизация запрещена.

## 10. Контрольный чеклист перед commit

- [ ] `pnpm lint` зелёный
- [ ] `pnpm typecheck` (`tsc --noEmit`) зелёный
- [ ] `pnpm test` (vitest) зелёный
- [ ] Нет `any` без обоснования
- [ ] Нет `as Type` для внешних данных без Zod-validation
- [ ] Server Components по умолчанию; `"use client"` обоснован
- [ ] `useEffect` отсутствует или обоснован комментарием (не для мутаций / не для derived state)
- [ ] Если изменён middleware/auth flow → review-gate **обязателен** (см. п.11)
- [ ] Multi-context auth: проверены все контексты (web/TG/embed)

## 11. Обязательные триггеры review-gate

Любое из ниже — `review-gate` **обязателен** перед push:

1. Изменения в `middleware.ts`, `proxy.ts`, `app/api/auth/*`, `lib/auth/*`.
2. Изменения, затрагивающие client/server component boundary (перевод компонента из server в client или наоборот).
3. Изменения LMS contract (endpoint URL, request/response struct).
4. Type assertions добавлены вместо type guards.
5. Любой fetch-запрос изменён по таймаутам, retries, AbortController, headers (auth).
6. Hotfix во время operator-driven smoke — **не исключение**, а ровно тот случай, когда review-gate критичен.

См. инцидент SPW 27.04: дважды коммит без review нарушил prevention action из ERRORS 2026-04-27.

## 12. Multi-Context Smoke Matrix

Для multi-context приложения (web + Telegram App + WP-embed iframe) **любой** PR с `fix(auth)`, изменением middleware/proxy.ts, или изменением auth-стратегии **обязан** в одном PR содержать smoke-evidence по **всем трём контекстам**:

| Контекст | Smoke-инструмент | Что проверяется |
|----------|------------------|-----------------|
| web | Playwright E2E | cookie session, magic-link login, /me запрос |
| Telegram App | Playwright + mock `window.Telegram.WebApp` | Bearer auth, CloudStorage, MainButton |
| WP-embed | Playwright iframe + postMessage mock | postMessage-bridge, iframe cookies (3rd-party) |

Несинхронизированные фиксы (изменили `proxy.ts` для web, не проверили TG App) — основная причина инцидента 27.04. `review-gate` обязан считать отсутствие smoke хотя бы одного контекста — блокирующий FAIL для auth-related PR.

## 13. Playwright Selector Stability

Селекторы в E2E-тестах — публичный контракт UI. При апгрейде UI-либ (base-ui, shadcn, headlessui) `getByRole` может перестать работать (роли меняются между версиями).

Правила:
- Предпочитать `getByTestId` для критичного flow (auth, payment, submit) — стабилен через апгрейды.
- `getByText` для пользовательских сообщений (lazy-binding к UI).
- `getByRole` только для нативных HTML-элементов (`button`, `link`, `heading`) — не для кастомных компонентов.
- Любая массовая замена селекторов в E2E (≥5 файлов) требует review-gate с явным обоснованием в коммите (какая либа обновилась).

Источник: SPW 28.04 — апгрейд base-ui v4 сломал `getByRole(heading)` в `CardTitle`, потребовался migration-pass.

## 14. Conditional UI Hide/Show — обе ветки

При условиях скрытия/показа форм submit/retry — обязательно покрывать **оба сценария**:

❌ **Плохо** (Y-6 Stage 6 bug):
```tsx
const showForm = allowSubmit && !lastResult;
// `!lastResult` ловит ЛЮБОЙ установленный lastResult, включая wrong-answer
// → после wrong submit форма скрывается → студент не может retry
```

✅ **Хорошо** — сужение до success-ветки:
```tsx
const showForm = allowSubmit && lastResult?.is_correct !== true;
// Скрывается только при успехе (где идёт auto-redirect)
// Wrong-answer оставляет форму видимой для retry
```

**Правила:**
- Любое условие скрытия формы submit обязано иметь **regression-тест**: `wrong submit → form visible → second submit`.
- `review-gate` измерение «корректность» проверяет «можно ли продолжить после wrong submit, blocked_limit, network error».
- Код-комментарий рядом с защитной проверкой **объясняет ОБА сценария** (happy + unhappy), не один.
- При наличии `effectivelyBlocked` (server-side limit) — учитывать regex-detect: `blocked || /лимит|limit|exceed/i.test(submitErr)`.

Источник: SPW ERRORS 2026-05-04 — Y-6 Stage 6 form-hide bug.

## 14. UX-flow rules (Y-5.2 SPW addition)

При любом UI-изменении прочитать `ux-flow-rules.md` и пройти audit-checklist (R1–R8). Ключевые принципы:

- **R1 (auto-progression):** После завершающего действия (submit, complete) — auto `router.push(next)` через 1-1.5с с inline-баннером. Не показывать промежуточный «success page».
- **R2 (click-budget):** ≤1 клик между действием и целевым следующим экраном.
- **R4 (forms parent setState):** В контролируемых формах parent setState из child onChange — через `queueMicrotask`, не синхронно (иначе React 18+ выкинет «Cannot update component while rendering»).
- **R7 (auto-resolve):** Default/next auto-resolved где возможно (`useLearningLoop` → `router.push`, без UI-выбора пользователя).

**Anti-pattern (видели в Y-5.2):**
```tsx
// ❌ ContinueWidget на /courses/[uid] показывался после complete material —
// promotion exit, лишний клик. R1 violation.
router.push(`/courses/${uid}`); // курс показал «Вернуться к материалу»

// ✅ R1-compliant
const next = await refetchNext();
router.push(`/courses/${uid}/material/${next.material_id}`);
```

Источник: Y-5.2 SPW (2026-05-02) — оператор сообщил «не плодить лишние экраны».

## 15. Проверочный пайплайн перед merge frontend changes

При любом merge UI-changes:
1. `pnpm type-check` PASS (0 errors)
2. `pnpm lint` PASS (0 errors, 0 react-hooks warnings)
3. `pnpm test` — без regressions
4. `pnpm test:e2e` — без regressions
5. `pnpm build` — без warnings
6. **`ux-flow-rules.md` audit checklist** — для UI-changes пройти R1–R8

Любой violation #6 — block-merge до фикса.
