# Tablet Webapp — Drill Recognition Console (Phase 3)

Army/NCC-inspired tablet control panel for the PC backend: QR pairing, readiness checks, recording, processing, reports, manual decisions, and attempt history.

## Prerequisites

- Node.js 18+
- PC backend running on `0.0.0.0:8000` (serves API + built webapp at `/app`)
- Tablet and PC on the same Wi-Fi network

## Setup

```bash
cd tablet-webapp
npm install
npm run build
```

The backend serves the production build from `tablet-webapp/dist` at `http://<PC_IP>:8000/app`.

## Development

```bash
npm run dev
```

Dev server: `http://<PC_IP>:5173/app/` (uses Vite proxy or manual backend URL).

For field use, prefer the backend-served build after `npm run build`.

## QR Pairing (recommended)

1. Start backend on PC: `uvicorn backend.app.main:app --host 0.0.0.0 --port 8000`
2. Terminal shows QR code; or open `http://<PC_IP>:8000/pair` on the PC browser
3. Scan QR from tablet camera — opens `http://<PC_IP>:8000/app?backend=...`
4. Webapp saves backend URL and opens the dashboard automatically

Manual fallback: `/connect`

## Usage Flow

```text
Scan QR → Dashboard → New Drill → Readiness Check → Record → Processing → Report
         ↓                                                              ↓
    System Status                                              Detailed Report / Manual Decision / Retake
```

1. **Landing** — Auto-connect from QR query params
2. **Dashboard** — System status + recent attempts
3. **New Session** — Cadet metadata + drill type cards
4. **Readiness** — Camera preview + pre-recording checks
5. **Recording** — Large start/stop controls + alignment guide
6. **Processing** — Stage checklist with WebSocket/polling
7. **Report** — Pass/fail summary, PDF, retake, manual decision
8. **Detailed Report** — Parameter table + evidence frame
9. **Attempt History** — Prior attempts for same cadet/drill

## Pages

| Route | Page |
|-------|------|
| `/` | QR auto-connect landing |
| `/connect` | Manual backend connection |
| `/dashboard` | Command console |
| `/admin` | System status |
| `/sessions/new` | New drill session |
| `/sessions/:id/readiness` | Pre-recording checks |
| `/sessions/:id/recording` | Start/stop recording |
| `/sessions/:id/processing` | Analysis progress |
| `/sessions/:id/report` | Report summary |
| `/sessions/:id/report/detailed` | Parameter + evidence view |
| `/sessions/:id/decision` | Instructor manual override |
| `/sessions/:id/attempts` | Attempt history |
| `/sessions/recent` | Recent sessions list |

## PWA

Installable on tablet browsers via `manifest.json` (standalone mode, army-green theme).

## Backend URL Storage

`localStorage` keys:

- `drill_backend_url`
- `drill_pairing_token` (when present in QR URL)

## Supported Drills

| Drill | Backend |
|-------|---------|
| Salute | ✅ Supported |
| Kadam Tal | ✅ Supported |
| Attention, March, Turns, Parade Rest | Coming soon (UI cards shown as disabled) |

## Tech Stack

- React 19 + TypeScript
- Vite 6 (`base: /app/`)
- Tailwind CSS 4
- Axios + React Router 7
- Native WebSocket API
