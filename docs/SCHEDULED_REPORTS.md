# 정기 리포트 (Phase 6)

`lens track report-all`을 매주 정해진 시각에 자동 실행해, 등록된 모든 프로젝트의 GA4
성과를 한 파일로 모아 둡니다.

## 왜 클라우드 스케줄이 아니라 로컬 launchd인가

Claude Code의 `schedule` 스킬은 **클라우드**의 격리된 샌드박스에서 도는 routine을
만듭니다. project-lens는 자격증명(Google OAuth, Ads Developer Token)을 OS
키체인(macOS Keychain)에, 프로젝트 레지스트리를 로컬 SQLite(`~/.project-lens/`)에
두는데 — 둘 다 **이 Mac 로컬에만 있고 클라우드 샌드박스에서는 접근할 수 없습니다**
(`docs/SECURITY.md`, `docs/ARCHITECTURE.md`의 설계 원칙). 그래서 클라우드 routine은
매번 인증 실패로 조용히 실패하게 됩니다 — 대신 이 Mac 자체에서 도는 launchd
LaunchAgent를 씁니다. cron이 아니라 launchd인 이유는, 이 Mac이 스케줄 시각에 잠들어
있었어도 깨어난 뒤 launchd가 놓친 실행을 따라잡아 주기 때문입니다(cron은 그냥
건너뜁니다).

## 설정된 스케줄

- **주기**: 매주 월요일 오전 9시 (로컬 시각)
- **원본**: [`scripts/launchd/com.project-lens.weekly-report.plist`](../scripts/launchd/com.project-lens.weekly-report.plist)
  (버전 관리됨 — 실제 설치 위치는 아래)
- **설치 위치**: `~/Library/LaunchAgents/com.project-lens.weekly-report.plist`
- **로그**: `~/.project-lens/logs/weekly-report.log` (표준출력),
  `~/.project-lens/logs/weekly-report.err.log` (표준에러)
- **리포트 결과**: `~/.project-lens/reports/<날짜>.txt` (`lens track report-all`이 직접 저장)

## 새 머신에서(또는 재설치) 설정하기

```bash
cp scripts/launchd/com.project-lens.weekly-report.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.project-lens.weekly-report.plist
```

plist의 경로들(`ProgramArguments`의 `.venv/bin/lens` 절대경로, `StandardOutPath` 등)은
지금 이 프로젝트가 있는 `/Users/koa/004-Projects/project-lens`와 사용자 홈 `/Users/koa`를
그대로 하드코딩하고 있습니다 — 경로가 바뀌면 plist를 고친 뒤 재등록하세요.

## 관리 명령

```bash
# 지금 당장 한 번 실행해보기 (스케줄과 별개로)
launchctl kickstart -k gui/$(id -u)/com.project-lens.weekly-report

# 상태 확인 (마지막 실행 결과, 다음 실행 예정 등)
launchctl print gui/$(id -u)/com.project-lens.weekly-report

# 끄기 (다시 켜려면 launchctl bootstrap으로 재등록)
launchctl bootout gui/$(id -u)/com.project-lens.weekly-report

# 등록/재등록 (plist를 고친 뒤에도 이걸로 반영)
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.project-lens.weekly-report.plist
```

## 스케줄 바꾸기

`~/Library/LaunchAgents/com.project-lens.weekly-report.plist`의 `StartCalendarInterval`
블록을 고치세요:

```xml
<key>StartCalendarInterval</key>
<dict>
    <key>Weekday</key>
    <integer>1</integer>  <!-- 0/7=일, 1=월, ..., 6=토 -->
    <key>Hour</key>
    <integer>9</integer>
    <key>Minute</key>
    <integer>0</integer>
</dict>
```

고친 뒤 `launchctl bootout` → `launchctl bootstrap`으로 다시 등록해야 반영됩니다.

## 확인된 것 / 확인 안 된 것

- [x] LaunchAgent 등록·수동 실행(`launchctl kickstart -k`) 성공
- [x] **로그인 세션과 무관하게(headless) OS 키체인 접근이 실제로 됨을 확인** — 이게
      가장 걱정했던 부분이었습니다. LaunchAgent가 keychain 접근 권한 프롬프트 없이
      바로 Google 인증을 통과해 실제 GA4 API까지 호출했고, 그 결과 진짜 Google
      쪽 에러(`SERVICE_DISABLED`, 아래 항목)를 받았습니다 — `AuthError`가 아니라
      `GoogleAPIError`였다는 것 자체가 인증이 문제없이 됐다는 증거입니다.
- [x] 표준출력/에러가 로그 파일에 기록됨, `~/.project-lens/reports/`에 리포트
      파일이 실제로 생성됨을 확인
- [x] `errors.short()`로 에러 메시지가 한 줄로 요약돼 로그가 읽기 좋음을 확인
- [x] **실제 성공적인 리포트까지 확인 완료.** GA4 Data API가 GCP 프로젝트
      (`project-lens-506802`)에서 켜져 있는데도 처음엔 `SERVICE_DISABLED`가 났었는데
      — 재시도하니 통과됨(활성화 전파 지연으로 추정). `launchctl kickstart -k`로
      다시 돌려 `~/.project-lens/logs/weekly-report.log`에 14개 프로젝트 전부의
      실제 GA4 수치(대부분 0 — PR이 아직 안 머지돼 사이트에 스니펫이 반영 안 됨,
      `shinkeonkim-my-portfolio`만 방문자 1)가 정상적으로 찍히고
      `~/.project-lens/reports/`에도 저장되는 것을 확인했습니다.
- [ ] 이 Mac이 몇 주 이상 재부팅/로그아웃 없이 켜져 있는 실사용 환경에서 매주
      실제로 도는지는 시간이 지나야 확인됩니다. `launchctl print`의
      `last exit code`/`state`로 다음 월요일 이후 확인하세요.
