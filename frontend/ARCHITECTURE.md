# Frontend architecture

The frontend uses Next.js App Router, React, strict TypeScript, and Tailwind CSS. Route files in `app/` stay thin where a feature has substantial client behavior; those routes render screens from `features/`.

## Module boundaries

- `app/`: routes, route layouts, metadata, and route-only composition.
- `features/`: workflows and feature-specific UI. A feature owns its data loading, mutations, and domain-specific components.
- `components/ui/`: reusable, domain-neutral UI primitives and shared style contracts.
- `components/`: reusable application components that know about application models, such as book/chapter filters.
- `lib/`: API transport, shared domain types, caching, and pure utilities. `lib/api.ts` is the stable public facade.
- `tests/`: Playwright regression coverage for critical user flows.

Dependencies should point inward: routes may use features and components; features may use components and `lib`; `components/ui` must not import from a feature.

## Shared UI

Import reusable primitives from `@/components/ui`:

- `Badge`: compact status labels with the existing neutral, green, amber, and blue tones.
- `Modal`: accessible dialog shell with backdrop dismissal, Escape dismissal, focus containment, and focus restoration.
- `LoadingState`, `ErrorState`, and `EmptyState`: semantic wrappers for existing feature-specific messages and skeleton layouts. Callers supply the established classes and loading content.
- `inputClass`: the standard management form-control style.
- `primaryButton` and `secondaryButton`: established action styles, usable on buttons and links.

`ManageHeader` remains in `features/management` because its breadcrumb and destination are specific to that workflow.

## Stateful feature screens

Stateful screens remain the orchestration boundary for lifecycle, requests, and mutations. Presentation with a focused responsibility belongs beside the screen in its feature directory. For example, the compare-books container owns selection, fetching, sorting, optimistic star updates, and drag state; `CompareItemCell` and `CompareViewSettingsPanel` own their respective rendering and local panel interaction. Shared feature contracts are in `compareTypes.ts`.

Avoid copying server data into multiple synchronized state objects. Derive filtered, grouped, and sorted views with `useMemo` when the computation is meaningful, and keep request cancellation guards in the component that owns the request lifecycle.

## API organization

Consumers import from `@/lib/api`, which preserves a single stable interface. Its implementation is separated into:

- `lib/api/types.ts`: backend response and domain contracts only.
- `lib/api/transport.ts`: base URL, request timeout, headers, response parsing, and normalized `ApiError` behavior.
- `lib/api/cache.ts`: GET deduplication, lookup caching, freshness, generation checks, and invalidation notifications.

Feature-specific endpoint wrappers may live inside their feature (as practice already does). Do not bypass the facade for general application requests, change cache keys, or add a second request/caching mechanism.

When adding UI, first reuse an existing primitive. Add a new primitive only when the same visual and behavioral contract is needed by multiple features. Keep domain data fetching and business rules out of `components/ui`, and preserve values in `tailwind.config.ts` instead of introducing one-off color constants.

## Verification

Run from `frontend/`:

```sh
npm run lint
npm run typecheck
NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run build
```

Playwright expects the frontend at port 3100 and its isolated backend at port 8100; see `playwright.config.ts` and `tests/stabilization.spec.ts`.
