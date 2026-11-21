# Frontend architecture

The frontend uses Next.js App Router, React, strict TypeScript, and Tailwind CSS. Route files in `app/` stay thin where a feature has substantial client behavior; those routes render screens from `features/`.

## Module boundaries

- `app/`: routes, route layouts, metadata, and route-only composition.
- `features/`: workflows and feature-specific UI. A feature owns its data loading, mutations, and domain-specific components.
- `components/ui/`: reusable, domain-neutral UI primitives and shared style contracts.
- `components/`: reusable application components that know about application models, such as book/chapter filters.
- `lib/`: API transport, shared domain types, caching, and pure utilities.
- `tests/`: Playwright regression coverage for critical user flows.

Dependencies should point inward: routes may use features and components; features may use components and `lib`; `components/ui` must not import from a feature.

## Shared UI

Import reusable primitives from `@/components/ui`:

- `Badge`: compact status labels with the existing neutral, green, amber, and blue tones.
- `Modal`: accessible dialog shell with backdrop dismissal, Escape dismissal, focus containment, and focus restoration.
- `inputClass`: the standard management form-control style.
- `primaryButton` and `secondaryButton`: established action styles, usable on buttons and links.

`ManageHeader` remains in `features/management` because its breadcrumb and destination are specific to that workflow.

When adding UI, first reuse an existing primitive. Add a new primitive only when the same visual and behavioral contract is needed by multiple features. Keep domain data fetching and business rules out of `components/ui`, and preserve values in `tailwind.config.ts` instead of introducing one-off color constants.

## Verification

Run from `frontend/`:

```sh
npm run lint
npm run typecheck
NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run build
```

Playwright expects the frontend at port 3100 and its isolated backend at port 8100; see `playwright.config.ts` and `tests/stabilization.spec.ts`.
