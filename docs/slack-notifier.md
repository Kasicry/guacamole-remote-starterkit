# Slack Webhook 알림 연동 가이드

## 1. 목표

Guacamole 원격접속이 성공하면 Slack Incoming Webhook으로 알림을 보낸다.

```text
Guacamole PostgreSQL connection history
    |
    v
notifier
    |
    v
Slack Incoming Webhook
    |
    v
Slack channel
```

## 2. 구현 방식

notifier는 Guacamole PostgreSQL의 `guacamole_connection_history` 테이블을 주기적으로 확인한다.

새 `history_id`가 생기면 접속 성공으로 보고 Slack webhook에 메시지를 보낸다.

Guacamole 본체는 수정하지 않는다. notifier가 꺼져도 원격접속은 계속 동작한다.

## 3. Slack Webhook 준비

Slack에서 Incoming Webhook URL을 발급한다.

1. Slack API 페이지에서 앱 생성
2. Incoming Webhooks 활성화
3. 알림을 받을 채널 선택
4. Webhook URL 복사

Webhook URL은 비밀값이다. GitHub에 커밋하지 않는다.

## 4. 설정

설정 파일을 만든다.

```powershell
Copy-Item notifier\.env.example notifier\.env
```

`notifier/.env`에 Slack webhook을 입력한다.

```env
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
SLACK_USERNAME=Guacamole Notifier
SLACK_ICON_EMOJI=:desktop_computer:
```

`notifier/.env`는 `.gitignore`에 포함되어 있어 커밋되지 않는다.

## 5. 실행

notifier는 Docker Compose profile로 분리되어 있다.

```powershell
docker compose --profile notifier up -d notifier
```

로그 확인:

```powershell
docker compose logs -f notifier
```

중지:

```powershell
docker compose --profile notifier stop notifier
```

## 6. 메시지 포맷

기본 메시지:

```text
Guacamole 원격접속 성공
사용자: Kasicry
접속: BusanCouputer
접속지: 172.19.0.1
시간: 2026-05-12T...
```

메시지 템플릿은 `NOTIFIER_MESSAGE_TEMPLATE`로 변경할 수 있다.

사용 가능한 변수:

```text
{history_id}
{username}
{remote_host}
{connection_name}
{start_date}
```

## 7. Dry-run

`SLACK_WEBHOOK_URL`이 비어 있으면 실제 Slack 발송을 하지 않고 로그만 남긴다.

```text
Slack webhook is not configured; dry-run message follows
Guacamole 원격접속 성공 | 사용자: Kasicry | 접속: BusanCouputer
```

## 8. 테스트

1. `notifier/.env`에 `SLACK_WEBHOOK_URL` 입력
2. notifier 실행
3. Guacamole에서 원격접속 시작
4. Slack 채널에 메시지가 오는지 확인

수동 webhook 테스트:

```powershell
$body = @{ text = "Guacamole Slack webhook test" } | ConvertTo-Json
Invoke-RestMethod -Uri "https://hooks.slack.com/services/..." -Method Post -Body $body -ContentType "application/json"
```
