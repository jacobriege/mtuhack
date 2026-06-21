# Wingman Frontend (Vue + Vite)

Frontend dashboard for viewing PPE violations and emergency detections.

## Prerequisites

- Node.js version supported by `package.json` engines
- Running backend API at `http://localhost:5000`

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
- `src/js/websocketIntegration.js` — websocket client that increments the shared update counter.
- `src/components/Container1.vue` / `button1.vue` / `Devider.vue` / `VerticalDevider.vue` — shared UI wrappers.
- `src/components/MisconductTimeline.vue` — currently empty placeholder component.
- `src/assets/` — base/global styling and static assets.

## API endpoints used by the frontend

- `GET /violations/bydate?startdate=...&enddate=...&flagged=true[&unread=true]`
- `GET /violations/count`
- `GET /violations/instance/image?violationId=...`
- `GET /violations/instance/flag?set=...&violationId=...`

## WebSocket integration

- Frontend websocket client: `src/js/websocketIntegration.js`
- Endpoint: `ws://localhost:5000/violations/ws`
- Behavior: each websocket message increments `data.updatecounter`, which refreshes list and counter components.
