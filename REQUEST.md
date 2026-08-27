1. 이 프로젝트에서는 Google Analytics와 Tag manager, Google Ads를 활용하여 웹사이트의 트래픽과 사용자 행동을 분석하고, 광고 캠페인의 성과를 측정합니다. 이를 통해 마케팅 전략을 최적화하고, 사용자 경험을 개선할 수 있습니다.
2. Google Analytics를 사용하여 웹사이트 방문자 수, 페이지뷰, 세션 지속 시간, 이탈률 등의 지표를 분석합니다. 이를 통해 어떤 페이지가 인기가 있는지, 사용자가 어떤 경로로 이동하는지 등을 파악할 수 있습니다.
3. Google Tag Manager를 활용하여 웹사이트에 다양한 태그를 쉽게 관리하고, 이벤트 추적을 설정할 수 있습니다. 이를 통해 특정 버튼 클릭, 폼 제출, 스크롤링 등의 사용자 행동을 추적하고, 이를 기반으로 마케팅 전략을 개선할 수 있습니다.
4. Google Ads를 통해 광고 캠페인을 운영하고, 클릭률(CTR), 전환율, 광고 비용 등을 분석합니다. 이를 통해 어떤 광고가 효과적인지, 어떤 키워드가 성과가 좋은지 등을 파악하고, 광고 예산을 효율적으로 배분할 수 있습니다.
5. 단, 이 프로젝트에서 추적하는 대상은 하나가 아니며, 여러 웹 사이트 프로젝트에 대해서 추적 관리하여 제대로 설정들을 구성하여 배포하는 과정을 거치면 됩니다. 각 웹사이트의 배포 방식과, Github URL 등은 지속적으로 사용자가 제시할 예정이며, 이는 Claude Command를 통해서 할 수 있도록 구현해두어야 합니다.
6. GIthub URL은 private Repository일 수도 있고, Public Repository일 수도 있으며, 사용자가 제공하는 URL에 따라 접근 권한을 확인하고, 필요한 경우 인증 절차를 거쳐야 합니다. 또한, 각 웹사이트의 배포 방식에 따라 설정 파일이나 스크립트가 다를 수 있으므로, 이를 유연하게 처리할 수 있는 구조를 갖추어야 합니다.
7. 모든 프로젝트의 코드를 계속 가지고 있는게 아니라 그때 그때 작업시에 clone하여 작업을 진행하고, 작업이 끝나면 해당 프로젝트의 코드를 삭제하는 방식으로 관리합니다. 이를 통해 저장 공간을 효율적으로 사용하고, 보안 문제를 최소화할 수 있습니다.
9. Google Analytics, Tag manager, Google ads 와 관련되어 해야 하는 행동도 명확히 정의하며, 자동화된 스크립트나 명령어를 통해 반복적인 작업을 최소화하고, 효율적인 데이터 수집과 분석이 가능하도록 구현해야 합니다. 또한, 각 웹사이트의 특성과 요구사항에 맞게 커스터마이징할 수 있는 기능을 제공하여, 다양한 프로젝트에 적용할 수 있도록 해야 합니다.
10. 프로젝트 진행 중 발생할 수 있는 문제나 오류에 대한 로그를 기록하고, 이를 분석하여 개선점을 도출할 수 있는 기능을 구현해야 합니다. 또한, 사용자에게 문제 해결 방법이나 가이드를 제공하여, 프로젝트 진행에 차질이 없도록 지원해야 합니다.
11. 기존에 추적중인 프로젝트였다면, 해당 정보를 기록해두고 관리할 수 있게 합니다. 이를 통해 프로젝트 진행 상황을 쉽게 파악하고, 필요한 경우 이전 설정을 참고하여 작업을 진행할 수 있도록 합니다. 또한, 프로젝트 완료 후에도 해당 정보를 보관하여, 향후 유사한 프로젝트 진행 시 참고할 수 있도록 합니다.
12. 각 프로젝트별로 추적 정보를 기록하고 관리할 수 있는 데이터베이스를 구축하여, 프로젝트 진행 상황과 성과를 체계적으로 관리할 수 있도록 합니다. 이를 통해 프로젝트 간의 비교 분석이 가능하며, 향후 프로젝트 계획 수립에 참고할 수 있습니다.
13. 필요한 보안 자격증명은 Github에 올라가지 않도록 관리하며, 별도로 제공할 수 있게 메뉴얼을 제시해야 합니다.

우선적으로 아래 Cloudflare Workers를 통해 배포된 Github URL들을 제시하겠습니다.
- https://github.com/kokoa-lab/how-to-get-google-dot-com
- https://github.com/kokoa-lab/dice-art
- https://github.com/kokoa-lab/pattern-type
- https://github.com/kokoa-lab/dev-tarot
- https://github.com/kokoa-lab/review-slot
- https://github.com/kokoa-lab/please-delete-my-account
- https://github.com/kokoa-lab/cozy-hive
- https://github.com/kokoa-study-room/transaction-isolation-level
- https://github.com/kokoa-study-room/compiler-study-site
- https://github.com/kokoa-study-room/terraform-associate-004-study-notes
- https://github.com/shinkeonkim/my-portfolio
- https://github.com/shinkeonkim/my-cv
- https://github.com/shinkeonkim/my-resume

아래의 프로젝트는 oh-my-homelab을 활용하여 배포중인 프로젝트입니다. oh-my-homelab은 개인 서버 환경에서 다양한 서비스를 쉽게 배포하고 관리할 수 있도록 도와주는 도구입니다. 이 프로젝트를 통해 배포되는 프로젝트들에 대해서도 다룰 수 있개 구성해야 합니다.
- https://github.com/shinkeonkim/codekr
- (참고: https://github.com/shinkeonkim/oh-my-homelab)
