# Google Ads 연동 매뉴얼

project-lens가 Google Ads와 하는 일은 두 가지뿐입니다: **(1) GA4 속성을 Ads 계정에
연결**하고 **(2) 웹페이지 전환 액션을 만드는 것**. 캠페인 생성이나 입찰 관리 같은 건
하지 않습니다 — 이 문서는 그 두 가지를 설정하는 절차입니다.

전체 아키텍처는 [`ARCHITECTURE.md`](ARCHITECTURE.md), 코드는 `google/ads.py`/
`google/ga4.py`의 `ensure_google_ads_link`, CLI는 `lens track link-ads`를 참고하세요.
자격증명 저장 위치 등 보안 관련 사항은 [`SECURITY.md`](SECURITY.md) 3번 섹션에 이미
정리돼 있습니다 — 이 문서는 그걸 실제로 따라가는 단계별 가이드입니다.

## 0. 미리 알아둘 것

- **Developer Token 승인에는 시간이 걸립니다** (수일). 아래 1번을 최대한 먼저
  신청해두고 기다리는 동안 나머지(GA4-Ads 연결)는 Developer Token 없이도 할 수
  있는 부분부터 진행하세요 (3번).
- **테스트 계정은 승인 없이 즉시 쓸 수 있습니다.** Basic Access 승인 전에 전체
  흐름을 미리 검증해보고 싶다면, Google Ads의 "테스트 관리자 계정"을 하나 만들어
  그 Developer Token(자동 발급, Test Account Access 등급)으로 먼저 연습해볼 수
  있습니다. 다만 테스트 계정은 실제 캠페인 데이터가 없으므로 전환 액션이 생성되는
  것만 확인 가능하고, 실제 전환 추적 검증은 결국 운영 계정 승인 후 해야 합니다.

## 1. Developer Token 신청

1. https://ads.google.com 에서 실제로 광고를 운영(또는 운영 예정)할 Google Ads
   계정에 로그인
2. 오른쪽 위 "도구 및 설정(스패너 아이콘) > 설정 > API 센터" 이동
   (계정이 MCC/관리자 계정이 아니면 API 센터가 없을 수 있습니다 — 이 경우 먼저
   관리자 계정을 만들거나, 기존 관리자 계정 아래로 이 계정을 연결해야 합니다)
3. "API 액세스" 신청 → 아래 정보를 입력해 **Basic Access** 신청
   - 사용 목적: 자체 웹사이트들의 전환 추적 자동화(개인/스터디 프로젝트) 같은 실제
     용도를 간단히 설명
   - 앱 이름: 자유롭게 (예: "project-lens")
4. 제출 후 심사 대기. 승인되면 API 센터에 **Developer Token** 문자열이 표시됩니다
   (`xxxxxxxxxxxxxxxxxxxxxx` 형태의 22자 문자열) — 이 값을 복사해두세요. 이건
   OAuth와 별개로 **project-lens가 지금 당장 저장할 수 있는 값**입니다.

## 2. project-lens에 Developer Token 등록

```bash
lens creds init --provider google-ads --developer-token <위에서 받은 토큰>
```

MCC(관리자 계정) 아래에 실제로 광고를 운영할 계정이 따로 있는 구조라면
`--login-customer-id`도 함께 넘기세요 (관리자 계정의 customer ID, 하이픈 없이 숫자만):

```bash
lens creds init --provider google-ads --developer-token <토큰> --login-customer-id 1234567890
```

## 3. OAuth 재인증 (Ads API 스코프 추가)

Google Ads API는 `analytics.edit`/`tagmanager.*`와는 별도로
`https://www.googleapis.com/auth/adwords` 스코프가 필요합니다. **1번을 기다리는 동안
미리 해둬도 됩니다** — 이 단계는 Developer Token과 무관하게 언제든 실행 가능합니다.

```bash
lens creds init --provider google
```

브라우저가 열리며 다시 동의 화면이 뜹니다. 이미 GA4/GTM 인증이 돼 있었다면 "재인증"이라는
느낌 없이 그냥 한 번 더 통과하면 됩니다.

## 4. 상태 확인

```bash
lens creds check
```

`google ads developer token: ok`가 나오면 준비가 끝난 겁니다. `ads_login_customer_id`는
2번에서 `--login-customer-id`를 안 넘겼다면 `(미설정, MCC 아닐 시 불필요)`로 나오는 게
정상입니다.

## 5. GA4 속성을 Ads 계정에 연결 (Developer Token 승인 전에도 가능)

이 단계는 GA4 Admin API만 쓰므로 **Developer Token이 없어도 됩니다.** 대상 프로젝트가
먼저 `lens track sync <slug> --yes`로 GA4 속성이 만들어져 있어야 합니다(`lens project
show <slug>`로 확인).

Ads customer ID를 모르면 https://ads.google.com 화면 오른쪽 위에서 확인하세요
(`123-456-7890` 형태로 표시됩니다 — project-lens에는 하이픈 빼고 숫자만 넘깁니다).

```bash
lens track link-ads <slug> --customer-id 1234567890          # dry-run으로 먼저 확인
lens track link-ads <slug> --customer-id 1234567890 --yes    # 실제로 연결
```

Developer Token이 아직 없으면 GA4-Ads 연결만 되고 전환 액션 생성은 자동으로 건너뜁니다
(dry-run 출력에 "Developer Token이 없어 전환 액션 생성은 건너뜁니다"라고 명확히 나옵니다).

## 6. 전환 액션 생성 (Developer Token 승인 후)

Developer Token이 등록돼 있으면 5번의 같은 명령이 전환 액션도 함께 만듭니다 — 별도
명령이 없습니다. 다시 실행하면 됩니다:

```bash
lens track link-ads <slug> --customer-id 1234567890 --yes
```

생성되는 전환 액션은 **웹페이지 전환(WEBPAGE), 카테고리 기본값(DEFAULT), 상태
활성(ENABLED)**입니다(`google/ads.py`). 이름은 `<slug> conversion`. 전환을 실제로
발생시키려면(예: 특정 버튼 클릭이나 폼 제출을 전환으로 잡기) GTM에서 별도로 트리거·태그를
설정해야 합니다 — project-lens는 전환 "액션"(Ads 쪽 정의)만 만들고, 그걸 실제로 언제
발생시킬지(GTM 쪽 이벤트 트래킹)는 아직 자동화 범위 밖입니다
(`docs/ROADMAP.md`의 "클릭/폼 제출/스크롤 이벤트 태그" 미구현 항목과 연결됨).

`tracking_configs.ads_conversion_action_ids`에 리소스 이름이 쌓이므로,
`lens project show <slug>`로 어떤 전환 액션이 연결됐는지 나중에도 확인할 수 있습니다.

## 문제 해결

일반적인 에러 타입(AuthError, GoogleAPIError, ValidationError)은
[`TROUBLESHOOTING.md`](TROUBLESHOOTING.md)를 먼저 보세요. Ads 특유의 증상:

| 증상 | 원인/조치 |
|---|---|
| `invalid_scope`/`invalid_client`로 인증 실패 | 3번(OAuth 재인증)을 아직 안 했습니다 |
| `DEVELOPER_TOKEN_NOT_APPROVED` 류 메시지 | 1번 신청이 아직 승인 대기 중입니다. `lens track link-ads`는 계속 GA4-Ads 연결만 하고 전환 액션은 건너뜁니다 — 오류가 아니라 정상 동작입니다 |
| `USER_PERMISSION_DENIED` | 로그인한 Google 계정이 해당 Ads customer ID에 대한 권한이 없습니다. Ads 계정의 "액세스 및 보안"에서 확인 |
| customer ID 관련 오류 | 하이픈(`-`) 없이 숫자만 넘겼는지 확인 |
| MCC 구조인데 계속 권한 오류 | `--login-customer-id`를 관리자 계정 ID로 다시 설정 (2번 다시 실행) |

## 다음에 확인할 것

- Developer Token 승인되면 실제 계정으로 `lens track link-ads` 라이브 검증 1회 필요
  (`docs/ROADMAP.md` Phase 3 — 지금까지는 fake 기반 단위 테스트로만 검증됨)
- 성과 리포트(방문자/전환율/광고비 통합)는 `lens track report`, 자세한 내용은
  [`ARCHITECTURE.md`](ARCHITECTURE.md)와 `docs/ROADMAP.md` Phase 3 참고
