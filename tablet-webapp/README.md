# Tablet Webapp — Drill Recognition (Phase 2)

React tablet webapp for controlling the PC backend: create sessions, start/stop recording, track processing, and view drill reports.

## Prerequisites

- Node.js 18+
- PC backend running (`uvicorn backend.app.main:app --host 0.0.0.0 --port 8000`)
- Tablet and PC on the same Wi-Fi network

## Setup

```bash
cd tablet-webapp
npm install
```

## Development

```bash
npm run dev
```

Open on tablet: `http://<PC_IP>:5173`

The dev server binds to `0.0.0.0` so tablets on the local network can connect.

## Production Build

```bash
npm run build
npm run preview -- --host 0.0.0.0
```

Or serve `dist/` with Nginx, or mount as static files from FastAPI.

## Usage Flow

1. **Connect** — Enter PC backend URL (e.g. `http://192.168.1.20:8000`)
2. **Dashboard** — Verify camera, model, and storage status
3. **New Session** — Enter cadet info and drill type (`kadam_tal` is fully supported)
4. **Recording** — Start/stop drill recording on the PC camera
5. **Processing** — Live WebSocket progress with polling fallback
6. **Report** — Score, summary, parameter table, media links
7. **Retake** — Reuse cadet/drill info for a new attempt

## Pages

| Route | Page |
|-------|------|
| `/` | Connection |
| `/dashboard` | System status |
| `/sessions/new` | Create session |
| `/sessions/:id/recording` | Start/stop recording |
| `/sessions/:id/processing` | Analysis progress |
| `/sessions/:id/report` | Drill report |
| `/sessions/recent` | Recent sessions list |

## Backend URL Storage

Saved in browser `localStorage` under key `drill_backend_url`.

## Supported Drills

| Drill | Backend |
|-------|---------|
| Kadam Tal | ✅ Supported |
| Salute | Coming soon |
| Attention | Coming soon |
| March | Coming soon |

## Tech Stack

- React 19 + TypeScript
- Vite 6
- Tailwind CSS 4
- Axios
- React Router 7
- Native WebSocket API
