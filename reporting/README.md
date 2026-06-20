# Reporting

**Violation types:**

- `no_hardhat`
- `no_west`
- `no_standup`

## Frontend

## Backend

**Start the server:**

```bash
.venv/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Routes

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/violations` | Submit a new violation |
| `GET` | `/violations/unread` | List unread violations |
| `GET` | `/violations/bydate` | Query violations by date range |
| `GET` | `/violations/count` | Count violations by type |
| `GET` | `/violations/instance/image` | Get anonymized image for a violation |
| `GET` | `/violations/instance/flag` | Toggle flag on a violation |
| `WS` | `/violations/ws` | Real-time violation stream |

---

## Testing
Simple testing scripts for debugging the reporting application.

```
test\
    test.py: creates a violaten using a test image
    test_get.py: test the frontend endpoints
    obama.jpeg: test image
    output: transormed images by the backend are stored here

```