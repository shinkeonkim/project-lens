---
description: 프로젝트의 GA4(및 연결됐다면 Ads) 성과 지표를 요약해서 보여줍니다
---

`$ARGUMENTS`에서 프로젝트 slug와, 기간을 언급했다면(예: "지난 한 달") `--range 30d`로
매핑하세요 (지원 값: `7d`, `30d`, 기본 `7d`). slug를 모르면 `/lens-list`로 확인하세요.

이 커맨드는 읽기 전용이라 확인 없이 바로 실행해도 됩니다:

```
lens track report <SLUG> [--range 7d|30d]
```

결과(방문자/세션/페이지뷰/이탈률/평균 세션 시간, 연결돼 있으면 Ads 노출수/클릭수/CTR/비용/전환수)를
사람이 읽기 좋게 요약하세요. 값이 전부 0이면 최근 만든 속성이라 아직 데이터가 안 쌓였을
수 있다고 안내하세요.

실패 시:

- "GA4 속성이 없습니다" → 먼저 `/lens-sync`로 GA4를 세팅해야 함을 안내
- 스코프/권한 오류 → `docs/TROUBLESHOOTING.md`의 GoogleAPIError 섹션 참고 (GA4 Data API는
  OAuth 스코프뿐 아니라 GCP 프로젝트에서 API 활성화도 별도로 필요합니다 —
  `docs/SECURITY.md` 2번 섹션)
