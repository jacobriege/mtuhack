# Frontend Documentation

This folder contains the frontend client project for the MTUHack system.

## Layout

- `wingman/` — Vue 3 + Vite application.
  - `src/main.js` — app entrypoint and mount logic.
  - `src/App.vue` — top-level app shell.
  - `src/components/` — UI modules for exploration, filtering, charting, details display, and shared layout wrappers.
  - `src/components/icons/` — icon components from the Vue starter template (currently not used by the dashboard flow).
  - `src/assets/` — global CSS and static frontend assets.

## Runtime flow

1. `main.js` boots the app.
2. `App.vue` renders the inspector component (`MissconductInspector.vue`).
3. The inspector coordinates:
   - explorer (`MissconductExplorer.vue`) for list, filters, and selection,
   - counter (`MissconductCounter.vue`) for the summary pie chart,
   - details viewer (`MissconductDetailsViewer.vue`) for selected image preview.

## API usage in current frontend

- `GET /violations/unread`
- `GET /violations/bydate?startdate=...&enddate=...&flagged=true`
- `GET /violations/count`

## Notes

- Component names currently keep the existing `Missconduct*` naming pattern to match the codebase as-is.
- `src/components/MisconductTimeline.vue` exists but is currently an empty placeholder.
