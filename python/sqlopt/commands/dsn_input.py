"""
DSN Interactive Input Module

Provides interactive DSN configuration functionality for baseline and branch commands.
Prompts users for database connection details when DSN contains placeholders.
"""

import sys

# Windows UTF-8 encoding fix
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass  # Fallback to default if reconfigure not available

import getpass
import os
import re
from pathlib import Path
from typing import Optional


def is_interactive() -> bool:
    """检测是否在交互式环境中"""
    return sys.stdin.isatty() and sys.stdout.isatty()


def _report_non_interactive_error(dsn: str, platform: str) -> None:
    """报告非交互环境的 DSN 配置错误"""
    print("\n" + "=" * 60, file=sys.stderr)
    print("[FAIL] 错误：数据库连接未配置", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(file=sys.stderr)
    print("当前环境：非交互式（无法提示输入）", file=sys.stderr)
    print(f"检测到 DSN 包含占位符：{dsn}", file=sys.stderr)
    print(file=sys.stderr)
    print("请手动配置 sqlopt.yml 文件：", file=sys.stderr)
    print(file=sys.stderr)
    print("  db:", file=sys.stderr)
    print(f"    platform: {platform}", file=sys.stderr)
    if platform == "postgresql":
        print(
            "    dsn: postgresql://myuser:mypass@127.0.0.1:5432/mydb?sslmode=disable",
            file=sys.stderr,
        )
    else:
        print("    dsn: mysql://myuser:mypass@127.0.0.1:3306/mydb", file=sys.stderr)
    print(file=sys.stderr)
    print("或使用环境变量：", file=sys.stderr)
    print(file=sys.stderr)
    if platform == "postgresql":
        print(
            '  export SQLOPT_DSN="postgresql://myuser:mypass@127.0.0.1:5432/mydb"',
            file=sys.stderr,
        )
    else:
        print(
            '  export SQLOPT_DSN="mysql://myuser:mypass@127.0.0.1:3306/mydb"',
            file=sys.stderr,
        )
    print(file=sys.stderr)
    print("或使用命令行参数：", file=sys.stderr)
    print(file=sys.stderr)
    print(
        '  sqlopt-cli baseline --file mapper.xml --sql-id xxx --dsn "..."',
        file=sys.stderr,
    )
    print(file=sys.stderr)
    print("【禁止】系统不会自动从其他配置文件推断 DSN", file=sys.stderr)
    print("=" * 60, file=sys.stderr)


def check_and_prompt_dsn(
    config: dict,
    config_path: Optional[str] = None,
    force_prompt: bool = False,
    cli_dsn: Optional[str] = None,
) -> dict:
    """
    Check DSN configuration and prompt user for input if placeholders are detected.

    Args:
        config: Configuration dictionary containing 'db' section
        config_path: Optional path to config file for saving
        force_prompt: If True, always prompt even without placeholders
        cli_dsn: DSN from command line (highest priority)

    Returns:
        Updated configuration dictionary with DSN set
    """
    db_config = config.get("db", {})
    dsn = db_config.get("dsn", "")

    # 优先使用命令行参数
    if cli_dsn:
        config["db"] = config.get("db", {})
        config["db"]["dsn"] = cli_dsn
        return config

    # 检查环境变量
    env_dsn = os.environ.get("SQLOPT_DSN")
    if env_dsn:
        config["db"] = config.get("db", {})
        config["db"]["dsn"] = env_dsn
        return config

    # 检查占位符
    placeholders = ["<user>", "<password>", "<database>", "<host>", "<dbname>"]
    has_placeholder = any(p.lower() in dsn.lower() for p in placeholders)

    if not has_placeholder and not force_prompt:
        return config

    # 非交互环境检查
    if not is_interactive():
        _report_non_interactive_error(dsn, db_config.get("platform", "postgresql"))
        sys.exit(1)

    # 交互环境提示用户输入
    print("\n" + "=" * 60, file=sys.stderr)
    print("[WARN]  数据库连接未配置", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    if has_placeholder:
        print("检测到 DSN 包含占位符，无法连接数据库", file=sys.stderr)
    else:
        print("用户要求配置数据库连接", file=sys.stderr)
    print(file=sys.stderr)

    # Interactive input
    platform = db_config.get("platform", "postgresql")

    # Get defaults
    default_port = "5432" if platform == "postgresql" else "3306"
    default_host = "127.0.0.1"
    default_user = "postgres"

    # Try to parse existing DSN for defaults
    if dsn and not has_placeholder:
        parsed = _parse_dsn(dsn, platform)
        if parsed:
            default_host = parsed.get("host", default_host)
            default_port = parsed.get("port", default_port)
            default_user = parsed.get("user", default_user)

    print("请配置数据库连接信息：", file=sys.stderr)
    print(file=sys.stderr)

    # Get input with defaults
    host_input = input(f"主机 [{default_host}]: ").strip()
    host = host_input or default_host

    port_input = input(f"端口 [{default_port}]: ").strip()
    port = port_input or default_port

    user_input = input(f"用户名 [{default_user}]: ").strip()
    user = user_input or default_user

    password = getpass.getpass("密码: ")

    database = input("数据库名: ").strip()

    # Validate input
    if not database:
        print("\n[FAIL] 数据库名不能为空，将使用现有配置继续执行", file=sys.stderr)
        return config

    if not password:
        print("\n[WARN] 密码为空，将使用空密码连接", file=sys.stderr)

    # Build DSN
    if platform == "postgresql":
        new_dsn = (
            f"postgresql://{user}:{password}@{host}:{port}/{database}?sslmode=disable"
        )
    else:
        new_dsn = f"mysql://{user}:{password}@{host}:{port}/{database}"

    # Update config
    config["db"] = config.get("db", {})
    config["db"]["dsn"] = new_dsn

    print(file=sys.stderr)
    print(f"[OK] DSN 已配置: {mask_dsn(new_dsn)}", file=sys.stderr)
    print(file=sys.stderr)

    # Ask to test connection
    test = input("是否测试数据库连接？[Y/n]: ").strip().lower() or "y"
    if test == "y":
        if test_db_connection(config):
            print("\n[OK] 数据库连接成功！", file=sys.stderr)
        else:
            print("\n[FAIL] 数据库连接失败，请检查配置后重试", file=sys.stderr)
            # Don't exit, allow user to continue with existing config

    print(file=sys.stderr)

    return config


def mask_dsn(dsn: str) -> str:
    """Hide password in DSN."""
    # Match patterns like: postgresql://user:pass@host:port/db or mysql://user:pass@host:port/db
    pattern = r"://([^:]+):([^@]+)@"
    return re.sub(pattern, r"://\1:***@", dsn)


def _parse_dsn(dsn: str, platform: str = "postgresql") -> Optional[dict]:
    """Parse DSN to extract connection parameters."""
    try:
        if platform == "postgresql":
            # postgresql://user:password@host:port/database?sslmode=disable
            pattern = r"postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/([^?]+)"
            match = re.match(pattern, dsn)
            if match:
                return {
                    "user": match.group(1),
                    "password": match.group(2),
                    "host": match.group(3),
                    "port": match.group(4),
                    "database": match.group(5),
                }
        else:
            # mysql://user:password@host:port/database
            pattern = r"mysql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)"
            match = re.match(pattern, dsn)
            if match:
                return {
                    "user": match.group(1),
                    "password": match.group(2),
                    "host": match.group(3),
                    "port": match.group(4),
                    "database": match.group(5),
                }
    except Exception:
        pass
    return None


def test_db_connection(config: dict) -> bool:
    """Test database connection."""
    platform = config.get("db", {}).get("platform", "postgresql")
    dsn = config.get("db", {}).get("dsn", "")

    if not dsn:
        print("DSN 未配置", file=sys.stderr)
        return False

    try:
        if platform == "postgresql":
            import psycopg2

            conn = psycopg2.connect(dsn)
            conn.close()
            return True
        else:
            import pymysql

            parsed = _parse_dsn(dsn, platform)
            if parsed:
                conn = pymysql.connect(
                    host=parsed["host"],
                    port=int(parsed["port"]),
                    user=parsed["user"],
                    password=parsed["password"],
                    database=parsed["database"],
                )
                conn.close()
                return True
    except ImportError:
        print("数据库驱动未安装", file=sys.stderr)
    except Exception as e:
        print(f"连接失败: {e}", file=sys.stderr)

    return False
