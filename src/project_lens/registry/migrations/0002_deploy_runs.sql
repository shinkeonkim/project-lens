-- Phase 1: 실행(clone/inject/PR) 이력 테이블.
-- change_log, tracking_configs, credentials_meta는 각 기능을 구현하는 Phase에서 추가한다.

CREATE TABLE deploy_runs (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id     INTEGER NOT NULL REFERENCES projects(id),
    run_type       TEXT NOT NULL CHECK (run_type IN ('register', 'sync', 'deploy', 'verify', 'report')),
    status         TEXT NOT NULL DEFAULT 'running'
                       CHECK (status IN ('running', 'success', 'failed', 'partial')),
    started_at     TEXT NOT NULL,
    finished_at    TEXT,
    commit_sha     TEXT,
    pr_url         TEXT,
    summary        TEXT,
    error_code     TEXT,
    error_summary  TEXT
);

CREATE INDEX idx_deploy_runs_project_id ON deploy_runs (project_id);
