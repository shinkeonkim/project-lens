-- 광고(AdSense) 게재 대상 여부를 프로젝트별로 명시적으로 관리한다.
-- 기본값은 'unreviewed' — 새로 등록되는 프로젝트가 검토 없이 자동으로 광고 대상에
-- 들어가지 않게 하기 위함이다 (포트폴리오/이력서 같은 개인 브랜드 사이트는 절대
-- 광고를 붙이면 안 된다는 요구사항 때문에, "명시적으로 허용"된 것만 다뤄야 한다).

ALTER TABLE projects ADD COLUMN ads_policy TEXT NOT NULL DEFAULT 'unreviewed'
    CHECK (ads_policy IN ('allowed', 'excluded', 'unreviewed'));
