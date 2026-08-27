-- Phase 6: Vercel/GitHub Pages 어댑터 추가 — deployment_type CHECK 제약에 값을 더한다.
-- SQLite는 CHECK 제약을 직접 수정할 수 없으므로 표준 방식(새 테이블 생성 → 복사 →
-- 교체)을 쓴다. deploy_runs/tracking_configs가 projects.id를 참조하므로, 재생성하는
-- 동안만 foreign_keys를 끈다 — 켜진 채로 하면 DROP TABLE에서
-- "FOREIGN KEY constraint failed"로 막힌다(실제 데이터로 검증 중 확인됨).

PRAGMA foreign_keys=OFF;

CREATE TABLE projects_new (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    slug            TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    github_url      TEXT NOT NULL,
    github_org      TEXT NOT NULL,
    github_repo     TEXT NOT NULL,
    visibility      TEXT NOT NULL CHECK (visibility IN ('public', 'private')),
    default_branch  TEXT NOT NULL,
    deployment_type TEXT NOT NULL DEFAULT 'unknown'
                        CHECK (deployment_type IN (
                            'cloudflare_workers', 'oh_my_homelab', 'vercel', 'github_pages', 'unknown'
                        )),
    deploy_mode     TEXT NOT NULL DEFAULT 'pr' CHECK (deploy_mode IN ('pr', 'direct')),
    status          TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'active', 'needs_attention', 'archived')),
    notes           TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    site_url        TEXT
);

INSERT INTO projects_new
SELECT id, slug, name, github_url, github_org, github_repo, visibility, default_branch,
       deployment_type, deploy_mode, status, notes, created_at, updated_at, site_url
FROM projects;

DROP TABLE projects;
ALTER TABLE projects_new RENAME TO projects;

PRAGMA foreign_keys=ON;
