"""Interactive startup authentication for TTS services.

Every service startup requires username/password authentication.
On success, a session token is generated and printed — use this token
in the X-API-Key header for all subsequent API requests.

Credentials are configured via environment variables:
  TTS_STARTUP_USER  — expected username (default: admin)
  TTS_STARTUP_PASS  — expected password (default: tts123)
"""

import os
import secrets
import sys

# Module-level token store — shared with auth.py via import
_startup_tokens: set = set()


def _read_password(prompt: str = "密码: ") -> str:
    """Read password input with masked echo on Windows, fallback to plain input."""
    try:
        import msvcrt

        sys.stdout.write(prompt)
        sys.stdout.flush()
        chars = []
        while True:
            ch = msvcrt.getch()
            if ch in (b"\r", b"\n"):
                sys.stdout.write("\n")
                break
            elif ch == b"\x08":  # backspace
                if chars:
                    chars.pop()
                    sys.stdout.write("\b \b")
            else:
                chars.append(ch.decode("utf-8", errors="ignore"))
                sys.stdout.write("*")
            sys.stdout.flush()
        return "".join(chars).strip()
    except (ImportError, AttributeError):
        return input(prompt).strip()


def require_startup_auth():
    """Prompt for username/password, generate a session token on success.

    The generated token must be sent as X-API-Key header in all API requests.
    The service exits if authentication fails.

    Modes:
      - Interactive (default): prompts for username/password
      - Docker / non-TTY:     skips prompts, reads TTS_STARTUP_TOKEN from env,
                               or auto-generates one if not set
    """
    expected_user = os.getenv("TTS_STARTUP_USER", "admin").strip()
    expected_pass = os.getenv("TTS_STARTUP_PASS", "tts123").strip()

    # Docker 模式 / 非交互终端 — 跳过交互，直接生成 token
    is_tty = sys.stdin.isatty() if hasattr(sys.stdin, "isatty") else False
    if not is_tty or os.path.exists("/.dockerenv"):
        token = os.getenv("TTS_STARTUP_TOKEN", "").strip()
        if not token:
            token = secrets.token_hex(32)
        _startup_tokens.add(token)

        print("\n" + "=" * 55)
        print("  TTS 服务启动 (非交互模式)")
        print("=" * 55)
        print(f"  API Token: {token}")
        print("  调用 API 时请在请求头中携带：")
        print(f"  X-API-Key: {token}")
        print("=" * 55 + "\n")
        return

    print("\n" + "=" * 55)
    print("  TTS 服务启动认证")
    print("=" * 55)

    username = ""
    while not username:
        username = input("用户名: ").strip()

    password = ""
    while not password:
        password = _read_password()

    if not secrets.compare_digest(username, expected_user) or \
       not secrets.compare_digest(password, expected_pass):
        print("\n认证失败，服务拒绝启动。")
        sys.exit(1)

    # 认证通过，生成会话 token
    token = secrets.token_hex(32)
    _startup_tokens.add(token)

    print("\n认证成功！服务启动中...")
    print("-" * 55)
    print(f"  API Token: {token}")
    print("-" * 55)
    print("  调用 API 时请在请求头中携带：")
    print(f'  X-API-Key: {token}')
    print("=" * 55 + "\n")
