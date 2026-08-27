-- Phase 2: GA4 웹 데이터 스트림을 만들려면 실제 배포 URL이 필요하다.
-- GitHub URL만으로는 알 수 없으므로 별도 컬럼으로 관리한다.

ALTER TABLE projects ADD COLUMN site_url TEXT;
