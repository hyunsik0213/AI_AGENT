# FastAPI Agent + Mock Spring API (Toy Project)

3일 토이 프로젝트를 위한 최소 구성입니다.

- `services/mock_spring`: Spring 서버 역할을 흉내내는 Mock API
- `services/agent`: 자연어를 해석해 적절한 API(툴)를 선택/호출하는 FastAPI Agent
- `data/*.json`: 임시 저장소(JSON 기반 persistence)

## 프로젝트 구조

```text
.
├── docker-compose.yml
├── services
│   ├── agent
│   │   ├── Dockerfile
│   │   ├── main.py
│   │   └── tooling.py
│   └── mock_spring
│       ├── Dockerfile
│       └── main.py
└── data
    ├── activities.json
    ├── members.json
    ├── schedules.json
    └── tokens.json
```

## 1) 실행 (Gemini 모드)

```bash
cp .env.example .env
```

`.env` 예시:

```env
AGENT_TOKEN=agent_admin_token
INTENT_MODE=gemini
GEMINI_API_KEY=여기에_실제_키
GEMINI_MODEL=gemini-2.0-flash
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta
```

실행:

```bash
docker compose up --build
```

- Agent: `http://127.0.0.1:8000`
- Mock Spring API: `http://127.0.0.1:8001`

## 2) Swagger에서 확인

- Agent Swagger: `http://127.0.0.1:8000/docs`
- Mock Swagger: `http://127.0.0.1:8001/docs`

Agent Swagger에서:
1. `POST /chat/command/plan` → 자연어로 **의도 + 선정 툴** 먼저 확인
2. `POST /chat/command` → **툴 호출 실행 + 결과 반환**까지 확인

## 3) 터미널 테스트 명령

헬스체크:

```bash
curl http://127.0.0.1:8000/health
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

## 4) Git 반영 방법

```bash
# 1) 상태 확인
git status

# 2) 스테이징
git add .

# 3) 커밋
git commit -m "Update agent tool planning and Gemini flow"

# 4) 원격 브랜치 푸시
git push origin <브랜치명>
```

푸시 후 GitHub에서 해당 브랜치로 `Compare & pull request` 버튼이 뜹니다.

## 5) FAQ

### Q1. GitHub에서 New Pull Request가 안 뜨는 이유?

대부분 아래 중 하나입니다.

1. 로컬 커밋을 원격에 아직 안 올림 (`git push` 안 함)
2. 기본 브랜치와 동일해서 diff가 없음
3. 권한/리포지토리 원격 설정 문제 (`git remote -v` 확인)

확인 명령:

```bash
git branch --show-current
git remote -v
git log --oneline -n 5
```

### Q2. 자연어 보고 툴도 AI가 선정해야 하지 않나?

맞습니다. 그래서 Agent에 툴 카탈로그(`tooling.py`)를 분리했고,
- `INTENT_MODE=gemini`일 때는 Gemini가 의도 + 툴 선정에 참여,
- 선정 결과는 백엔드에서 허용한 API 목록(`/apis`)과 교차 검증 후 실행합니다.

### Q3. Swagger에서 자연어 넣으면 툴 선정부터 실행/반환까지 되나?

네. Agent Swagger에서
- `/chat/command/plan`은 **선정 단계** 확인,
- `/chat/command`는 **실행 및 반환** 확인용입니다.

## 워크플로우 요약

1. Agent가 `GET /apis`로 사용 가능한 API 목록 조회
2. 자연어 의도 파악 (rule 또는 gemini)
3. 툴 선정 (규칙 기반 또는 gemini + 검증)
4. 툴 호출 실행
5. 결과 반환

