# 데이터 모델 (SQLite 레지스트리)

DB 위치: `~/.project-lens/registry.sqlite3` (레포 바깥, git 추적 대상 아님).
민감정보(토큰 등)는 절대 이 DB에 저장하지 않습니다 — GA4/GTM/Ads의 **ID 값**(속성 ID,
컨테이너 ID, 전환 액션 ID 등)만 저장하며, 이는 비밀이 아니라 식별자입니다.

## projects

프로젝트(=하나의 웹사이트 레포) 단위 레지스트리.

| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | INTEGER PK | |
| slug | TEXT UNIQUE | `org-repo` 형태, 커맨드에서 프로젝트 지칭에 사용 |
| name | TEXT | 표시용 이름 |
| github_url | TEXT | 원본 URL |
| github_org | TEXT | `kokoa-lab`, `shinkeonkim` 등 |
| github_repo | TEXT | |
| visibility | TEXT | `public` \| `private` |
| default_branch | TEXT | |
| deployment_type | TEXT | `cloudflare_workers` \| `oh_my_homelab` \| `vercel` \| `github_pages` \| `unknown` |
| deploy_mode | TEXT | `pr`(기본) \| `direct` — 프로젝트별 옵트인 |
| status | TEXT | `pending` \| `active` \| `needs_attention` \| `archived` |
| notes | TEXT | 자유 메모 |
| created_at | TEXT (ISO8601) | |
| updated_at | TEXT (ISO8601) | |

## tracking_configs

프로젝트별 GA4/GTM/Ads 연결 정보. `project_id`에 1:1.

| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | INTEGER PK | |
| project_id | INTEGER FK → projects.id | |
| ga4_property_id | TEXT | |
| ga4_measurement_id | TEXT | `G-XXXXXXX` |
| ga4_stream_id | TEXT | |
| gtm_account_id | TEXT | |
| gtm_container_id | TEXT | `GTM-XXXXXXX` |
| gtm_workspace_id | TEXT | |
| gtm_last_published_version | TEXT | |
| ads_customer_id | TEXT | |
| ads_conversion_action_ids | TEXT (JSON array) | |
| config_version | INTEGER | 스니펫/태그 구성 스키마 버전, drift 감지용 |
| last_synced_at | TEXT (ISO8601) | |

## deploy_runs

명령 실행(등록/동기화/배포/검증) 1회 = 1 row. 감사(audit) 및 `/lens-logs`의 기반.

| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | INTEGER PK | run_id로 사용 |
| project_id | INTEGER FK | |
| run_type | TEXT | `register` \| `sync` \| `deploy` \| `verify` \| `report` |
| status | TEXT | `success` \| `failed` \| `partial` |
| started_at | TEXT | |
| finished_at | TEXT | |
| commit_sha | TEXT | 삽입 커밋(있는 경우) |
| pr_url | TEXT | PR 모드일 때 |
| log_path | TEXT | `~/.project-lens/logs/...jsonl` 경로 |
| error_code | TEXT | 실패 시 에러 타입 |
| error_summary | TEXT | 사람이 읽는 요약 |

## change_log

필드 단위 변경 이력. 프로젝트 간 비교/추후 재구성 시 "무엇이 언제 왜 바뀌었는지" 추적용.

| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | INTEGER PK | |
| project_id | INTEGER FK | |
| run_id | INTEGER FK → deploy_runs.id | |
| field_changed | TEXT | 예: `tracking_configs.gtm_container_id` |
| old_value | TEXT | |
| new_value | TEXT | |
| changed_at | TEXT | |

## credentials_meta — 계획 변경, SQLite 테이블로 구현하지 않음

원래 계획은 자격증명 상태(마지막 검증 시각, 만료 여부)를 SQLite 테이블로 추적하는
것이었으나, 실제 구현에서는 더 단순한 방식을 택했다: `lens creds check`가
`keyring.get_password(...)`(Google OAuth, Ads Developer Token 존재 여부)와
`~/.project-lens/settings.json`(계정 ID 설정 여부)을 그때그때 직접 조회해 보여준다.
비밀 값이 실제로 어디 있는지(keyring)와 상태를 보여주는 곳을 분리하지 않아 더
단순하고, "DB에는 있다는데 실제로는 만료됐다" 같은 동기화 문제도 없다. 이력(언제
발급했는지 등)이 필요해지면 그때 테이블을 추가한다.

## 마이그레이션

스키마 변경은 단순 순번 마이그레이션 스크립트(`src/project_lens/registry/migrations/NNNN_*.sql`)로
관리합니다. 별도 `lens db migrate` 명령은 없습니다 — `connect()`(모든 CLI 명령이 시작할 때
호출)가 매번 적용 안 된 마이그레이션을 자동으로 실행합니다(`registry/db.py`). 별도 ORM 없이
표준 라이브러리 `sqlite3` + 얇은 repository 함수로 구현해 의존성을 최소화합니다.

**CHECK 제약을 바꿔야 할 때** (예: `deployment_type`에 새 값 추가, migration 0005 참고):
SQLite는 `ALTER TABLE`로 CHECK 제약을 직접 못 고칩니다. 새 테이블을 만들어 데이터를
복사하고 기존 테이블을 바꿔치기해야 하는데, 다른 테이블이 그 테이블을 외래키로 참조하면
(`deploy_runs`/`tracking_configs`가 `projects.id`를 참조) `PRAGMA foreign_keys=ON`인 채로
`DROP TABLE`을 하면 `FOREIGN KEY constraint failed`로 막힙니다(실제 데이터로 검증 중
확인됨). 스크립트 앞뒤로 `PRAGMA foreign_keys=OFF;`/`PRAGMA foreign_keys=ON;`으로 감싸야
합니다. **실제 사용자 DB의 사본으로 먼저 검증**한 뒤(레지스트리는 사용자의 실제 프로젝트
이력이 든 진짜 데이터입니다) 적용하세요 — 이 마이그레이션도 그렇게 확인했습니다.
