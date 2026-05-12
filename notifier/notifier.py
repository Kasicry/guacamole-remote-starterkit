import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

import psycopg


def log(message: str) -> None:
    print(f"{datetime.now(timezone.utc).isoformat()} {message}", flush=True)


def env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        log(f"Invalid integer for {name}={raw!r}; using {default}")
        return default


def db_connect():
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "postgres"),
        port=env_int("POSTGRES_PORT", 5432),
        dbname=os.getenv("POSTGRES_DB", "guacamole_db"),
        user=os.getenv("POSTGRES_USER", "guacamole_user"),
        password=os.getenv("POSTGRES_PASSWORD", "guacamole_password"),
        autocommit=True,
    )


def fetch_new_connections(conn, last_history_id: int):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT history_id, username, remote_host, connection_name, start_date
            FROM guacamole_connection_history
            WHERE history_id > %s
            ORDER BY history_id ASC
            """,
            (last_history_id,),
        )
        return cur.fetchall()


def fetch_latest_history_id(conn) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT COALESCE(MAX(history_id), 0) FROM guacamole_connection_history")
        return int(cur.fetchone()[0])


def render_message(row) -> str:
    history_id, username, remote_host, connection_name, start_date = row
    template = os.getenv(
        "NOTIFIER_MESSAGE_TEMPLATE",
        "Guacamole 원격접속 성공\n사용자: {username}\n접속: {connection_name}\n접속지: {remote_host}\n시간: {start_date}",
    )
    return template.replace("\\n", "\n").format(
        history_id=history_id,
        username=username,
        remote_host=remote_host or "-",
        connection_name=connection_name,
        start_date=start_date.isoformat(),
    )


def json_dumps(payload: dict) -> bytes:
    import json

    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def send_slack_message(message: str) -> None:
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook_url:
        log("Slack webhook is not configured; dry-run message follows")
        log(message.replace("\n", " | "))
        return

    payload = {
        "text": message,
        "username": os.getenv("SLACK_USERNAME", "Guacamole Notifier"),
    }

    icon_emoji = os.getenv("SLACK_ICON_EMOJI")
    if icon_emoji:
        payload["icon_emoji"] = icon_emoji

    request = urllib.request.Request(
        webhook_url,
        data=json_dumps(payload),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=env_int("SLACK_TIMEOUT_SECONDS", 15)) as response:
        body = response.read().decode("utf-8", errors="replace")
        if response.status < 200 or response.status >= 300:
            raise RuntimeError(f"Slack webhook failed: HTTP {response.status} {body}")
        if body and body.strip().lower() != "ok":
            log(f"Slack webhook response: {body.strip()}")
    log("Sent Slack notification")


def main() -> int:
    poll_seconds = env_int("NOTIFIER_POLL_SECONDS", 5)
    notify_existing = os.getenv("NOTIFIER_NOTIFY_EXISTING", "false").lower() == "true"

    while True:
        try:
            with db_connect() as conn:
                last_history_id = 0 if notify_existing else fetch_latest_history_id(conn)
                log(f"Notifier started; last_history_id={last_history_id}")

                while True:
                    rows = fetch_new_connections(conn, last_history_id)
                    for row in rows:
                        last_history_id = max(last_history_id, int(row[0]))
                        send_slack_message(render_message(row))
                    time.sleep(poll_seconds)
        except (psycopg.Error, urllib.error.URLError, RuntimeError) as exc:
            log(f"Notifier error: {exc}")
            time.sleep(max(poll_seconds, 5))
        except KeyboardInterrupt:
            return 0
        except Exception as exc:
            log(f"Unexpected notifier error: {exc}")
            return 1


if __name__ == "__main__":
    sys.exit(main())
