# Tokamak AI API Server - API 문서

## 목차

1. [인증](#인증)
2. [헬스 체크](#헬스-체크)
3. [API 키 관리](#api-키-관리)
4. [Ollama API](#ollama-api)
5. [사용량 통계](#사용량-통계)
6. [에러 처리](#에러-처리)

---

## 인증

모든 API 요청은 Bearer 토큰 인증을 사용합니다.

```http
Authorization: Bearer sk-your-api-key-here
```

### 사용자 역할

- **admin**: 모든 엔드포인트 접근 가능, API 키 관리 권한
- **user**: 일반 API 사용 가능
- **readonly**: 읽기 전용 (현재 미구현)

---

## 헬스 체크

### GET /health

서버 상태를 확인합니다. 인증이 필요하지 않습니다.

**요청 예시:**
```bash
curl http://localhost:8000/health
```

**응답 예시:**
```json
{
  "status": "ok",
  "timestamp": "2025-12-16T06:56:01.780714Z",
  "version": "1.0.0",
  "ollama_servers": [
    {
      "url": "http://192.168.50.180:11434",
      "healthy": true,
      "current_load": 0,
      "success_count": 0,
      "fail_count": 0,
      "response_time_ms": 0,
      "last_check": "2025-12-15T22:55:58.626703+00:00"
    }
  ],
  "database_connected": true
}
```

### GET /status

상세 서버 상태를 확인합니다. **관리자 권한 필요**

**요청 예시:**
```bash
curl http://localhost:8000/status \
  -H "Authorization: Bearer sk-your-admin-key"
```

**응답 예시:**
```json
{
  "load_balancer": {
    "servers": [...],
    "total_requests": 0,
    "total_failures": 0
  },
  "timestamp": "2025-12-16T06:56:01.780714Z"
}
```

---

## API 키 관리

모든 API 키 관리 엔드포인트는 **관리자 권한**이 필요합니다.

### POST /admin/api-keys

새로운 API 키를 생성합니다.

**요청 본문:**
```json
{
  "username": "developer1",
  "role": "user",
  "rate_limit": 1000,
  "description": "프론트엔드 개발자"
}
```

**필드 설명:**
- `username` (필수): 사용자 이름
- `role` (선택): `admin`, `user`, `readonly` (기본값: `user`)
- `rate_limit` (선택): 시간당 요청 제한 (기본값: 1000)
- `description` (선택): 설명

**요청 예시:**
```bash
curl -X POST http://localhost:8000/admin/api-keys \
  -H "Authorization: Bearer sk-your-admin-key" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "developer1",
    "role": "user",
    "rate_limit": 1000,
    "description": "프론트엔드 개발자"
  }'
```

**응답 예시:**
```json
{
  "api_key": "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "username": "developer1",
  "role": "user",
  "rate_limit": 1000,
  "created_at": "2025-12-16T06:55:58.670000Z",
  "description": "프론트엔드 개발자"
}
```

**⚠️ 중요:** API 키는 생성 시에만 표시됩니다. 안전하게 저장하세요.

### GET /admin/api-keys

모든 API 키 목록을 조회합니다.

**요청 예시:**
```bash
curl http://localhost:8000/admin/api-keys \
  -H "Authorization: Bearer sk-your-admin-key"
```

**응답 예시:**
```json
{
  "keys": [
    {
      "username": "admin_new",
      "role": "admin",
      "rate_limit": 10000,
      "is_active": true,
      "created_at": "2025-12-16T06:55:58.670000Z",
      "last_used_at": "2025-12-16T06:56:01.780714Z",
      "description": null
    },
    {
      "username": "developer1",
      "role": "user",
      "rate_limit": 1000,
      "is_active": true,
      "created_at": "2025-12-16T06:55:58.670000Z",
      "last_used_at": null,
      "description": "프론트엔드 개발자"
    }
  ]
}
```

### DELETE /admin/api-keys/{username}

특정 사용자의 API 키를 취소합니다.

**요청 예시:**
```bash
curl -X DELETE http://localhost:8000/admin/api-keys/developer1 \
  -H "Authorization: Bearer sk-your-admin-key"
```

**응답 예시:**
```json
{
  "message": "API key for developer1 has been revoked"
}
```

---

## Ollama API

Ollama API와 호환되는 엔드포인트입니다.

### POST /api/generate

텍스트 생성을 요청합니다.

#### 스트리밍 vs 비스트리밍

**비스트리밍 (stream: false)** - 기본값
- 전체 응답이 완성된 후 한 번에 반환됩니다
- 응답을 받기까지 시간이 걸릴 수 있습니다
- 전체 응답을 한 번에 처리할 수 있습니다
- 사용 사례: 간단한 요청, 배치 처리, 전체 응답이 필요한 경우

**스트리밍 (stream: true)**
- 응답이 생성되는 즉시 실시간으로 청크 단위로 전송됩니다
- 첫 번째 토큰부터 바로 받을 수 있어 응답 속도가 빠르게 느껴집니다
- 각 줄이 JSON 객체로 전송됩니다 (NDJSON 형식)
- 사용 사례: 대화형 인터페이스, 긴 응답, 실시간 피드백이 필요한 경우

**차이점 비교:**

| 항목 | 비스트리밍 | 스트리밍 |
|------|-----------|---------|
| 응답 방식 | 전체 응답 한 번에 | 청크 단위 실시간 |
| 첫 응답 시간 | 전체 생성 완료 후 | 즉시 시작 |
| 사용자 경험 | 대기 시간 있음 | 즉각적인 피드백 |
| 데이터 형식 | 단일 JSON 객체 | NDJSON (줄 단위) |
| 처리 방식 | 한 번에 처리 | 스트림 처리 필요 |

**요청 본문:**
```json
{
  "model": "gpt-oss:20b",
  "prompt": "Python으로 피보나치 수열을 계산하는 함수를 작성하세요",
  "stream": false,
  "options": {
    "temperature": 0.7,
    "top_p": 0.9
  },
  "system": "You are a helpful coding assistant",
  "template": null,
  "context": null,
  "raw": false
}
```

**필드 설명:**
- `model` (필수): 사용할 모델 이름
- `prompt` (필수): 생성할 프롬프트
- `stream` (선택): 스트리밍 응답 여부 (기본값: `false`)
- `options` (선택): 모델 옵션 (temperature, top_p 등)
- `system` (선택): 시스템 프롬프트
- `template` (선택): 프롬프트 템플릿
- `context` (선택): 이전 응답에서 받은 컨텍스트 토큰 배열. 연속된 대화를 유지하려는 경우에만 사용. 단발성 요청에서는 생략 가능.
- `raw` (선택): 원시 모드
- `format` (선택): 응답 형식. `"json"`을 지정하면 JSON 구조화 응답 요청. 기본값: `null`

**요청 예시 (비스트리밍):**
```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Authorization: Bearer sk-your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-oss:20b",
    "prompt": "Hello, world!",
    "stream": false
  }'
```

**응답 예시 (비스트리밍):**
```json
{
  "model": "gpt-oss:20b",
  "created_at": "2025-12-16T06:56:01.780714Z",
  "response": "Hello! How can I help you today?",
  "done": true,
  "context": [1234, 5678, 9012],
  "total_duration": 1234567890,
  "load_duration": 123456,
  "prompt_eval_count": 10,
  "prompt_eval_duration": 123456,
  "eval_count": 20,
  "eval_duration": 1234567
}
```

**참고:**
- `context` 필드는 Ollama 백엔드가 반환하는 토큰 ID 배열입니다.
- 단발성 요청에서는 `context`를 무시해도 됩니다.
- 연속된 대화를 유지하려면 이전 응답의 `context`를 다음 요청에 포함하세요.

**요청 예시 (스트리밍):**
```bash
# 기본 스트리밍 (버퍼링 없이 실시간 출력)
curl -X POST http://localhost:8000/api/generate \
  -H "Authorization: Bearer sk-your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-oss:20b",
    "prompt": "Hello, world!",
    "stream": true
  }' \
  --no-buffer

# 또는 N 옵션 사용 (줄 단위로 실시간 출력)
curl -N -X POST http://localhost:8000/api/generate \
  -H "Authorization: Bearer sk-your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-oss:20b",
    "prompt": "Hello, world!",
    "stream": true
  }'

# JSON 포맷팅과 함께 (각 줄을 JSON으로 파싱)
curl -N -X POST http://localhost:8000/api/generate \
  -H "Authorization: Bearer sk-your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-oss:20b", "prompt": "Hello, world!", "stream": true}' \
  | while IFS= read -r line; do
      echo "$line" | python -m json.tool 2>/dev/null || echo "$line"
    done
```

**응답 예시 (스트리밍):**
각 줄이 JSON 객체로 전송됩니다:
```json
{"model": "gpt-oss:20b", "created_at": "...", "response": "Hello", "done": false}
{"model": "gpt-oss:20b", "created_at": "...", "response": "!", "done": false}
{"model": "gpt-oss:20b", "created_at": "...", "response": "", "done": true}
```

### POST /api/chat

채팅 형식의 대화를 요청합니다.

**요청 본문:**
```json
{
  "model": "gpt-oss:20b",
  "messages": [
    {
      "role": "system",
      "content": "You are a helpful coding assistant"
    },
    {
      "role": "user",
      "content": "Python으로 리스트를 정렬하는 방법을 알려주세요"
    }
  ],
  "stream": false,
  "options": {
    "temperature": 0.7
  }
}
```

**필드 설명:**
- `model` (필수): 사용할 모델 이름
- `messages` (필수): 메시지 배열
  - `role`: `system`, `user`, `assistant`
  - `content`: 메시지 내용
  - `images` (선택): 이미지 URL 배열
- `stream` (선택): 스트리밍 응답 여부
- `options` (선택): 모델 옵션
- `format` (선택): 응답 형식. `"json"`을 지정하면 JSON 구조화 응답 요청. 기본값: `null`

**요청 예시:**
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Authorization: Bearer sk-your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-oss:20b",
    "messages": [
      {"role": "user", "content": "Hello!"}
    ],
    "stream": false
  }'
```

**응답 예시:**
```json
{
  "model": "gpt-oss:20b",
  "created_at": "2025-12-16T06:56:01.780714Z",
  "message": {
    "role": "assistant",
    "content": "Hello! How can I help you?"
  },
  "done": true,
  "total_duration": 1234567890,
  "load_duration": 123456,
  "prompt_eval_count": 10,
  "prompt_eval_duration": 123456,
  "eval_count": 20,
  "eval_duration": 1234567
}
```

### GET /api/tags

사용 가능한 모델 목록을 조회합니다.

**요청 예시:**
```bash
curl http://localhost:8000/api/tags \
  -H "Authorization: Bearer sk-your-api-key"
```

**응답 예시:**
```json
{
  "models": [
    {
      "name": "gpt-oss:20b",
      "model": "gpt-oss:20b",
      "modified_at": "2025-12-16T06:55:58.670000Z",
      "size": 65369818941,
      "digest": "a951a23b46a1f6093dafee2ea481d634b4e31ac720a8a16f3f91e04f5a40ecd9",
      "details": {
        "parent_model": "",
        "format": "gguf",
        "family": "gptoss",
        "families": ["gptoss"],
        "parameter_size": "116.8B",
        "quantization_level": "MXFP4"
      }
    }
  ]
}
```

---

## 사용량 통계

### GET /usage/me

현재 사용자의 사용량 통계를 조회합니다.

**요청 예시:**
```bash
curl http://localhost:8000/usage/me \
  -H "Authorization: Bearer sk-your-api-key"
```

**응답 예시:**
```json
{
  "username": "developer1",
  "rate_limit": 1000,
  "current_hour_usage": 42,
  "remaining": 958,
  "recent_requests": [
    {
      "timestamp": "2025-12-16T06:56:01.780714Z",
      "model": "gpt-oss:20b",
      "endpoint": "generate",
      "success": true,
      "duration_ms": 1234
    }
  ]
}
```

### GET /admin/usage/{username}

특정 사용자의 사용량 통계를 조회합니다. **관리자 권한 필요**

**쿼리 파라미터:**
- `days` (선택): 조회할 일수 (기본값: 7)

**요청 예시:**
```bash
curl "http://localhost:8000/admin/usage/developer1?days=30" \
  -H "Authorization: Bearer sk-your-admin-key"
```

**응답 예시:**
```json
{
  "username": "developer1",
  "total_requests": 150,
  "successful_requests": 148,
  "failed_requests": 2,
  "total_tokens": 45000,
  "avg_tokens_per_request": 300.0,
  "most_used_model": "gpt-oss:20b",
  "period_start": "2025-12-09T06:56:01.780714Z",
  "period_end": "2025-12-16T06:56:01.780714Z"
}
```

---

## 에러 처리

### HTTP 상태 코드

- `200 OK`: 요청 성공
- `400 Bad Request`: 잘못된 요청 형식
- `401 Unauthorized`: 인증 실패 (API 키 없음 또는 잘못됨)
- `403 Forbidden`: 권한 없음 (관리자 권한 필요)
- `404 Not Found`: 리소스를 찾을 수 없음
- `429 Too Many Requests`: Rate limit 초과
- `500 Internal Server Error`: 서버 내부 오류
- `502 Bad Gateway`: Ollama 서버 연결 실패
- `503 Service Unavailable`: 서비스 사용 불가

### 에러 응답 형식

```json
{
  "error": "Rate limit exceeded",
  "detail": "You have exceeded your rate limit of 1000 requests per hour",
  "timestamp": "2025-12-16T06:56:01.780714Z"
}
```

### Rate Limit 에러

Rate limit을 초과하면 다음 응답을 받습니다:

```json
{
  "error": "Rate limit exceeded",
  "detail": "You have exceeded your rate limit of 1000 requests per hour. Remaining: 0",
  "timestamp": "2025-12-16T06:56:01.780714Z"
}
```

**응답 헤더:**
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1702728000
```

---

## 예제

### Python 예제

```python
import requests

API_URL = "http://localhost:8000"
API_KEY = "sk-your-api-key-here"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# 텍스트 생성
response = requests.post(
    f"{API_URL}/api/generate",
    headers=headers,
    json={
        "model": "gpt-oss:20b",
        "prompt": "Python으로 hello world 함수를 작성하세요",
        "stream": False
    }
)

print(response.json())

# 채팅
response = requests.post(
    f"{API_URL}/api/chat",
    headers=headers,
    json={
        "model": "gpt-oss:20b",
        "messages": [
            {"role": "user", "content": "Hello!"}
        ],
        "stream": False
    }
)

print(response.json()["message"]["content"])

# 사용량 확인
response = requests.get(
    f"{API_URL}/usage/me",
    headers=headers
)

usage = response.json()
print(f"사용량: {usage['current_hour_usage']}/{usage['rate_limit']}")
```

### JavaScript/Node.js 예제

```javascript
const API_URL = "http://localhost:8000";
const API_KEY = "sk-your-api-key-here";

const headers = {
  "Authorization": `Bearer ${API_KEY}`,
  "Content-Type": "application/json"
};

// 텍스트 생성
async function generate() {
  const response = await fetch(`${API_URL}/api/generate`, {
    method: "POST",
    headers: headers,
    body: JSON.stringify({
      model: "gpt-oss:20b",
      prompt: "Python으로 hello world 함수를 작성하세요",
      stream: false
    })
  });
  
  const data = await response.json();
  console.log(data.response);
}

// 스트리밍 생성
async function generateStream() {
  const response = await fetch(`${API_URL}/api/generate`, {
    method: "POST",
    headers: headers,
    body: JSON.stringify({
      model: "gpt-oss:20b",
      prompt: "Python으로 hello world 함수를 작성하세요",
      stream: true
    })
  });
  
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    
    const chunk = decoder.decode(value);
    const lines = chunk.split('\n').filter(line => line.trim());
    
    for (const line of lines) {
      const data = JSON.parse(line);
      if (data.response) {
        process.stdout.write(data.response);
      }
      if (data.done) {
        console.log('\n완료');
        return;
      }
    }
  }
}
```

### cURL 예제

```bash
# 환경 변수 설정
export API_URL="http://localhost:8000"
export API_KEY="sk-your-api-key-here"

# Health check
curl $API_URL/health

# 모델 목록
curl $API_URL/api/tags \
  -H "Authorization: Bearer $API_KEY"

# 텍스트 생성
curl -X POST $API_URL/api/generate \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-oss:20b",
    "prompt": "Hello, world!",
    "stream": false
  }'

# 사용량 확인
curl $API_URL/usage/me \
  -H "Authorization: Bearer $API_KEY"
```

---

## Rate Limiting

각 API 키는 시간당 요청 제한이 있습니다. 기본값은 1000 requests/hour입니다.

Rate limit 정보는 응답 헤더에 포함됩니다:

```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 958
X-RateLimit-Reset: 1702728000
```

Rate limit을 초과하면 `429 Too Many Requests` 응답을 받습니다.

---

## Swagger UI

서버가 실행 중일 때 다음 URL에서 대화형 API 문서를 확인할 수 있습니다:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

---

## 버전 정보

- **API 버전**: 1.0.0
- **Ollama API 호환성**: Ollama API v1.0과 호환

---

## 지원

문제가 발생하거나 질문이 있으면 다음을 확인하세요:

1. [README.md](../README.md) - 설치 및 설정 가이드
2. [QUICKSTART.md](QUICKSTART.md) - 빠른 시작 가이드
3. [ARCHITECTURE.md](ARCHITECTURE.md) - 아키텍처 설명

