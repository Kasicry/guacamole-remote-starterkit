# 코드리뷰: Apache Guacamole 원격접속 환경 구성

## 1. 전체 구조

이번 작업은 Apache Guacamole을 Docker Compose로 실행하고, 웹브라우저에서 원격접속할 수 있도록 구성한 것이다.

현재 실행 구조는 다음과 같다.

```text
Browser
  |
  | HTTP  : 13500
  | HTTPS : 13543
  v
Guacamole Web
  |
  v
guacd
  |
  v
RDP / SSH / VNC 대상 서버

Guacamole Web
  |
  v
PostgreSQL
```

핵심 컨테이너는 4개다.

| 컨테이너 | 역할 |
|---|---|
| `remote-service-postgres` | Guacamole 사용자, 권한, 연결 설정 저장 |
| `remote-service-guacd` | RDP/SSH/VNC 실제 중계 |
| `remote-service-guacamole` | 웹 UI와 API 제공 |
| `remote-service-https-proxy` | HTTPS reverse proxy |

## 2. `compose.yaml`

이 파일은 전체 서비스를 정의하는 핵심 파일이다.

### 2.1 PostgreSQL

```yaml
postgres:
  image: postgres:16-alpine
```

Guacamole은 사용자, 연결 정보, 권한 정보를 DB에 저장한다. 여기서는 PostgreSQL을 사용한다.

중요한 설정:

```yaml
POSTGRES_DB: guacamole_db
POSTGRES_USER: guacamole_user
POSTGRES_PASSWORD: guacamole_password
```

이 값들은 Guacamole 컨테이너가 DB에 접속할 때도 동일하게 사용된다.

```yaml
volumes:
  - guacamole-postgres-data:/var/lib/postgresql/data
  - ./initdb:/docker-entrypoint-initdb.d:ro
```

`guacamole-postgres-data`는 DB 데이터를 보존하기 위한 Docker volume이다. 컨테이너를 재시작해도 사용자/연결 설정이 유지된다.

`./initdb`는 DB 최초 생성 시 실행되는 SQL 파일 위치다. 여기에 `001-initdb.sql`이 들어 있다.

### 2.2 guacd

```yaml
guacd:
  image: guacamole/guacd:1.6.0
```

`guacd`는 Guacamole의 핵심 중계 데몬이다. 사용자가 웹에서 RDP 연결을 누르면, Guacamole Web이 직접 RDP를 처리하지 않고 `guacd`에게 연결을 맡긴다.

### 2.3 Guacamole Web

```yaml
guacamole:
  image: guacamole/guacamole:1.6.0
```

브라우저에서 접속하는 웹 애플리케이션이다.

```yaml
depends_on:
  postgres:
    condition: service_healthy
  guacd:
    condition: service_started
```

PostgreSQL이 준비된 뒤 Guacamole을 시작하도록 설정했다. DB가 준비되기 전에 Guacamole이 먼저 뜨면 인증 설정을 읽지 못할 수 있다.

```yaml
ports:
  - "13500:8080"
```

호스트의 `13500` 포트를 컨테이너 내부 `8080`으로 연결한다.

접속 주소:

```text
http://127.0.0.1:13500/guacamole/
```

```yaml
REMOTE_IP_VALVE_ENABLED: "true"
```

reverse proxy 뒤에서 실제 클라이언트 IP를 인식하기 위한 설정이다.

### 2.4 HTTPS Proxy

```yaml
https-proxy:
  image: nginx:1.27-alpine
```

처음에는 Caddy를 사용했지만, Windows 로컬 TLS 클라이언트에서 self-signed 인증서 처리 문제가 있어 Nginx로 교체했다.

```yaml
ports:
  - "13543:443"
```

호스트의 `13543` 포트를 HTTPS 프록시 컨테이너의 `443`으로 연결한다.

접속 주소:

```text
https://127.0.0.1:13543/guacamole/
https://121.174.213.240:13543/guacamole/
```

```yaml
volumes:
  - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
  - ./certs:/certs:ro
```

Nginx 설정 파일과 인증서 파일을 컨테이너 안으로 읽기 전용으로 마운트한다.

## 3. `nginx.conf`

이 파일은 HTTPS reverse proxy 설정이다.

```nginx
listen 443 ssl;
```

컨테이너 내부에서 HTTPS 443 포트를 연다. 호스트에서는 `compose.yaml`에 의해 `13543`으로 노출된다.

```nginx
ssl_certificate /certs/guacamole.crt;
ssl_certificate_key /certs/guacamole.key;
```

self-signed 인증서를 사용한다. 이 인증서는 테스트용이며, 브라우저에서 보안 경고가 뜰 수 있다.

```nginx
proxy_pass http://guacamole:8080;
```

HTTPS로 들어온 요청을 내부 Guacamole Web 컨테이너로 전달한다.

Docker Compose 네트워크 안에서는 서비스 이름 `guacamole`이 DNS 이름처럼 동작한다.

```nginx
proxy_set_header X-Forwarded-Proto https;
proxy_set_header X-Real-IP $remote_addr;
```

Guacamole이 원래 요청이 HTTPS였고, 실제 접속자가 누구인지 알 수 있게 헤더를 넘긴다.

```nginx
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";
```

WebSocket 연결을 위해 필요하다. Guacamole 원격 세션은 브라우저와 서버 사이의 실시간 통신이 중요하므로 이 설정이 빠지면 세션 화면이 정상 동작하지 않을 수 있다.

## 4. `initdb/001-initdb.sql`

Guacamole의 PostgreSQL 스키마 초기화 파일이다.

이 파일은 공식 Guacamole 컨테이너의 `initdb.sh --postgresql` 명령으로 생성했다.

역할:

- Guacamole 사용자 테이블 생성
- 연결 정보 테이블 생성
- 권한 테이블 생성
- 기본 관리자 계정 생성

주의할 점:

DB volume이 이미 생성된 뒤에는 `initdb` 파일을 수정해도 자동 재실행되지 않는다. PostgreSQL 공식 이미지의 초기화 스크립트는 데이터 디렉터리가 비어 있을 때만 실행된다.

## 5. `certs/guacamole.crt`, `certs/guacamole.key`

HTTPS 테스트를 위해 생성한 self-signed 인증서다.

포함된 SAN 값:

```text
localhost
127.0.0.1
172.30.1.3
121.174.213.240
```

브라우저에서 인증서 경고가 뜨는 것은 정상이다. 공인 도메인과 Let's Encrypt 인증서를 쓰지 않았기 때문이다.

운영 환경에서는 self-signed 인증서 대신 공인 인증서를 사용해야 한다.

## 6. `guide.md`

운영자가 외부에서 접속하기 위해 필요한 절차를 정리한 문서다.

포함 내용:

- 로컬 접속 주소
- 내부망 접속 주소
- 외부 IP 접속 주소
- Windows 방화벽 규칙
- 공유기 포트포워딩
- HTTPS 접속 방법
- 체크리스트

현재 외부 HTTPS 포트포워딩 값은 다음과 같다.

```text
외부 포트: 13543
내부 IP: 172.30.1.3
내부 포트: 13543
프로토콜: TCP
```

## 7. `agents.md`

AI 코드 에이전트가 이 프로젝트에서 지켜야 할 작업 지침이다.

핵심 원칙:

- 코딩 전에 문제를 먼저 이해한다.
- 단순한 해결책을 우선한다.
- 요청한 부분만 외과적으로 수정한다.
- 작업 성공 기준을 명확히 정의한다.

이 파일은 프로젝트 협업 규칙에 가깝고, 런타임 동작에는 영향을 주지 않는다.

## 8. 삭제한 Caddy 구성

현재 최종 구성에서는 Caddy를 사용하지 않는다.

초기 HTTPS 적용 시 Caddy를 사용했지만, Windows 로컬 TLS 클라이언트에서 다음 오류가 반복되어 Nginx로 교체했다.

```text
Schannel: SEC_E_NO_CREDENTIALS
보안 패키지에 사용할 수 있는 인증서가 없습니다
```

혼동을 줄이기 위해 더 이상 사용하지 않는 `Caddyfile`은 삭제했다.

## 9. 계정 및 연결 설정 변경

초기 관리자 계정 `guacadmin`은 `Kasicry`로 변경했다.

현재 로그인 ID:

```text
Kasicry
```

비밀번호는 사용자가 변경한 상태다. 로그에서 비밀번호 변경 이벤트가 확인되었다.

RDP 연결 `BusanCouputer`는 다음 흐름으로 수정했다.

1. 처음에는 RDP 포트가 `13500`으로 되어 있었다.
2. `13500`은 Guacamole 웹 접속 포트이므로 RDP 포트로는 잘못된 값이다.
3. RDP 포트는 `3389`로 변경했다.
4. 대상 IP도 변경했다.
5. RDP 인증서 오류를 해결하기 위해 `ignore-cert=true`를 추가했다.

현재 RDP 연결 핵심 설정:

```text
hostname: 172.30.1.3
port: 3389
ignore-cert: true
```

## 10. 검증한 내용

검증 결과:

```text
HTTP Guacamole: 200 OK
HTTPS proxy 내부 테스트: 200 OK
PostgreSQL: healthy
guacd: healthy
RDP 대상 3389: TcpTestSucceeded=True
13500 방화벽 규칙: 등록 완료
13543 방화벽 규칙: 등록 완료
```

Windows의 `curl`과 `Invoke-WebRequest`는 self-signed HTTPS에서 Schannel 오류가 났지만, Python OpenSSL 클라이언트와 컨테이너 내부 테스트에서는 HTTPS가 정상 응답했다.

따라서 서비스 자체는 정상이고, 로컬 Windows 클라이언트의 인증서 신뢰/Schannel 처리 이슈로 판단했다.

## 11. 남은 개선점

### 11.1 공인 도메인과 Let's Encrypt 적용

현재는 IP 기반 self-signed 인증서다. 운영 환경에서는 도메인을 연결하고 공인 인증서를 적용해야 한다.

예시:

```text
remote.example.com
```

이렇게 구성하면 브라우저 인증서 경고가 사라지고 외부 사용자 경험이 좋아진다.

### 11.2 HTTP 포트 제한

현재 HTTP `13500`과 HTTPS `13543`이 모두 열려 있다.

운영에서는 외부에 HTTPS만 공개하고 HTTP는 내부 접근용으로 제한하는 것이 좋다.

### 11.3 비밀번호/시크릿 관리

`compose.yaml`에 DB 비밀번호가 평문으로 들어 있다.

운영에서는 `.env` 파일, Docker secrets, 또는 별도 비밀 관리 도구를 사용하는 것이 좋다.

### 11.4 사용하지 않는 HTTPS 프록시 설정 정리

최종 구성은 Nginx다. Caddy 설정 파일은 삭제했으므로, 이후 HTTPS 관련 수정은 `nginx.conf`와 `compose.yaml`의 `https-proxy` 서비스를 기준으로 진행하면 된다.

### 11.5 백업 자동화

Guacamole 설정은 PostgreSQL volume에 저장된다. 주기적으로 DB 백업을 자동화해야 한다.

예시:

```powershell
docker compose exec postgres pg_dump -U guacamole_user guacamole_db > backup.sql
```

## 12. 주니어 개발자가 기억할 핵심

- `13500`은 Guacamole HTTP 웹 포트다.
- `13543`은 HTTPS reverse proxy 포트다.
- RDP 대상 서버 포트는 보통 `3389`다.
- `guacd`는 원격접속 프로토콜을 실제로 중계하는 컴포넌트다.
- PostgreSQL volume을 지우면 Guacamole 사용자/연결 설정이 사라질 수 있다.
- self-signed 인증서는 테스트용이다. 운영에서는 공인 인증서를 써야 한다.
