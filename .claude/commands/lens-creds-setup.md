---
description: GitHub/Google 자격증명 상태를 확인하고, 필요한 다음 단계를 안내합니다
---

project-lens 레포 루트에서 `lens`(PATH에 없으면 `<project-lens repo>/.venv/bin/lens`)로
다음을 실행하세요:

```
lens creds check
```

출력(`google oauth`, `ga4_account_id`, `gtm_account_id`, `google ads developer token`,
`ads_login_customer_id`)을 확인하고, `missing`이나 `(미설정)`이 있으면 아래 절차를
안내하세요. 각 단계는 브라우저 동의나 외부 콘솔 작업이 필요해 **사용자가 직접 실행해야
합니다** — 명령을 자동 실행하지 말고 안내만 하세요.

1. **google oauth가 missing**: `docs/SECURITY.md` 2번 섹션대로 GCP 콘솔에서 OAuth
   클라이언트를 만들고 `~/.project-lens/credentials/google_oauth_client.json`에 저장한
   뒤 `lens creds init --provider google` 실행 (브라우저 동의 필요)
2. **ga4_account_id / gtm_account_id가 미설정**: 인증이 끝났다면
   `lens creds accounts`로 접근 가능한 계정 목록을 보여주고, 사용자에게 어떤 계정을
   기본으로 쓸지 확인한 뒤
   `lens creds set-accounts --ga4-account-id <ID> --gtm-account-id <ID>` 실행
3. **google ads developer token이 missing** (Ads 자동화를 쓰려는 경우만): Google Ads
   계정의 "도구 및 설정 > API 센터"에서 Developer Token을 발급받은 뒤(승인까지 수일
   소요될 수 있음)
   `lens creds init --provider google-ads --developer-token <TOKEN> [--login-customer-id <ID>]`
   실행. **주의**: 기존에 `google oauth`를 이미 인증했다면 Ads API 스코프(`adwords`)가
   없을 수 있으니 `lens creds init --provider google`을 다시 실행해 재인증하라고
   안내하세요.

모든 항목이 `ok`/설정된 상태면 "Google 연동 준비가 끝났습니다"라고 알려주고, 다음으로
`/lens-sync` 또는 `/lens-link-ads`를 쓸 수 있다고 안내하세요.
