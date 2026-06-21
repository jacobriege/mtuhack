# Wingman Frontend (Vue + Vite)

Frontend dashboard for viewing PPE violations and emergency detections.

## Prerequisites

- Node.js version supported by `package.json` engines
- Running backend API at `http://localhost:8000`

## Run locally

```bash
cd frontend/wingman
npm install
npm run dev
```

Open: `http://localhost:5173`

## Build

```bash
npm run build
```

## Current structure

- `src/main.js` — Vue bootstrap entrypoint.
- `src/App.vue` — app shell hosting the main inspector UI.
- `src/components/MissconductInspector.vue` — top-level layout coordinator.
- `src/components/MissconductExplorer.vue` — misconduct list and selection.
- `src/components/Filter.vue` — popup filters for date range and flagged records.
- `src/components/MissconductDetailsViewer.vue` — selected image viewer.
- `src/components/MissconductCounter.vue` — pie-chart summary.
- `src/components/Container1.vue` / `button1.vue` / `Devider.vue` / `VerticalDevider.vue` — shared UI wrappers.
- `src/components/MisconductTimeline.vue` — currently empty placeholder component.
- `src/assets/` — base/global styling and static assets.

## API endpoints used by the frontend

- `GET /violations/unread`
- `GET /violations/bydate?startdate=...&enddate=...&flagged=true`
- `GET /violations/count`
