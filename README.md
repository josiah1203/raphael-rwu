# raphael-rwu

Raphael Work Unit execution accounting, banking, allocation

## API

- Prefix: `/v1/rwu`
- Port: `8101`
- Health: `GET /health`

## Events

_Published and consumed events documented in `openapi.yaml` and raphael-contracts._

## Development

```bash
uv sync
uv run uvicorn raphael_rwu.app:app --reload --port 8101
```

Part of the [Raphael Platform](https://github.com/hummingbird-labs) by HummingBird Labs.
