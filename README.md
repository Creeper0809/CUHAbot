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

## 비밀값 관리

- `DISCORD_TOKEN`, `DEV_DISCORD_TOKEN`, `DATABASE_PASSWORD`는 로그·이슈·PR에 붙여 넣지 마세요.
- 토큰이 노출됐다면 Discord Developer Portal에서 즉시 재발급하고 기존 토큰을 폐기하세요.
- 서버의 `.env`는 가능하면 소유자만 읽을 수 있도록 권한을 `600`으로 설정하세요.
- Git에는 값이 비어 있는 예제 파일만 올립니다.
