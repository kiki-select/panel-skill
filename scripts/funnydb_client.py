"""
panel-skill 共享 FunnyDB 客户端：定位 Git Bash、调用 funnydb shim、处理反引号转义。

被 create_panel.py / create_dashboard.py 复用。设计与 ds-skill/scripts/run_sql.py 一致。

平台说明：
- Windows 必须通过 Git Bash 调 funnydb shim（shim 自身再调 wsl）。
  Windows PATH 里的 bash 常优先指向 WSL 的 bash.exe，会让 shim 在 WSL 内找不到 wsl 命令。
  脚本自动定位 Git Bash；非标准位置请设 GIT_BASH 环境变量。
- macOS/Linux 直接用 PATH 里的 bash。
"""
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

# 反引号 / 反斜杠用 chr() 表示，避免源码里的字面量被 shell/heredoc 误处理
BACKTICK = chr(96)
BACKSLASH = chr(92)

GIT_BASH_CANDIDATES = [
    os.environ.get("GIT_BASH"),
    r"C:\Program Files\Git\usr\bin\bash.exe",
    r"C:\Program Files\Git\bin\bash.exe",
    r"C:\Program Files (x86)\Git\usr\bin\bash.exe",
]


def find_bash() -> str:
    """挑当前平台正确的 bash。"""
    if platform.system() == "Windows":
        for cand in GIT_BASH_CANDIDATES:
            if cand and Path(cand).exists():
                return cand
        found = shutil.which("bash")
        if found and "System32" not in found and "WindowsApps" not in found:
            return found
        raise RuntimeError(
            "Windows 上未找到 Git Bash。请设置 GIT_BASH 环境变量或安装 Git for Windows。"
        )
    found = shutil.which("bash")
    if not found:
        raise RuntimeError("PATH 中找不到 bash")
    return found


def escape_payload(payload: dict) -> str:
    """序列化 payload，并把反引号转成 \u0060 字面，规避 WSL bash -c 的命令替换吞噬。"""
    s = json.dumps(payload, ensure_ascii=False)
    return s.replace(BACKTICK, BACKSLASH + "u0060")


def call(funnydb_dir: str, path: str, payload: dict) -> dict:
    """POST 到 funnydb skillhub，返回解开 envelope 后的 data。失败直接退出并打印错误。"""
    if not Path(funnydb_dir).is_dir():
        raise RuntimeError(f"funnydb skill 目录不存在: {funnydb_dir}")

    payload_json = escape_payload(payload)
    result = subprocess.run(
        [find_bash(), "scripts/funnydb", "post", path, "--data", payload_json],
        cwd=funnydb_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        sys.stderr.write(result.stderr or result.stdout)
        sys.exit(result.returncode)

    try:
        resp = json.loads(result.stdout)
    except json.JSONDecodeError:
        sys.stderr.write(f"funnydb 返回非 JSON:\n{result.stdout}\n")
        sys.exit(1)

    # 两种 envelope：{"code":0,"data":{...}} 或顶层直接是结果
    if isinstance(resp, dict) and "code" in resp and resp["code"] not in (0, "0"):
        sys.stderr.write(f"FunnyDB 报错: {json.dumps(resp, ensure_ascii=False, indent=2)}\n")
        sys.exit(1)
    return resp.get("data", resp) if isinstance(resp, dict) else resp


def resolve_env(app_id, funnydb_dir):
    """统一处理 app_id / funnydb_dir 的 CLI 参数与环境变量回退。"""
    app_id = app_id or os.environ.get("FUNNYDB_APP_ID")
    if not app_id:
        sys.exit("error: --app-id 必填（或设置 FUNNYDB_APP_ID 环境变量）")
    funnydb_dir = funnydb_dir or os.environ.get("FUNNYDB_SKILL_DIR")
    if not funnydb_dir:
        sys.exit("error: --funnydb-dir 必填（或设置 FUNNYDB_SKILL_DIR 环境变量）")
    return int(app_id), funnydb_dir
