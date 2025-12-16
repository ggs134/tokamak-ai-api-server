# Network Optimization Guide

## 네트워크 구성 권장사항

### 1. 같은 랙/스위치 배치
- API 서버와 DGX 서버들을 같은 10Gbps 스위치에 연결
- 지연시간 목표: < 1ms

### 2. 전용 VLAN 구성
```bash
# API 서버와 Ollama 서버들을 전용 VLAN에 배치
# 예: VLAN 100 - Ollama Infrastructure
# 192.168.100.0/24

API Server:     192.168.100.10
DGX Spark #1:   192.168.100.101
DGX Spark #2:   192.168.100.102
...
DGX Spark #10:  192.168.100.110
```

### 3. MTU 최적화
```bash
# Jumbo frames 활성화 (9000 bytes)
# API 서버에서
sudo ip link set dev eth0 mtu 9000

# 각 DGX 서버에서도 동일하게 설정
```

### 4. TCP 튜닝 (API 서버)
```bash
# /etc/sysctl.conf에 추가
net.core.rmem_max = 134217728
net.core.wmem_max = 134217728
net.ipv4.tcp_rmem = 4096 87380 67108864
net.ipv4.tcp_wmem = 4096 65536 67108864
net.core.netdev_max_backlog = 5000
net.ipv4.tcp_congestion_control = bbr

# 적용
sudo sysctl -p
```

### 5. 네트워크 성능 테스트

#### 지연시간 측정
```bash
# API 서버에서 각 DGX로 ping
for i in {101..110}; do
  ping -c 10 192.168.100.$i | tail -1
done

# 목표: avg < 1ms
```

#### 대역폭 측정
```bash
# DGX 서버에서 iperf3 서버 실행
iperf3 -s

# API 서버에서 테스트
iperf3 -c 192.168.100.101 -t 10 -P 4

# 목표: 9+ Gbps (10GbE 네트워크)
```

#### HTTP 성능 테스트
```bash
# Apache Bench로 Ollama 직접 테스트
ab -n 100 -c 10 -p prompt.json -T application/json \
   http://192.168.100.101:11434/api/generate

# prompt.json:
# {"model": "deepseek-coder:33b", "prompt": "test", "stream": false}
```

### 6. 방화벽 최적화

#### API 서버
```bash
# 불필요한 conntrack 비활성화 (내부 트래픽)
sudo iptables -t raw -A PREROUTING -s 192.168.100.0/24 -j NOTRACK
sudo iptables -t raw -A OUTPUT -d 192.168.100.0/24 -j NOTRACK
```

#### DGX 서버들
```bash
# API 서버만 허용
sudo ufw allow from 192.168.100.10 to any port 11434
sudo ufw default deny incoming
sudo ufw enable
```

### 7. Keep-Alive 최적화

API 서버의 httpx 클라이언트 설정:
```python
# app/load_balancer.py 수정
async with httpx.AsyncClient(
    timeout=600.0,
    limits=httpx.Limits(
        max_keepalive_connections=100,
        max_connections=200,
        keepalive_expiry=30.0
    )
) as client:
    ...
```

### 8. 모니터링

#### 실시간 네트워크 모니터링
```bash
# API 서버에서
sudo apt install iftop
sudo iftop -i eth0

# 또는 nload
sudo apt install nload
nload eth0
```

#### Prometheus 메트릭
```python
# app/monitoring.py에 추가
network_latency = Histogram(
    'ollama_backend_network_latency_ms',
    'Network latency to backend',
    ['server']
)
```

### 9. 트러블슈팅

#### 높은 지연시간 (>5ms)
```bash
# 네트워크 경로 확인
traceroute 192.168.100.101

# 스위치 포트 확인
# 같은 스위치에 연결되어 있는지 확인
```

#### 패킷 손실
```bash
# 패킷 손실 확인
ping -c 100 192.168.100.101 | grep loss

# 인터페이스 에러 확인
ip -s link show eth0
```

#### 대역폭 병목
```bash
# 현재 대역폭 사용량
sudo iftop -i eth0 -n -P

# 예상 트래픽 계산:
# 30명 동시 사용 × 평균 1MB 응답 = 30MB/s = 240Mbps
# 10GbE는 충분함
```

### 10. 베스트 프랙티스

✅ **권장 구성**
- API 서버와 DGX: 같은 10GbE 스위치
- 전용 VLAN: 내부 트래픽 격리
- Jumbo Frames: 9000 MTU
- Keep-Alive: 연결 재사용

❌ **피해야 할 것**
- 방화벽을 API↔DGX 사이에 두지 말 것
- NAT 사용하지 말 것 (직접 라우팅)
- 무선 연결 사용 금지
- 다른 데이터센터에 배치 금지

### 예상 성능

최적 구성 시:
- **네트워크 지연**: 0.3-0.8ms
- **요청 오버헤드**: API 서버 2-5ms + 네트워크 1ms = 총 3-6ms
- **LLM 추론 시간**: 10-30초 (모델 크기에 따라)
- **총 응답 시간**: 추론 시간이 압도적 (99.9%)

결론: 네트워크를 최적화해도 전체 응답 시간의 0.1% 미만이므로,
       일반적인 1GbE 네트워크도 충분합니다.
