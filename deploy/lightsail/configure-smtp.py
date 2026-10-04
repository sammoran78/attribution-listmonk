"""Apply VM-local SES SMTP credentials without printing them."""
import json
import pathlib
import subprocess


def main():
    base = pathlib.Path(__file__).resolve().parent
    creds = json.loads((base / "secrets/smtp.json").read_text())
    smtp = [{
        "enabled": True, "host": "email-smtp.ap-southeast-2.amazonaws.com",
        "port": 587, "auth_protocol": "login", "username": creds["username"],
        "password": creds["password"], "hello_hostname": "lists.creativeattribution.com",
        # smtppool v2.1.2 starts its idle sweeper only when MaxConns > 1.
        # Campaign concurrency/rate remain one; this enables idle cleanup.
        "max_conns": 2, "idle_timeout": "5s", "wait_timeout": "10s",
        "max_msg_retries": 2, "msg_retry_delay": "1s", "tls_type": "STARTTLS",
        "tls_skip_verify": False, "from_addresses": [],
        "email_headers": [{"Reply-To": "sam.moran@mq.edu.au"}],
    }]
    value = json.dumps(smtp).replace("'", "''")
    sql = "UPDATE settings SET value = '" + value + "'::jsonb WHERE key = 'smtp';\n"
    subprocess.run(["docker", "compose", "exec", "-T", "db", "psql", "-v", "ON_ERROR_STOP=1", "-U", "listmonk", "-d", "listmonk"], cwd=base, input=sql, text=True, check=True)


if __name__ == "__main__":
    main()
