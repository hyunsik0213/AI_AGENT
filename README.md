# FastAPI Agent + Mock Spring API (Toy Project)

## 1) 실행 전 준비 (Git Bash)

```bash
cd /c/Users/<you>/OneDrive/바탕\ 화면/etc/공부용/AI_AGENT
cp .env.example .env
```

`.env` 예시:

```env
# 포트 충돌 나면 여기 숫자만 바꾸면 됨
AGENT_HOST_PORT=8000
MOCK_HOST_PORT=8001

AGENT_TOKEN=agent_admin_token
INTENT_MODE=gemini
GEMINI_API_KEY=여기에_실제_키
GEMINI_MODEL=gemini-2.0-flash
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta
```

## 2) 실행 (Docker)

```bash
docker compose up --build
```

## 3) 확인 (Git Bash)

> `ccurl` 아님, 반드시 `curl`

```bash
curl http://127.0.0.1:8000/health
```

`AGENT_HOST_PORT`를 바꿨다면 그 포트로 호출:

```bash
curl http://127.0.0.1:${AGENT_HOST_PORT}/health
```

툴 선정만 확인:

```bash
curl -X POST http://127.0.0.1:8000/chat/command/plan \
  -H "Content-Type: application/json" \
  -d '{"message":"@AI 2주동안 합주에 참석하지 않은 팀원들 목록 조회해줘"}'
```

실행까지:

```bash
curl -X POST http://127.0.0.1:8000/chat/command \
  -H "Content-Type: application/json" \
  -d '{"message":"@AI 3/28 운영자 회의 일정 추가해줘"}'
```

## 4) 지금 발생한 오류 해결 가이드

### 오류 A) `Bind for 0.0.0.0:8000 failed: port is already allocated`

의미: 8000 포트를 이미 다른 프로세스가 사용 중.

해결 1 (권장): `.env`에서 포트 변경
```env
AGENT_HOST_PORT=8002
```
그 후 재실행:
```bash
docker compose down
docker compose up --build
```

해결 2: 점유 프로세스 종료
```bash
# Windows Git Bash에서
netstat -ano | findstr :8000
# 마지막 PID 확인 후
taskkill //PID <PID번호> //F
```

### 오류 B) `curl /health`가 `{"detail":"Not Found"}`

의미: 8000에서 **다른 서버**가 응답 중일 가능성이 큼.

확인:
```bash
docker compose ps
```
`agent`가 어떤 host port로 바인딩됐는지 보고 그 포트로 호출.

### 경고) `version is obsolete`

`docker-compose.yml`의 `version` 필드 경고라 동작에는 큰 문제 없지만,
이 레포에서는 이미 제거해두었습니다.

## 5) Swagger 경로

- Agent: `http://127.0.0.1:<AGENT_HOST_PORT>/docs`
- Mock: `http://127.0.0.1:<MOCK_HOST_PORT>/docs`

## 6) Git 반영

```bash
git status
git add .
git commit -m "Fix docker port binding config and troubleshooting docs"
git push origin <브랜치명>
```
