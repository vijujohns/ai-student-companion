# AI Tutor

## Deployment Knobs
Host, port, protocol, CORS, Redis, model, and RAG values are loaded from [configs/settings.base.json](../configs/settings.base.json) plus an environment overlay.

Environment overlays:

- Development: [configs/settings.dev.json](../configs/settings.dev.json)
- Testing: [configs/settings.test.json](../configs/settings.test.json)
- Production example: [configs/settings.prod.example.json](../configs/settings.prod.example.json)

Environment variable names and defaults are listed in [ENVIRONMENT.md](ENVIRONMENT.md).

Update the matching environment overlay when moving to another machine or environment:

- network.backend.bind_host: Backend bind interface (for example 0.0.0.0)
- network.backend.public_host: Hostname/IP exposed to browser clients
- network.backend.port: Backend HTTP/WS port
- network.backend.protocol: API protocol used by frontend (http or https)
- network.backend.ws_protocol: WebSocket protocol used by frontend (ws or wss)
- network.frontend.host: Vite host bind value
- network.frontend.port: Frontend dev port
- network.frontend.preview_port: Frontend preview port
- network.cors.origins: Explicit allowed origins for browser calls
- network.cors.origin_regex: Optional regex for broader origin matching
- network.redis.host: Redis host
- network.redis.port: Redis port
- network.testing.host: Host used by Playwright test server
- network.testing.frontend_port: Playwright frontend test port
- network.testing.backend_port: Playwright backend test port

Runtime code paths already read from the merged config:

- Backend startup: [backend/run.py](../backend/run.py)
- Backend CORS: [backend/app/main.py](../backend/app/main.py)
- Redis client config: [backend/app/modules/cache.py](../backend/app/modules/cache.py)
- Frontend API base URL: [frontend/src/services/api.js](../frontend/src/services/api.js)
- Frontend WS base URL: [frontend/src/services/websocket.js](../frontend/src/services/websocket.js)
- Frontend dev/preview server: [frontend/vite.config.js](../frontend/vite.config.js)
- Playwright test networking: [frontend/playwright.config.js](../frontend/playwright.config.js)

## Sample Config Profiles

### Development (Single Machine)
```json
{
	"network": {
		"backend": {
			"bind_host": "0.0.0.0",
			"public_host": "",
			"port": 8000,
			"protocol": "http",
			"ws_protocol": "ws"
		},
		"frontend": {
			"host": "0.0.0.0",
			"port": 3000,
			"preview_port": 4173
		},
		"redis": {
			"host": "localhost",
			"port": 6379
		}
	}
}
```

### Production (Public Host + TLS)
```json
{
	"network": {
		"backend": {
			"bind_host": "0.0.0.0",
			"public_host": "api.yourdomain.com",
			"port": 443,
			"protocol": "https",
			"ws_protocol": "wss"
		},
		"frontend": {
			"host": "0.0.0.0",
			"port": 3000,
			"preview_port": 4173
		},
		"cors": {
			"origins": [
				"https://yourdomain.com",
				"https://www.yourdomain.com"
			],
			"origin_regex": "^https://([a-zA-Z0-9-]+\\.)?yourdomain\\.com$"
		},
		"redis": {
			"host": "redis.internal",
			"port": 6379
		}
	}
}
```

## Backend
cd backend
pip install -r requirements.txt
python run.py

## Redis
Install Redis locally and run:
redis-server

## Frontend
cd frontend
npm install
npm start

## Features
- RAG Q&A
- WebSocket streaming
- Redis caching
- JWT auth (extendable)
- Translation fallback
- PWA ready

## Architecture Docs
- Backend TruthMap: [backend/backend-truthmap.md](backend/backend-truthmap.md)
- Message Envelope: [backend/message-envelope.md](backend/message-envelope.md)
- Frontend README: [frontend/README.md](frontend/README.md)

## Troubleshooting
- Ensure Redis running
- Use Python 3.10+
