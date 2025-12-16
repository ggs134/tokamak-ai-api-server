# Architecture Documentation

## System Overview

```
                    인터넷
                      │
                      │ HTTPS (443)
                      ▼
            ┌─────────────────┐
            │  Nginx Proxy    │
            │  (Optional)     │
            │  - SSL/TLS      │
            │  - Rate Limit   │
            └────────┬────────┘
                     │
                     │ HTTP (8000)
                     ▼
        ┌─────────────────────────┐
        │   API Server            │
        │   (별도 머신)             │
        │                         │
        │  FastAPI Application    │
        │  ├─ Authentication      │
        │  ├─ Rate Limiter        │
        │  └─ Load Balancer       │
        │                         │
        │  ┌──────────┐           │
        │  │  SQLite  │ (로컬)     │
        │  │  Database│           │
        │  └──────────┘           │
        └─────────┬───────────────┘
                  │
                  │ 10Gbps 전용 네트워크
                  │ (192.168.100.0/24)
      ┌───────────┼───────────┐
      │           │           │
      ▼           ▼           ▼
┌──────────┐ ┌──────────┐ ┌──────────┐
│ DGX #1   │ │ DGX #2   │ │ DGX #10  │
│          │ │          │ │    ...   │
│ Ollama   │ │ Ollama   │ │ Ollama   │
│ :11434   │ │ :11434   │ │ :11434   │
│          │ │          │ │          │
│ RTX 6000 │ │ RTX 6000 │ │ RTX 6000 │
│ 96GB×8   │ │ 96GB×8   │ │ 96GB×8   │
└──────────┘ └──────────┘ └──────────┘
```

## 하드웨어 권장 사양

### API 서버 (별도 머신)

#### 옵션 1: 경량 구성 (소규모 팀 ~30명)
- **CPU**: AMD Ryzen 7 5800X (8코어) 또는 Intel i7-12700
- **RAM**: 16GB DDR4
- **Storage**: 256GB NVMe SSD
- **Network**: 1GbE (충분)
- **예상 비용**: ~$800-1000

#### 옵션 2: 권장 구성 (확장 가능)
- **CPU**: AMD Ryzen 9 5950X (16코어) 또는 Threadripper 3960X
- **RAM**: 32GB DDR4
- **Storage**: 512GB NVMe SSD
- **Network**: 10GbE (DGX와 같은 네트워크)
- **예상 비용**: ~$1500-2000

#### 옵션 3: 엔터프라이즈 구성 (대규모)
- **CPU**: AMD EPYC 7443P (24코어) 또는 Xeon Gold
- **RAM**: 64GB ECC
- **Storage**: 1TB NVMe SSD (RAID1)
- **Network**: 10GbE 듀얼 포트 (bonding)
- **예상 비용**: ~$3000-4000

### DGX Spark 서버들 (이미 보유)
- **GPU**: RTX 6000 Blackwell 96GB × 8개
- **Network**: 10GbE 이상
- **Ollama**: 포트 11434

## 소프트웨어 스택

### API 서버
```
┌─────────────────────────────┐
│  OS: Ubuntu 24.04 LTS       │
├─────────────────────────────┤
│  Python 3.11                │
│  ├─ FastAPI                 │
│  ├─ uvicorn (workers: 8)    │
│  ├─ httpx (async client)    │
│  ├─ SQLAlchemy (async ORM)  │
│  └─ aiosqlite (async)       │
├─────────────────────────────┤
│  SQLite 3                   │
├─────────────────────────────┤
│  Nginx (optional)           │
│  systemd                    │
└─────────────────────────────┘
```

### DGX 서버들
```
┌─────────────────────────────┐
│  Ollama Server              │
│  Port: 11434                │
│                             │
│  Models:                    │
│  ├─ deepseek-coder:33b      │
│  ├─ qwen2.5-coder:32b       │
│  └─ codellama:70b           │
└─────────────────────────────┘
```

## 데이터 흐름

### 1. 일반 요청 흐름
```
Client 
  → API Key 인증
  → Rate Limit 체크 (SQLite)
  → Load Balancer (최소 연결 서버 선택)
  → Ollama Server (DGX)
  → 응답 스트리밍
  → Usage 로깅 (SQLite)
  → Client
```

### 2. 장애 처리 흐름
```
Request
  → Server 1 (실패)
  → Load Balancer (failover)
  → Server 2 (성공)
  → Response

백그라운드:
  → Health Checker (60초마다)
  → Server 1 3회 연속 실패
  → Mark as Unhealthy
  → 다음 헬스 체크 시 복구 확인
```

## 성능 특성

### 30명 동시 사용 시나리오

**요청 패턴**:
- 평균 요청 간격: 30초
- 동시 요청: ~15개
- 피크 시간: ~30개

**리소스 사용량**:
```
API 서버:
├─ CPU: 20-40% (8코어 기준)
├─ RAM: 4-8GB
├─ Network: 50-100Mbps
└─ Disk I/O: 낮음 (SQLite DB + 로그)

SQLite:
├─ RAM: 50-100MB (캐시)
├─ Disk: DB 파일 크기 (수백 MB ~ 수 GB)
└─ Connections: 단일 파일 (동시 읽기 지원)
```

**응답 시간 분석**:
```
총 응답 시간: 12-25초 (평균 15초)
├─ API 인증: 2-5ms (0.03%)
├─ Rate Limit: 2-5ms (0.03%)
├─ 로드밸런싱: 1ms (0.01%)
├─ 네트워크 (API↔DGX): 0.5-1ms (0.01%)
├─ Ollama 추론: 12-25초 (99.92%)
└─ DB 로깅: 5-10ms (0.05%)

결론: LLM 추론 시간이 압도적 (99.9%)
     API 서버 오버헤드는 무시 가능 수준
```

## 확장성

### 수평 확장 (더 많은 사용자)

#### 1. API 서버 추가
```
              Load Balancer (Nginx/HAProxy)
                    │
        ┌───────────┼───────────┐
        │           │           │
        ▼           ▼           ▼
    API Server  API Server  API Server
        #1          #2          #3
        │           │           │
        └───────────┴───────────┘
                    │
            Shared SQLite Database
            (파일 공유 또는 네트워크 마운트)
```

#### 2. 데이터베이스 확장
- SQLite: 네트워크 파일 시스템(NFS) 또는 공유 스토리지 사용
- 대규모 환경: PostgreSQL로 마이그레이션 고려

#### 3. DGX 서버 추가
- 단순히 `.env`에 새 서버 추가
- 로드 밸런서가 자동으로 분산

### 수직 확장 (더 큰 모델)

#### 현재 구성 (RTX 6000 96GB)
- 33B 모델: 여유 있음
- 70B 모델: 가능
- 120B+ 모델: Tensor Parallelism 필요

#### 대용량 모델 서빙
```python
# Ollama에서 멀티 GPU 사용
# 자동으로 처리되므로 설정 불필요
```

## 고가용성 (HA) 구성

### 최소 HA 구성
```
           VIP (Keepalived)
                 │
        ┌────────┴────────┐
        │                 │
    API Server       API Server
    (Active)         (Standby)
        │                 │
        └────────┬────────┘
                 │
        Shared Storage/DB
```

### 완전 HA 구성
```
        Geographic Load Balancer
                 │
        ┌────────┴────────┐
        │                 │
   Data Center 1    Data Center 2
   ├─ API Servers  ├─ API Servers
   ├─ DGX Cluster  ├─ DGX Cluster
   └─ SQLite DB    └─ SQLite DB
      (복제)          (복제)
```

## 보안 아키텍처

### 네트워크 계층
```
Internet
  │ (HTTPS only)
  ▼
Nginx (DMZ)
  │ (HTTP, internal)
  ▼
API Server (Private Network)
  │ (Internal only)
  ▼
DGX Servers (Isolated VLAN)
```

### 인증 계층
```
1. API Key → 사용자 인증
2. Rate Limit → DDoS 방어
3. Role-based → 권한 관리
4. Audit Log → 추적 가능성
```

## 비용 분석

### 초기 투자
- API 서버 하드웨어: $1,500
- 네트워크 스위치: $0 (기존 사용)
- 소프트웨어: $0 (오픈소스)
**총 초기 비용: ~$1,500**

### 운영 비용 (월간)
- 전력 (API 서버): ~$20
- 데이터센터 랙 공간: $0 (기존)
- 유지보수: $0 (자체 관리)
**총 월간 비용: ~$20**

### DGX 서버 비용
- 이미 보유하고 있으므로 추가 비용 없음
- 기존 GPU 인프라 활용

## 배포 타임라인

```
Day 1: 하드웨어 준비
  ├─ API 서버 구매/준비
  └─ 네트워크 구성 확인

Day 2: 소프트웨어 설치
  ├─ OS 설치 (Ubuntu 24.04)
  ├─ Python 환경 구성
  └─ SQLite는 Python과 함께 제공됨

Day 3: API 서버 배포
  ├─ 코드 배포
  ├─ 데이터베이스 초기화
  ├─ API 키 생성
  └─ 테스트

Day 4: 통합 및 테스트
  ├─ DGX 서버 연결 확인
  ├─ 부하 테스트
  └─ 모니터링 설정

Day 5: 프로덕션 오픈
  ├─ 팀원 API 키 배포
  ├─ 사용 가이드 공유
  └─ 모니터링 시작
```

## 모니터링 대시보드

### 주요 메트릭
1. **요청 메트릭**
   - 초당 요청 수 (RPS)
   - 응답 시간 (p50, p95, p99)
   - 에러율

2. **백엔드 메트릭**
   - 각 DGX 서버 상태
   - 활성 연결 수
   - 응답 시간

3. **사용자 메트릭**
   - 사용자별 요청 수
   - Rate limit 근접도
   - 토큰 사용량

4. **시스템 메트릭**
   - CPU/RAM 사용률
   - 네트워크 대역폭
   - 디스크 I/O

## 문제 해결

### 일반적인 문제

1. **높은 응답 시간**
   - 원인: DGX 서버 과부하
   - 해결: DGX 서버 추가

2. **인증 실패**
   - 원인: API 키 만료/삭제
   - 해결: 새 API 키 발급

3. **Rate limit 초과**
   - 원인: 과도한 요청
   - 해결: Rate limit 조정 또는 캐싱

4. **백엔드 연결 실패**
   - 원인: DGX 서버 다운
   - 해결: 자동 failover (이미 구현됨)

## 백업 및 재해 복구

### 백업 대상
1. **SQLite 데이터베이스 파일**
   - 파일: `tokamak_ai_api.db`
   - 포함 내용: API 키, Usage 로그, Rate limit 데이터
   
2. **환경 설정**
   - `.env` 파일
   - Nginx 설정

### 백업 스크립트
```bash
# 매일 자동 백업
0 2 * * * /opt/tokamak-ai-api/scripts/backup.sh
```

### 복구 절차
1. 새 API 서버 준비
2. 소프트웨어 재설치
3. 데이터베이스 복구
4. 설정 파일 복원
5. 서비스 시작
