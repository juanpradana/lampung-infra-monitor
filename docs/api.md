# API Documentation

## Base URL
```
http://localhost:8032/api
```

## Authentication

Semua endpoint (kecuali login) memerlukan JWT token di header:
```
Authorization: Bearer <token>
```

### Login
```http
POST /api/auth/login
Content-Type: application/x-www-form-urlencoded

username=admin&password=admin123
```

Response:
```json
{
    "access_token": "eyJ...",
    "token_type": "bearer",
    "user": {
        "id": 1,
        "username": "admin",
        "role": "superadmin"
    }
}
```

---

## Events

### List Events (dengan filter)
```http
GET /api/events?page=1&per_page=50&category=bencana&severity=high&kabupaten=Bandar+Lampung&date_from=2026-01-01&search=banjir
```

### Create Event
```http
POST /api/events
Authorization: Bearer <token>
Content-Type: application/json

{
    "title": "Banjir di Way Halim",
    "description": "Banjir setinggi 1 meter",
    "category": "bencana",
    "severity": "high",
    "kabupaten": "Bandar Lampung",
    "kecamatan": "Way Halim",
    "latitude": -5.3971,
    "longitude": 105.2668
}
```

### Update Event
```http
PUT /api/events/{id}
Authorization: Bearer <token>

{
    "status": "resolved",
    "resolved_at": "2026-06-02T10:00:00"
}
```

### Delete Event (superadmin only)
```http
DELETE /api/events/{id}
Authorization: Bearer <token>
```

---

## Dashboard

### Statistics
```http
GET /api/dashboard/stats?days=30
```

### Timeline
```http
GET /api/dashboard/timeline?days=30&category=bencana
```

### By Location
```http
GET /api/dashboard/by-location?days=30
```

### By Category
```http
GET /api/dashboard/by-category?days=30&kabupaten=Bandar+Lampung
```

### Monitoring Logs
```http
GET /api/dashboard/monitoring-logs?limit=20
```

---

## Admin (superadmin only)

### List Users
```http
GET /api/admin/users
```

### Update User
```http
PUT /api/admin/users/{id}

{
    "role": "operator",
    "is_active": true
}
```

### Delete User
```http
DELETE /api/admin/users/{id}
```

### Trigger Monitoring
```http
POST /api/admin/monitoring/trigger?job=all
```

### Test Telegram
```http
POST /api/admin/telegram/test

{
    "message": "Test notification"
}
```

### Get Locations
```http
GET /api/admin/locations
```

---

## Roles

| Role | Bisa |
|------|------|
| **superadmin** | Semua: CRUD user, CRUD events, trigger monitoring, Telegram test |
| **operator** | CRUD events (input/edit/hapus insiden) |
| **viewer** | Dashboard read-only, lihat data |

---

## Error Codes

| Code | Meaning |
|------|---------|
| 400 | Bad Request |
| 401 | Unauthorized (token invalid/expired) |
| 403 | Forbidden (role tidak cukup) |
| 404 | Not Found |
| 500 | Internal Server Error |
