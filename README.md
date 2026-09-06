# CUHABot

Discord 기반 RPG 봇입니다. 봇을 실행하기 전에 프로젝트 루트에 `.env` 파일을 만들고 Discord 및 PostgreSQL 접속 정보를 설정해야 합니다.

> `.env`에는 봇 토큰과 DB 비밀번호가 들어갑니다. Git에 커밋하지 마세요. 저장소의 `.gitignore`는 `.env`를 제외하도록 설정되어 있습니다.

## 기본 `.env` 예시

운영 봇을 실행할 때 사용하는 최소 설정입니다.

```dotenv
DEV=FALSE
FORCE_SYNC=FALSE

GUILD_ID=123456789012345678
APPLICATION_ID=123456789012345678
DISCORD_TOKEN=여기에_운영_봇_토큰

DATABASE_URL=db
DATABASE_PORT=5432
DATABASE_USER=cuhabot
DATABASE_PASSWORD=충분히_긴_비밀번호
DATABASE_TABLE=cuhabot

ROGUELIKE_DUNGEON_DEFAULT_ENABLED=TRUE
BOX_REVEAL_ENABLED=TRUE
ITEMIZATION_V4_ENABLED=TRUE
FARMING_FOCUS_ENABLED=TRUE
CRAFTING_V4_ENABLED=TRUE
BUILD_PRESETS_V4_ENABLED=TRUE
SET_EFFECTS_V4_ENABLED=TRUE
```

로컬에서 PostgreSQL을 직접 실행한다면 `DATABASE_URL=127.0.0.1`처럼 설정합니다. Compose로 실행할 때는 PostgreSQL 서비스 이름인 `db` 또는 `e2e-db`를 사용합니다.

## Discord 및 실행 모드

| 필드 | 필수 여부 | 넣어야 하는 값 | 용도 |
|---|---|---|---|
| `DEV` | 선택 | `TRUE` 또는 `FALSE` | `TRUE`이면 운영 봇 정보 대신 `DEV_APPLICATION_ID`와 `DEV_DISCORD_TOKEN`을 사용합니다. 기본적으로 `FALSE`로 두는 것이 안전합니다. |
| `GUILD_ID` | 필수 | Discord 서버 ID | 슬래시 명령을 등록하고 E2E 대상 서버를 판별할 Guild ID입니다. Discord 개발자 모드를 켠 뒤 서버의 **서버 ID 복사**로 확인합니다. |
| `APPLICATION_ID` | 운영 모드에서 필수 | Discord Application ID | `DEV`가 `TRUE`가 아닐 때 사용할 운영 애플리케이션 ID입니다. Discord Developer Portal의 **General Information → Application ID**에서 확인합니다. |
| `DISCORD_TOKEN` | 운영 모드에서 필수·비밀 | 운영 Bot Token | `DEV`가 `TRUE`가 아닐 때 로그인할 봇 토큰입니다. Discord Developer Portal의 **Bot** 메뉴에서 발급합니다. |
| `DEV_APPLICATION_ID` | 개발 모드에서 필수 | 개발 Discord Application ID | `DEV=TRUE`일 때 사용할 개발 애플리케이션 ID입니다. |
| `DEV_DISCORD_TOKEN` | 개발 모드에서 필수·비밀 | 개발 Bot Token | `DEV=TRUE`일 때 로그인할 개발 봇 토큰입니다. |
| `FORCE_SYNC` | 선택 | `TRUE` 또는 `FALSE` | `TRUE`이면 시작할 때 대상 Guild의 슬래시 명령을 다시 동기화합니다. 명령 변경을 반영한 뒤에는 불필요한 반복 동기화를 막기 위해 `FALSE`로 돌리는 것을 권장합니다. |

`DEV`, `FORCE_SYNC`, `E2E_API_ENABLED` 등 기존 실행 모드 필드는 코드에서 문자열 `TRUE`를 기준으로 판정합니다. 문서 예제처럼 대문자 `TRUE`/`FALSE`를 사용하세요.

## PostgreSQL

| 필드 | 필수 여부 | 넣어야 하는 값 | 용도 |
|---|---|---|---|
| `DATABASE_URL` | 필수 | 호스트명 또는 IP | PostgreSQL 서버 주소입니다. 이름과 달리 `postgres://...` 전체 URL이 아니라 `db`, `127.0.0.1` 같은 **호스트만** 입력합니다. |
| `DATABASE_PORT` | 필수 | 보통 `5432` | PostgreSQL 접속 포트입니다. |
| `DATABASE_USER` | 필수 | PostgreSQL 사용자명 | 봇과 마이그레이션이 사용할 DB 계정입니다. |
| `DATABASE_PASSWORD` | 필수·비밀 | DB 계정 비밀번호 | `DATABASE_USER`의 비밀번호입니다. NAS Compose에서는 PostgreSQL 컨테이너의 초기 비밀번호로도 사용됩니다. |
| `DATABASE_TABLE` | 필수 | PostgreSQL 데이터베이스명 | 실제로는 테이블명이 아니라 접속할 **데이터베이스 이름**입니다. 예: `cuhabot`, `cuhabot_e2e_test`. |

## 게임 기능 플래그

아래 값은 모두 선택 사항이며, 지정하지 않으면 기본적으로 비활성화됩니다. `TRUE`, `YES`, `ON`, `1`을 활성 값으로 인식하지만 일관성을 위해 `TRUE`/`FALSE` 사용을 권장합니다. Guild 관리 명령으로 별도 설정한 값이 있으면 Guild 설정이 환경변수보다 우선합니다.

| 필드 | 기능 |
|---|---|
| `ROGUELIKE_DUNGEON_DEFAULT_ENABLED` | 일반 던전의 8방 경로 선택·스킬 개조·보스 구조를 기본 활성화합니다. |
| `BOX_REVEAL_ENABLED` | 상자 단계별 공개 연출과 통합 천장 처리를 활성화합니다. |
| `ITEMIZATION_V4_ENABLED` | 장비 등급별 랜덤 옵션과 V4 장비 시스템을 활성화합니다. |
| `FARMING_FOCUS_ENABLED` | 목표 파밍, 지역 진척도, 인장 보상을 활성화합니다. |
| `CRAFTING_V4_ENABLED` | 분해, 재련, 계승, 지역 장비 제작 기능을 활성화합니다. |
| `BUILD_PRESETS_V4_ENABLED` | 장비·스탯·스킬을 함께 저장하는 통합 빌드 프리셋을 활성화합니다. |
| `SET_EFFECTS_V4_ENABLED` | 명시적 `set_key`를 사용하는 V4 세트 효과를 활성화합니다. |

## NAS 배포용 `.env.nas`

NAS에서는 `/volume1/docker/cuhabot/.env.nas`를 사용합니다. 기본 필드는 일반 `.env`와 같으며 다음 값만 추가로 사용할 수 있습니다.

| 필드 | 필수 여부 | 기본값 | 용도 |
|---|---|---|---|
| `CUHABOT_DATA_ROOT` | 선택 | `/volume1/docker/cuhabot` | PostgreSQL 데이터 디렉터리의 NAS 호스트 경로입니다. `docker-compose.nas.yml`을 다른 위치에서 운영할 때만 변경합니다. |

NAS에서는 `DATABASE_URL=db`, `DATABASE_PORT=5432`로 둡니다. `.env.nas` 권한은 `600`으로 제한하세요. 자세한 절차는 [NAS 배포 문서](docs/nas-deployment.md)를 참고하세요.

## Discord E2E 전용 `.env.e2e`

실제 Discord Gateway·메시지·컴포넌트와 격리 PostgreSQL을 검사할 때만 필요합니다. [`.env.e2e.example`](.env.e2e.example)을 `.env.e2e`로 복사해 사용하며, 운영 봇과 운영 DB 정보는 넣지 마세요.

| 필드 | 필수 여부 | 기본값/형식 | 용도 |
|---|---|---|---|
| `E2E_ENABLED` | E2E에서 필수 | `TRUE` | 봇의 E2E 명령과 검증 경로를 활성화합니다. |
| `E2E_API_ENABLED` | 테스트 API 사용 시 필수 | `TRUE` | 봇 프로세스 안에서 E2E HTTP API를 시작합니다. 운영에서는 반드시 `FALSE`로 둡니다. |
| `E2E_FORCE_TEMP_ADMIN` | 선택 | `FALSE` 권장 | 테스트 실행 중 격리 테스트 계정에만 필요한 관리자 조건을 임시 적용합니다. 개발 Guild에서만 사용하세요. |
| `E2E_CHANNEL_ID` | 필수 | Discord 채널 ID | 드라이버 봇이 명령을 보내고 결과 메시지를 확인할 테스트 채널입니다. |
| `MCP_BOT_ID` | 필수 | 드라이버 Bot의 사용자 ID | 개발 봇이 허용할 E2E 드라이버 봇을 식별합니다. Application ID가 아니라 Discord Bot 사용자 ID를 넣습니다. |
| `MCP_TOKEN` | 필수·비밀 | 드라이버 Bot Token | 실제 명령을 전송하는 별도 드라이버 봇의 토큰입니다. 테스트 대상인 `DEV_DISCORD_TOKEN`과 달라야 합니다. |
| `E2E_API_TOKEN` | 필수·비밀 | 임의의 긴 난수 문자열 | `/v1/test-runs` API 호출에 사용하는 Bearer 토큰입니다. Discord 토큰이 아닙니다. |
| `E2E_API_BIND` | 선택 | `0.0.0.0` | 컨테이너 내부 API 바인드 주소입니다. Compose는 호스트의 `127.0.0.1:8765`에만 공개합니다. 직접 실행한다면 `127.0.0.1`을 권장합니다. |
| `E2E_API_PORT` | 선택 | `8765` | E2E HTTP API 포트입니다. |
| `E2E_QUEUE_SIZE` | 선택 | `10` | 동시에 대기할 수 있는 테스트 실행의 최대 개수입니다. 실제 실행은 FIFO 단일 워커로 처리됩니다. |
| `E2E_RUN_TIMEOUT_SECONDS` | 선택 | `900` | 테스트 한 건의 최대 실행 시간(초)입니다. |
| `E2E_DUNGEON_MAX_STEPS` | 선택 | `1` | E2E 자동 진행 시 일반 던전에서 실행할 최대 단계 수입니다. |
| `E2E_TOWER_MAX_FLOORS` | 선택 | `1` | E2E 자동 진행 시 타워에서 진행할 최대 층 수입니다. |
| `E2E_MINIGAME_AUTOPILOT` | 선택 | `FALSE` | 미니게임의 사람 입력을 테스트 자동 응답으로 대체합니다. |
| `E2E_UI_AUTOPILOT` | 직접 설정하지 않음 | 런타임 내부 관리 | Discord 버튼/선택 대기를 자동화하는 내부 플래그입니다. 테스트 러너가 실행 중에 설정하며 운영 `.env`에는 넣지 않습니다. |

E2E에서는 위 필드와 함께 다음 값을 사용합니다.

```dotenv
DEV=TRUE
GUILD_ID=테스트_Guild_ID
DEV_APPLICATION_ID=개발_Application_ID
DEV_DISCORD_TOKEN=개발_Bot_Token

DATABASE_URL=e2e-db
DATABASE_PORT=5432
DATABASE_USER=cuhabot_e2e
DATABASE_PASSWORD=격리_DB_비밀번호
DATABASE_TABLE=cuhabot_e2e_test

E2E_ENABLED=TRUE
E2E_API_ENABLED=TRUE
E2E_CHANNEL_ID=테스트_채널_ID
MCP_BOT_ID=드라이버_Bot_사용자_ID
MCP_TOKEN=드라이버_Bot_Token
E2E_API_TOKEN=임의의_긴_API_토큰
```

## 비밀값 관리

- `DISCORD_TOKEN`, `DEV_DISCORD_TOKEN`, `MCP_TOKEN`, `DATABASE_PASSWORD`, `E2E_API_TOKEN`은 로그·이슈·PR에 붙여 넣지 마세요.
- 토큰이 노출됐다면 Discord Developer Portal에서 즉시 재발급하고 기존 토큰을 폐기하세요.
- 서버의 `.env`, `.env.nas`, `.env.e2e`는 가능하면 소유자만 읽을 수 있도록 권한을 `600`으로 설정하세요.
- Git에는 값이 비어 있는 예제 파일만 올립니다.
