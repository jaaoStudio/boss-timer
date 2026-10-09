#!/usr/bin/env python3
"""每日同步 Cloudflare IP 網段到 Traefik 的 cf-only middleware（見 docs/adr/0007）。

boss-timer 只接受經過 Cloudflare 的連線，網段來自 Cloudflare 的 /ips API；網段不保證永久不變，
新網段沒同步到時，從那些節點來的使用者會被擋。所以每天比對 etag，有變動就重新產生設定檔
（Traefik file provider 會自動重新載入），變動或失敗都寄信通知。

正式機以 cron 執行：python3 -I ~/boss-tracker/sync_cloudflare_ips.py
"""
import ipaddress
import json
import os
import smtplib
import sys
import tempfile
import time
import urllib.request
from email.message import EmailMessage

CF_IPS_URL = "https://api.cloudflare.com/client/v4/ips"
OUTPUT = os.environ.get("CF_IPS_OUTPUT", "/opt/traefik/dynamic/cloudflare-ips.yml")
TRAEFIK_API = os.environ.get("TRAEFIK_API", "http://127.0.0.1:8081")
MIDDLEWARE = "cf-only"
MAIL_TO = os.environ.get("MAIL_TO", "jack580936@gmail.com")
MAIL_FROM = os.environ.get("MAIL_FROM", "boss-timer@jaao.tw")
SMTP_HOST = os.environ.get("SMTP_HOST", "127.0.0.1")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "25"))

# 網段數量低於此值視為 API 回傳異常，寧可不更新也不要把白名單縮到幾乎全擋
MIN_IPV4, MIN_IPV6 = 10, 3


def fetch_cloudflare_ips() -> tuple[str, list[str], list[str]]:
    with urllib.request.urlopen(CF_IPS_URL, timeout=20) as resp:
        body = json.load(resp)
    if not body.get("success"):
        raise RuntimeError(f"Cloudflare /ips 回傳失敗：{body.get('errors')}")
    result = body["result"]
    ipv4, ipv6 = result["ipv4_cidrs"], result["ipv6_cidrs"]
    if len(ipv4) < MIN_IPV4 or len(ipv6) < MIN_IPV6:
        raise RuntimeError(f"網段數量異常（IPv4 {len(ipv4)}、IPv6 {len(ipv6)}），不更新")
    for cidr in ipv4 + ipv6:
        ipaddress.ip_network(cidr, strict=True)
    return result["etag"], ipv4, ipv6


def read_current() -> tuple[str | None, list[str]]:
    """從現有設定檔讀回 etag 與網段；檔案不存在時回傳 (None, [])。"""
    try:
        with open(OUTPUT, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        return None, []
    etag = next((l.split(":", 1)[1].strip() for l in lines if l.startswith("# etag:")), None)
    ranges = [l.strip()[2:].strip('"') for l in lines if l.strip().startswith('- "')]
    return etag, ranges


def write_config(etag: str, ranges: list[str]) -> None:
    content = "\n".join([
        "# 由 deploy/sync_cloudflare_ips.py 自動產生，請勿手動修改",
        f"# etag: {etag}",
        "http:",
        "  middlewares:",
        f"    {MIDDLEWARE}:",
        "      ipAllowList:",
        "        sourceRange:",
        *[f'          - "{r}"' for r in ranges],
        "",
    ])
    # 先寫暫存檔再 rename，Traefik 不會讀到寫一半的檔案；副檔名不是 .yml，不會被 file provider 載入
    out_dir = os.path.dirname(OUTPUT)
    fd, tmp = tempfile.mkstemp(dir=out_dir, prefix=".cloudflare-ips.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.chmod(tmp, 0o644)
        os.replace(tmp, OUTPUT)
    except BaseException:
        os.unlink(tmp)
        raise


def traefik_loaded_ranges() -> list[str]:
    """回傳 Traefik 實際載入的 cf-only 網段，用來確認新設定已生效。"""
    url = f"{TRAEFIK_API}/api/http/middlewares/{MIDDLEWARE}@file"
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.load(resp)["ipAllowList"]["sourceRange"]


def wait_until_loaded(ranges: list[str]) -> bool:
    for _ in range(10):
        try:
            if sorted(traefik_loaded_ranges()) == sorted(ranges):
                return True
        except Exception:
            pass
        time.sleep(3)
    return False


def send_mail(subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = f"[boss-timer] {subject}"
    msg["From"] = MAIL_FROM
    msg["To"] = MAIL_TO
    msg.set_content(body)
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
        smtp.send_message(msg)


def main() -> int:
    try:
        etag, ipv4, ipv6 = fetch_cloudflare_ips()
        ranges = ipv4 + ipv6
        old_etag, old_ranges = read_current()
        if etag == old_etag and sorted(ranges) == sorted(old_ranges):
            print(f"未變動（etag {etag}）")
            return 0

        write_config(etag, ranges)
        loaded = wait_until_loaded(ranges)
        added = sorted(set(ranges) - set(old_ranges))
        removed = sorted(set(old_ranges) - set(ranges))
        body = "\n".join([
            f"Cloudflare IP 網段已更新：etag {old_etag} → {etag}",
            f"設定檔：{OUTPUT}",
            f"Traefik 載入確認：{'成功' if loaded else '失敗，請手動檢查 Traefik'}",
            "",
            "新增：", *(added or ["（無）"]),
            "", "移除：", *(removed or ["（無）"]),
        ])
        print(body)
        send_mail("Cloudflare IP 網段已更新" if loaded else "Cloudflare IP 網段已更新，但 Traefik 未確認載入", body)
        return 0 if loaded else 1
    except Exception as e:
        body = f"同步 Cloudflare IP 網段失敗，cf-only 白名單維持舊版：\n\n{type(e).__name__}: {e}"
        print(body, file=sys.stderr)
        try:
            send_mail("Cloudflare IP 網段同步失敗", body)
        except Exception as mail_err:
            print(f"寄送失敗通知也失敗：{mail_err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
