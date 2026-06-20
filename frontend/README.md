# Frontend Documentation

This folder contains the frontend client project for the MTUHack system.

## Layout

- `wingman/` — Vue 3 + Vite application.
  - `src/main.js` — app entrypoint and mount logic.
  - `src/App.vue` — top-level app shell.
  - `src/components/` — UI modules for exploration, filtering, charting, and details display.
  - `src/assets/` — global CSS and static frontend assets.

## Runtime flow

1. `main.js` boots the app.
2. `App.vue` renders `MissconductInspector`.
3. `MissconductInspector` coordinates:
   - `MissconductExplorer` (list + filters + selection),
   - `MissconductCounter` (summary pie chart),
   - `MissconductDetailsViewer` (selected image preview).

## API usage in current frontend

- `GET /violations/unread`
- `GET /violations/bydate?startdate=...&enddate=...&flagged=true`
- `GET /violations/count`
