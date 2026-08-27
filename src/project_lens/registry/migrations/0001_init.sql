-- Phase 0: 프로젝트 레지스트리 기본 테이블.
-- 나머지 테이블(tracking_configs, deploy_runs, change_log, credentials_meta)은
-- 해당 기능을 구현하는 Phase에서 후속 마이그레이션으로 추가한다 (docs/DATA_MODEL.md 참고).

CREATE TABLE projects (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    slug            TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    github_url      TEXT NOT NULL,
    github_org      TEXT NOT NULL,
    github_repo     TEXT NOT NULL,
    visibility      TEXT NOT NULL CHECK (visibility IN ('public', 'private')),
    default_branch  TEXT NOT NULL,
    deployment_type TEXT NOT NULL DEFAULT 'unknown'
                        CHECK (deployment_type IN ('cloudflare_workers', 'oh_my_homelab', 'unknown')),
    deploy_mode     TEXT NOT NULL DEFAULT 'pr' CHECK (deploy_mode IN ('pr', 'direct')),
    status          TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'active', 'needs_attention', 'archived')),
    notes           TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
