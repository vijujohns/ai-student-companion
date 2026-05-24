# Brain Teaser Frontend (Vite)

This frontend runs on Vite + React.

## Scripts

- `npm run dev` or `npm start`: Start local dev server
- `npm run build`: Production build (output in `dist/`)
- `npm run preview`: Preview production build locally
- `npm run test`: Run tests with Vitest

## Environment Variables

Create/update `.env.local` in `v3/frontend`:

- Network settings are loaded from `../configs/settings.base.json` plus the active environment overlay.
- Keep `.env.local` empty unless you explicitly need an override for a special environment.

Only variables prefixed with `VITE_` are exposed to frontend code.

## Local Run

1. `npm install`
2. `npm run dev`
3. Open the frontend URL defined by `network.frontend` in the active merged config

## Production Build

1. `npm run build`
2. Deploy the `dist/` folder to your static host
