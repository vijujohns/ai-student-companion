# Message Envelope Contract

All user-facing REST responses use a stable message envelope.

## Response Shape

```json
{
  "...payload": "...",
  "message": {
    "message_id": "MSG-1000",
    "level": "INFO",
    "user_text": "Operation completed successfully."
  }
}
```

## Rules

- `message.message_id` is always present and stable.
- `message.level` is one of `INFO`, `ALERT`, `WARN`, `ERROR`, `CRITICAL`.
- `message.user_text` is safe for UI display.
- Errors also include an `error` field with machine-readable detail.

## Examples

### Success

```json
{
  "sessions": [],
  "message": {
    "message_id": "MSG-1000",
    "level": "INFO",
    "user_text": "Operation completed successfully."
  }
}
```

### Error

```json
{
  "message": {
    "message_id": "MSG-1401",
    "level": "ERROR",
    "user_text": "You are not authorized to perform this action."
  },
  "error": "Authorization header missing"
}
```
