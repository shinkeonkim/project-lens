-- Phase 2: 프로젝트별 GA4/GTM(추후 Ads) 연결 정보. docs/DATA_MODEL.md 참고.
-- 여기 저장되는 값은 전부 식별자(ID)이며 비밀 값이 아니다.

CREATE TABLE tracking_configs (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id                  INTEGER NOT NULL UNIQUE REFERENCES projects(id),
    ga4_account_id              TEXT,
    ga4_property_id             TEXT,
    ga4_measurement_id          TEXT,
    ga4_stream_id               TEXT,
    gtm_account_id              TEXT,
    gtm_container_id            TEXT,
    gtm_workspace_id            TEXT,
    gtm_last_published_version  TEXT,
    ads_customer_id             TEXT,
    ads_conversion_action_ids   TEXT NOT NULL DEFAULT '[]',
    config_version              INTEGER NOT NULL DEFAULT 1,
    last_synced_at              TEXT NOT NULL
);
