# Frontend (React + Vite)

This is the web UI for the task management platform.

## Prerequisites

- Node.js 18+ (recommended 20+)
- npm

## Install

```bash
npm ci
```

## Run in development

```bash
npm run dev
```

Default local URL: `http://localhost:3000`

## API proxy behavior

Vite proxies `/api/*` to:

- `VITE_API_URL` (if provided), or
- `http://localhost:8000` (default)

Example:

```bash
VITE_API_URL=http://localhost:8003 npm run dev
```

## Build

```bash
npm run build
```

Preview built files locally:

```bash
npm run preview
```

## Type check

```bash
npm run lint
```
