# 보안 및 자격증명 관리

원칙: **project-lens 레포에는 어떤 비밀 값도 커밋되지 않습니다.** 코드/문서만 git으로
관리하고, 실제 자격증명은 로컬 머신(`~/.project-lens/credentials/`)이나 OS 키체인에만
존재합니다. 아래는 필요한 자격증명 목록과 발급/보관 절차입니다.

## 필요한 자격증명

| 용도 | 종류 | 보관 위치 |
|---|---|---|
| GitHub 레포 접근(clone, PR 생성) | 기존 `gh auth login` 세션 재사용 | `gh` 자체 관리 (별도 저장 안 함) |
| GA4 Admin API | Google Cloud OAuth 클라이언트 + refresh token | OS keyring (`keyring` 패키지) |
| Google Tag Manager API | 위와 동일 OAuth 클라이언트 공유 가능 | 동일 |
| Google Ads API | OAuth refresh token + **Developer Token** + (있다면) `login-customer-id` | keyring + `~/.project-lens/credentials/google-ads.yaml` (chmod 600) |
| Cloudflare Workers 직접 배포(옵트인 시) | Cloudflare API Token | keyring, 없으면 `direct` 모드 자동 비활성화 |

## 1. GitHub

이미 로컬에 `gh auth login`이 되어 있다면 추가 설정이 필요 없습니다. project-lens는 자체
토큰을 발급하지 않고 `gh` CLI가 관리하는 세션을 그대로 subprocess로 사용합니다.

```bash
gh auth status      # 로그인 여부 확인
gh auth login        # 안 되어 있으면 로그인 (SSO 필요한 조직은 추가로 gh auth refresh -h github.com -s ... )
```

private 레포(kokoa-lab, kokoa-study-room 조직 등)는 해당 조직에 대한 접근 권한이 계정에
있어야 합니다. `/lens-creds-setup` 실행 시 `gh repo view <url>`로 접근 가능 여부를 사전 점검합니다.

## 2. Google Cloud 프로젝트 준비 (최초 1회)

1. GCP 콘솔(console.cloud.google.com)에서 project-lens 전용 프로젝트 생성 (예: `project-lens-automation`)
2. "API 및 서비스 > 라이브러리"에서 다음 API 활성화:
   - Google Analytics Admin API
   - Google Analytics Data API (`lens track report`의 방문자/세션 등 리포트 조회에 필요 —
     OAuth 스코프(`analytics.readonly`)와 별개로 GCP 프로젝트에서도 따로 활성화해야 함,
     안 해두면 `SERVICE_DISABLED` 오류)
   - Tag Manager API
   - (Phase 3용, 미리 활성화해도 무방) Google Ads API
3. "API 및 서비스 > OAuth 동의 화면" 구성 (User Type: 외부 또는 내부 무관, 테스트 모드로 충분 —
   테스트 사용자로 본인 Google 계정만 추가)
4. "API 및 서비스 > 사용자 인증 정보 > OAuth 클라이언트 ID 만들기" (애플리케이션 유형: **데스크톱 앱**)
   → JSON 다운로드
5. 다운로드한 JSON을 아래 경로에 그대로 저장 (파일명 고정):

```bash
mkdir -p ~/.project-lens/credentials
mv ~/Downloads/client_secret_*.json ~/.project-lens/credentials/google_oauth_client.json
chmod 600 ~/.project-lens/credentials/google_oauth_client.json
```

6. 로컬에서 최초 1회 인증 플로우 실행 (브라우저가 열리며 GA4/GTM scope 동의 필요):

```bash
lens creds init --provider google
```

성공하면 refresh token이 포함된 credentials가 OS 키체인(`keyring`)에 저장되고, 이후 CLI
실행 시마다 자동으로 읽어와 만료 시 갱신합니다. `google_oauth_client.json`은 keyring과 달리
평문 로컬 파일로 남아있지만 `~/.project-lens/` 아래(project-lens 레포 바깥)에 있고
`.gitignore`의 `credentials/` 규칙으로 실수 커밋을 방지합니다.

7. GA4/GTM 자동 생성 시 사용할 기본 계정을 확인하고 저장:

```bash
lens creds accounts        # 접근 가능한 GA4/GTM 계정 목록 조회
lens creds set-accounts --ga4-account-id <GA4_ACCOUNT_ID> --gtm-account-id <GTM_ACCOUNT_ID>
lens creds check           # 전체 상태 확인
```

**여러 GA4/GTM 계정을 구분해 써야 한다면** (예: 개인 프로젝트는 개인 계정, 스터디 랩
프로젝트는 랩 계정) `--profile`로 이름 붙인 프로필을 추가로 만들고, GitHub org별로
매핑합니다:

```bash
lens creds set-accounts --ga4-account-id <LAB_GA4_ID> --gtm-account-id <LAB_GTM_ID> --profile lab
lens creds map-org kokoa-lab lab
lens creds map-org kokoa-study-room lab
# shinkeonkim 같이 매핑 안 한 org는 계속 default 프로필을 씀
```

`lens creds check`에서 프로필별 계정과 org 매핑을 모두 확인할 수 있습니다.

## 3. Google Ads Developer Token

Google Ads API는 OAuth 외에 **Developer Token** 승인이 별도로 필요합니다 (Basic Access
신청 → Google 심사, 수일 소요 가능). Google Ads 계정의 "도구 및 설정 > API 센터"에서
신청합니다.

승인 전까지는 GA4/GTM 자동화만 사용하고, `lens track link-ads`는 GA4-Ads 연결(GA4 Admin
API만 필요, Developer Token 불필요)까지만 수행하고 전환 액션 생성은 건너뜁니다.

```bash
lens creds init --provider google-ads \
  --developer-token <DEVELOPER_TOKEN> \
  --login-customer-id <MCC_CUSTOMER_ID>   # MCC(관리자 계정) 아래에서 접근할 때만 필요
```

Developer Token은 OS 키체인에 저장되며, `login-customer-id`는 비밀이 아니라
`~/.project-lens/settings.json`에 저장됩니다.

**주의**: Google Ads API는 `analytics.edit`/`tagmanager.*`와는 별도로
`https://www.googleapis.com/auth/adwords` OAuth 스코프가 필요합니다. Ads 연동을 처음
쓰기 전에 기존 Google 인증이 있었다면 `lens creds init --provider google`을 다시
실행해 이 스코프를 포함해 재인증해야 `insufficient authentication scopes` 오류를
피할 수 있습니다.

`lens creds check`로 전체 상태(`google oauth`, `google ads developer token`,
`ads_login_customer_id`)를 확인할 수 있습니다.

```bash
lens creds init --provider google-ads --developer-token <TOKEN> --login-customer-id <ID>
```

## 4. Cloudflare (선택, `deploy_mode=direct` 사용 시에만)

```bash
lens creds init --provider cloudflare --api-token <TOKEN>
```

이 토큰이 없으면 `direct` 배포를 요청해도 CLI가 자동으로 `pr` 모드로 폴백하고 경고를 남깁니다
(무동작 실패보다 안전한 대체 동작을 우선).

## 5. 로컬 파일 보호

- `~/.project-lens/credentials/`는 CLI가 최초 실행 시 `chmod 700`으로 생성
- 개별 파일은 `chmod 600`
- `.gitignore`에 다음을 명시 (project-lens 레포 자체에 실수로 `.env`/`credentials/` 등이
  생기는 것을 방지):

```
.env
.env.*
credentials/
*.sqlite3
*.jsonl
```

## 6. 점검 커맨드

```bash
lens creds check          # 전체 자격증명 상태 표 출력 (ok / expiring_soon / missing / invalid)
```

`/lens-creds-setup` 커맨드는 위 결과를 사람이 읽기 쉬운 안내로 변환하고, 부족한 항목에 대해
이 문서의 해당 섹션 링크를 함께 제시합니다.
