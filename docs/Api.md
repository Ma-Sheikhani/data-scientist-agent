# 📖 API Reference

This document describes the REST API of the **Data Scientist Agent**.

All endpoints accept and return **JSON**, except file uploads, which use `multipart/form-data`.

Interactive API documentation is available through **Swagger UI** when the server is running:

```text
http://localhost:8000/docs
```

---

## Base URL

```text
http://localhost:8000
```

All API paths in this document are relative to the base URL.

---

# 🔐 Authentication

The API uses **JWT (JSON Web Token)** authentication.

Most endpoints require a valid access token sent as a **Bearer** token in the `Authorization` header.

```http
Authorization: Bearer <access_token>
```

Access tokens are obtained from the `/auth/token` endpoint and expire after a configurable period (30 minutes by default).

---

# 🚦 Rate Limiting

To protect the service against abuse, the API applies configurable rate limits using **SlowAPI**.

| Endpoint | Default Limit |
|----------|---------------|
| `/auth/token` | 10 requests per minute per IP |
| `/v1/analyze` | 5 requests per minute per IP |
| All other endpoints | 50 requests per hour / 200 requests per day |

When a rate limit is exceeded, the API returns:

```http
429 Too Many Requests
```

---

# 📌 Endpoints

## 1. Register a New User

### Endpoint

```http
POST /auth/register
```

### Request Body

```json
{
  "email": "user@example.com",
  "password": "securepassword"
}
```

### Response — 201 Created

```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "email": "user@example.com",
  "is_active": true
}
```

### Possible Errors

| Status Code | Description |
|-------------|-------------|
| **400** | Email is already registered |
| **422** | Validation error (invalid email or missing fields) |

---

## 2. Login (Obtain an Access Token)

### Endpoint

```http
POST /auth/token
```

### Request Body

```json
{
  "email": "user@example.com",
  "password": "securepassword"
}
```

### Response — 200 OK

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

### Possible Errors

| Status Code | Description |
|-------------|-------------|
| **401** | Invalid email or password |
| **422** | Validation error |
| **429** | Rate limit exceeded |

---

## 3. Submit an Analysis Job

### Endpoint

```http
POST /v1/analyze
```

**Authentication required**

### Content Type

```text
multipart/form-data
```

### Request Fields

| Field | Type | Description |
|------|------|-------------|
| `file` | File | CSV dataset |
| `question` | String | Natural-language question about the dataset |

### Example

```bash
curl -X POST http://localhost:8000/v1/analyze \
  -H "Authorization: Bearer <TOKEN>" \
  -F "file=@iris.csv" \
  -F "question=What is the average sepal length by species?"
```

### Response — 201 Created

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "question": "What is the average sepal length by species?",
  "created_at": "2025-01-01T12:00:00Z",
  "result": null
}
```

### Possible Errors

| Status Code | Description |
|-------------|-------------|
| **400** | Invalid CSV file, missing filename, or invalid question |
| **401** | Authentication required |
| **413** | Uploaded file exceeds the maximum allowed size |
| **429** | Rate limit exceeded |

---

## 4. Get Job Status

### Endpoint

```http
GET /v1/analyze/{job_id}/status
```

**Authentication required**

### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `job_id` | UUID | Job identifier |

### Example

```bash
curl http://localhost:8000/v1/analyze/550e8400-e29b-41d4-a716-446655440000/status \
  -H "Authorization: Bearer <TOKEN>"
```

### Response While Running

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  "question": "...",
  "created_at": "...",
  "result": null
}
```

### Response When Completed

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "question": "...",
  "created_at": "...",
  "result": {
    "summary": "The average sepal length for setosa is 5.006 cm...",
    "statistics": {
      "setosa": {
        "mean": 5.006,
        "std": 0.352
      }
    },
    "figures": [0, 1],
    "tables": []
  }
}
```

### Possible Errors

| Status Code | Description |
|-------------|-------------|
| **401** | Authentication required |
| **404** | Job not found or access denied |

---

## 5. Retrieve a Generated Figure

### Endpoint

```http
GET /v1/analyze/{job_id}/figure/{index}
```

**Authentication required**

### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `job_id` | UUID | Job identifier |
| `index` | Integer | Zero-based figure index |

### Example

```bash
curl http://localhost:8000/v1/analyze/<JOB_ID>/figure/0 \
  -H "Authorization: Bearer <TOKEN>" \
  --output figure0.png
```

### Response

Returns the requested figure as an `image/png` file.

### Possible Errors

| Status Code | Description |
|-------------|-------------|
| **401** | Authentication required |
| **404** | Job not found, figure unavailable, or index out of range |

---

## 6. Agent Health Check

### Endpoint

```http
GET /agent-health
```

Authentication is **not required**.

Returns the health status of the sandbox service.

### Response

```json
{
  "sandbox": true
}
```

If the sandbox is unavailable:

```json
{
  "sandbox": false
}
```

---

## 7. API Health Check

### Endpoint

```http
GET /health
```

Authentication is **not required**.

This endpoint acts as a simple liveness probe.

### Response

```json
{
  "status": "ok"
}
```

---

# ❌ Error Responses

All error responses follow the same structure:

```json
{
  "detail": "Human-readable description of the error"
}
```

Rate limiting errors return:

```json
{
  "error": "Rate limit exceeded: 5 requests per minute"
}
```

---

# 🔌 Using the API with n8n

The included **n8n** workflows use these REST endpoints directly.

You can:

- Use the provided workflows without modification.
- Build your own frontend using the REST API.
- Generate client SDKs directly from the Swagger documentation.

Swagger UI is available at:

```text
http://localhost:8000/docs
```
