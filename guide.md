# Apache Guacamole 외부 접속 가이드

## 1. 현재 접속 정보

현재 Guacamole은 Docker Compose로 실행 중이며, 호스트의 `13500` 포트로 노출되어 있다.
HTTPS reverse proxy는 `13543` 포트로 노출되어 있다.

로컬 접속 주소:

```text
http://127.0.0.1:13500/guacamole/
https://127.0.0.1:13543/guacamole/
```

같은 네트워크의 다른 PC에서 접속할 때:

```text
http://서버IP:13500/guacamole/
https://서버IP:13543/guacamole/
```

로그인 계정:

```text
ID: Kasicry
Password: guacadmin
```

운영 전에는 반드시 로그인 후 비밀번호를 변경한다.

## 2. 서비스 상태 확인

프로젝트 폴더에서 다음 명령으로 컨테이너 상태를 확인한다.

```powershell
docker compose ps
```

정상 상태 예시는 다음과 같다.

```text
remote-service-guacamole   Up   0.0.0.0:13500->8080/tcp
remote-service-guacd       Up   4822/tcp
remote-service-postgres    Up   5432/tcp
```

서비스 시작:

```powershell
docker compose up -d
```

서비스 중지:

```powershell
docker compose down
```

로그 확인:

```powershell
docker compose logs -f guacamole
```

## 3. 내부망에서 접속하기

서버의 내부 IP를 확인한다.

```powershell
ipconfig
```

예를 들어 서버 IP가 `192.168.0.10`이면 같은 네트워크의 PC에서 다음 주소로 접속한다.

```text
http://192.168.0.10:13500/guacamole/
```

접속이 안 되면 다음을 확인한다.

- Guacamole 컨테이너가 실행 중인지 확인한다.
- `13500` 포트가 다른 프로그램과 충돌하지 않는지 확인한다.
- Windows 방화벽 또는 서버 방화벽에서 TCP `13500` 포트를 허용한다.
- 접속하는 PC와 서버가 같은 네트워크에 있는지 확인한다.

## 4. Windows 방화벽에서 13500 포트 허용

관리자 PowerShell에서 다음 명령을 실행한다.

```powershell
New-NetFirewallRule `
  -DisplayName "Guacamole 13500" `
  -Direction Inbound `
  -Protocol TCP `
  -LocalPort 13500 `
  -Action Allow
```

규칙 확인:

```powershell
Get-NetFirewallRule -DisplayName "Guacamole 13500"
```

## 5. 외부 인터넷에서 접속하기

외부에서 접속하려면 서버가 있는 네트워크의 공인 IP 또는 도메인이 필요하다.

외부 접속 주소:

```text
http://공인IP:13500/guacamole/
https://공인IP:13543/guacamole/
```

도메인을 연결한 경우:

```text
http://remote.example.com:13500/guacamole/
https://remote.example.com:13543/guacamole/
```

현재 HTTPS는 자체 생성한 self-signed 인증서를 사용한다. 암호화는 적용되지만 공인 인증서가 아니므로 브라우저에 인증서 경고가 표시될 수 있다. 경고 없는 HTTPS를 사용하려면 도메인을 연결하고 Let's Encrypt 인증서를 발급받아야 한다.

## 6. 공유기 또는 라우터 포트포워딩

서버가 사내망이나 가정용 공유기 뒤에 있다면 공유기에서 포트포워딩을 설정해야 한다.

예시:

| 항목 | 값 |
|---|---|
| 외부 포트 | 13543 |
| 내부 IP | Guacamole 서버 IP |
| 내부 포트 | 13543 |
| 프로토콜 | TCP |

설정 후 외부 네트워크에서 다음 주소로 접속한다.

```text
https://공인IP:13543/guacamole/
```

공인 IP 확인은 서버 또는 같은 네트워크의 브라우저에서 `what is my ip`로 확인할 수 있다.

## 7. 클라우드 서버에서 접속 허용

AWS, Azure, GCP, Oracle Cloud 같은 클라우드 VM에서 실행하는 경우 보안그룹 또는 방화벽 규칙에 TCP `13500` 인바운드 허용이 필요하다.
HTTPS 접속을 사용할 경우 TCP `13543` 인바운드 허용이 필요하다.

권장 규칙:

| 항목 | 값 |
|---|---|
| Protocol | TCP |
| Port | 13543 |
| Source | 관리자 고정 IP |

가능하면 `0.0.0.0/0` 전체 공개 대신 접속할 관리자 IP만 허용한다.

## 8. 운영 권장 구성

외부 공개 운영 시 권장 구조는 다음과 같다.

```text
User Browser
    |
    | HTTPS 443
    v
Reverse Proxy
    |
    | HTTP 13500
    v
Guacamole
    |
    v
guacd
    |
    +--> RDP / SSH / VNC 대상 서버
```

권장 사항:

- 가능하면 외부에는 HTTPS 포트만 공개한다. 현재 테스트 구성에서는 `13543`을 사용한다.
- Guacamole의 `13500` 포트는 서버 내부 또는 reverse proxy에서만 접근하도록 제한한다.
- HTTPS 인증서를 적용한다.
- 기본 비밀번호를 즉시 변경한다.
- 2차 인증을 적용한다.
- 접속 대상 서버의 RDP, SSH, VNC 포트는 인터넷에 직접 노출하지 않는다.

## 9. Nginx reverse proxy 구성

현재 프로젝트는 Nginx를 사용해 HTTPS reverse proxy를 제공한다.

```text
외부 HTTPS: https://121.174.213.240:13543/guacamole/
내부 프록시: nginx -> guacamole:8080
```

현재 `nginx.conf`:

```nginx
server {
    listen 443 ssl;
    server_name localhost 127.0.0.1 172.30.1.3 121.174.213.240;

    ssl_certificate /certs/guacamole.crt;
    ssl_certificate_key /certs/guacamole.key;

    location / {
        proxy_pass http://guacamole:8080;
    }
}
```

도메인을 연결하면 `server_name`에 도메인을 추가하고, 공유기에서 `443` 또는 원하는 HTTPS 포트를 Nginx 프록시로 포워딩한다.

## 10. 접속 테스트 체크리스트

- `docker compose ps`에서 세 컨테이너가 `Up` 상태인지 확인한다.
- 서버에서 `http://127.0.0.1:13500/guacamole/` 접속이 되는지 확인한다.
- 서버에서 `https://127.0.0.1:13543/guacamole/` 접속이 되는지 확인한다.
- 같은 내부망 PC에서 `http://서버IP:13500/guacamole/` 접속이 되는지 확인한다.
- 같은 내부망 PC에서 `https://서버IP:13543/guacamole/` 접속이 되는지 확인한다.
- 외부 접속이 필요하면 공유기 포트포워딩 또는 클라우드 보안그룹을 확인한다.
- 로그인 ID `Kasicry`로 접속되는지 확인한다.
- 기본 비밀번호 `guacadmin`을 변경한다.

## 11. 주의사항

- 현재 구성은 테스트용 HTTP 구성이다.
- 외부 인터넷에 바로 공개하기 전 HTTPS와 2차 인증을 적용한다.
- 관리자 계정은 개인별로 분리해서 운영한다.
- 접속 로그를 주기적으로 확인한다.
- Guacamole과 Docker 이미지를 정기적으로 업데이트한다.
- PostgreSQL 볼륨은 정기 백업한다.
