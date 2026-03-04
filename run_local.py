#!/usr/bin/env python3
"""
Run the Climate Anomaly Engine locally without Docker Compose.

Starts a PostGIS container (optional), the FastAPI backend, and the React
frontend dev server — all from a single command.

Usage:
    python run_local.py                  # DB + API + frontend
    python run_local.py --no-db          # skip PostGIS container
    python run_local.py --skip-install   # skip pip/npm install
    python run_local.py --build          # production build + preview
"""

import argparse
import os
import platform
import shutil
import signal
import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"
INIT_SQL = ROOT / "docker" / "postgis" / "init.sql"
SEED_SCRIPT = ROOT / "scripts" / "seed_local_db.py"
VENV_DIR = BACKEND_DIR / ".venv"
ENV_FILE = ROOT / ".env"

IS_WIN = platform.system() == "Windows"

# ---------------------------------------------------------------------------
# PostGIS container defaults
# ---------------------------------------------------------------------------
CONTAINER_NAME = "climate-postgis-local"
DB_IMAGE = "postgis/postgis:16-3.4"
DB_PORT = "5432"
DB_USER = "climate"
DB_PASSWORD = "climate_secret"
DB_NAME = "climate_db"

# ---------------------------------------------------------------------------
# ANSI helpers (modern Windows Terminal supports these)
# ---------------------------------------------------------------------------
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"

DB_TAG = f"{CYAN}[DB ]{RESET}"
API_TAG = f"{GREEN}[API]{RESET}"
WEB_TAG = f"{BLUE}[WEB]{RESET}"
SYS_TAG = f"{YELLOW}[SYS]{RESET}"

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------
_children: list[subprocess.Popen] = []
_shutting_down = False


def log(tag: str, msg: str) -> None:
    print(f"{tag} {msg}", flush=True)


def banner() -> None:
    print(
        f"\n{BOLD}{'=' * 60}\n"
        f"  Climate Anomaly Engine  —  Local Runner\n"
        f"{'=' * 60}{RESET}\n"
    )


# ---------------------------------------------------------------------------
# Prerequisite checks
# ---------------------------------------------------------------------------
def _cmd_version(name: str, args: list[str]) -> str | None:
    if shutil.which(name) is None:
        return None
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=10)
        return (r.stdout.strip() or r.stderr.strip()) or "found"
    except Exception:
        return "found"


def check_prerequisites(need_docker: bool) -> None:
    log(SYS_TAG, "Checking prerequisites ...")
    ok = True

    v = sys.version_info
    if v >= (3, 11):
        log(SYS_TAG, f"  Python {v.major}.{v.minor}.{v.micro}")
    else:
        log(SYS_TAG, f"  {RED}Python {v.major}.{v.minor} — need 3.11+{RESET}")
        ok = False

    nv = _cmd_version("node", ["node", "--version"])
    if nv:
        log(SYS_TAG, f"  Node.js {nv}")
    else:
        log(SYS_TAG, f"  {RED}Node.js not found (need 18+){RESET}")
        ok = False

    npv = _cmd_version("npm", ["npm", "--version"])
    if npv:
        log(SYS_TAG, f"  npm {npv}")
    else:
        log(SYS_TAG, f"  {RED}npm not found{RESET}")
        ok = False

    if need_docker:
        dv = _cmd_version("docker", ["docker", "--version"])
        if dv:
            log(SYS_TAG, f"  Docker {dv}")
        else:
            log(SYS_TAG, f"  {RED}Docker not found — needed for PostGIS (use --no-db to skip){RESET}")
            ok = False

    if not ok:
        log(SYS_TAG, f"\n{RED}Missing prerequisites. Install them and try again.{RESET}")
        sys.exit(1)

    log(SYS_TAG, "  All prerequisites met.\n")


# ---------------------------------------------------------------------------
# .env loading
# ---------------------------------------------------------------------------
def _load_dotenv(path: Path) -> dict[str, str]:
    """Minimal .env parser — no dependency needed."""
    env: dict[str, str] = {}
    if not path.is_file():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip()
    return env


# ---------------------------------------------------------------------------
# PostGIS container management
# ---------------------------------------------------------------------------
def _container_running() -> bool | None:
    """Return True if running, False if stopped, None if absent."""
    r = subprocess.run(
        ["docker", "inspect", "--format", "{{.State.Running}}", CONTAINER_NAME],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        return None
    return r.stdout.strip().lower() == "true"


def _wait_for_db(timeout: int = 60) -> None:
    log(DB_TAG, "Waiting for database to accept connections ...")
    t0 = time.time()
    while time.time() - t0 < timeout:
        r = subprocess.run(
            ["docker", "exec", CONTAINER_NAME, "pg_isready", "-U", DB_USER],
            capture_output=True,
            text=True,
        )
        if r.returncode == 0:
            log(DB_TAG, f"Database ready ({time.time() - t0:.1f}s).\n")
            return
        time.sleep(1)
    log(DB_TAG, f"{RED}Database not ready after {timeout}s — aborting.{RESET}")
    sys.exit(1)


def start_postgis() -> None:
    state = _container_running()

    if state is True:
        log(DB_TAG, f"Container '{CONTAINER_NAME}' already running.")
        _wait_for_db()
        return

    if state is False:
        log(DB_TAG, f"Starting stopped container '{CONTAINER_NAME}' ...")
        subprocess.run(["docker", "start", CONTAINER_NAME], check=True,
                        capture_output=True)
        _wait_for_db()
        return

    log(DB_TAG, f"Creating container '{CONTAINER_NAME}' ...")
    cmd: list[str] = [
        "docker", "run", "-d",
        "--name", CONTAINER_NAME,
        "-p", f"{DB_PORT}:5432",
        "-e", f"POSTGRES_USER={DB_USER}",
        "-e", f"POSTGRES_PASSWORD={DB_PASSWORD}",
        "-e", f"POSTGRES_DB={DB_NAME}",
    ]
    if INIT_SQL.is_file():
        cmd += ["-v", f"{INIT_SQL}:/docker-entrypoint-initdb.d/init.sql:ro"]
    cmd.append(DB_IMAGE)
    subprocess.run(cmd, check=True, capture_output=True)
    _wait_for_db()


def stop_postgis() -> None:
    log(DB_TAG, f"Stopping container '{CONTAINER_NAME}' ...")
    subprocess.run(["docker", "stop", CONTAINER_NAME], capture_output=True)


# ---------------------------------------------------------------------------
# Venv helpers
# ---------------------------------------------------------------------------
def _venv_python() -> str:
    if IS_WIN:
        return str(VENV_DIR / "Scripts" / "python.exe")
    return str(VENV_DIR / "bin" / "python")


def _venv_pip() -> str:
    if IS_WIN:
        return str(VENV_DIR / "Scripts" / "pip.exe")
    return str(VENV_DIR / "bin" / "pip")


# ---------------------------------------------------------------------------
# Dependency installation
# ---------------------------------------------------------------------------
def setup_backend(skip_install: bool) -> None:
    log(API_TAG, "Setting up backend ...")

    if not VENV_DIR.exists():
        log(API_TAG, f"Creating virtual environment ({VENV_DIR.relative_to(ROOT)}) ...")
        subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True)
    else:
        log(API_TAG, "Virtual environment already exists.")

    if skip_install:
        log(API_TAG, "Skipping pip install (--skip-install).\n")
        return

    log(API_TAG, "Installing backend dependencies ...")
    result = subprocess.run(
        [_venv_pip(), "install", "-r", str(BACKEND_DIR / "requirements.txt")],
        cwd=str(BACKEND_DIR),
    )
    if result.returncode != 0:
        log(API_TAG, f"{RED}pip install failed (exit code {result.returncode}).{RESET}")
        log(API_TAG, f"{YELLOW}Hint: If a package failed to build, you may need to "
            f"install its system-level dependency or update the pin in "
            f"backend/requirements.txt.{RESET}")
        sys.exit(1)
    log(API_TAG, "Backend dependencies installed.\n")


def setup_frontend(skip_install: bool) -> None:
    log(WEB_TAG, "Setting up frontend ...")
    node_modules = FRONTEND_DIR / "node_modules"

    if skip_install:
        if not node_modules.exists():
            log(WEB_TAG, f"{YELLOW}Warning: node_modules missing but --skip-install set.{RESET}\n")
        else:
            log(WEB_TAG, "Skipping npm install (--skip-install).\n")
        return

    log(WEB_TAG, "Installing frontend dependencies ...")
    subprocess.run(
        ["npm", "install"],
        check=True,
        cwd=str(FRONTEND_DIR),
        shell=IS_WIN,
    )
    log(WEB_TAG, "Frontend dependencies installed.\n")


# ---------------------------------------------------------------------------
# Process streaming
# ---------------------------------------------------------------------------
def _pipe_lines(stream, tag: str) -> None:
    """Forward lines from a subprocess stream to stdout with a tag prefix."""
    try:
        for line in iter(stream.readline, ""):
            if _shutting_down:
                break
            if line:
                print(f"{tag} {line}", end="", flush=True)
    except (ValueError, OSError):
        pass


def _spawn(
    cmd: list[str],
    tag: str,
    *,
    cwd: str,
    env: dict[str, str] | None = None,
    shell: bool = False,
) -> subprocess.Popen:
    """Spawn a subprocess and stream its output with the given tag."""
    kwargs: dict = dict(
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        shell=shell,
    )
    if env is not None:
        kwargs["env"] = env
    if IS_WIN:
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

    proc = subprocess.Popen(cmd, **kwargs)
    _children.append(proc)

    threading.Thread(target=_pipe_lines, args=(proc.stdout, tag), daemon=True).start()
    threading.Thread(target=_pipe_lines, args=(proc.stderr, tag), daemon=True).start()
    return proc


# ---------------------------------------------------------------------------
# Service launchers
# ---------------------------------------------------------------------------
def _backend_env() -> dict[str, str]:
    """Build the environment for the backend process.

    Loads the project-root .env, then forces POSTGRES_HOST=localhost so the
    backend connects to the local / Docker-managed database instead of the
    Docker-network hostname 'postgis'.
    """
    env = os.environ.copy()
    env.update(_load_dotenv(ENV_FILE))
    env["POSTGRES_HOST"] = "localhost"
    return env


def start_backend() -> subprocess.Popen:
    log(API_TAG, "Starting backend  (uvicorn --reload on :8000) ...")
    return _spawn(
        [_venv_python(), "-m", "uvicorn", "app.main:app", "--reload",
         "--host", "0.0.0.0", "--port", "8000"],
        API_TAG,
        cwd=str(BACKEND_DIR),
        env=_backend_env(),
    )


def start_frontend(build_mode: bool) -> subprocess.Popen:
    if build_mode:
        log(WEB_TAG, "Building frontend for production ...")
        subprocess.run(
            ["npm", "run", "build"],
            check=True,
            cwd=str(FRONTEND_DIR),
            shell=IS_WIN,
        )
        log(WEB_TAG, "Starting preview server on :5173 ...")
        cmd = ["npm", "run", "preview"]
    else:
        log(WEB_TAG, "Starting frontend dev server on :5173 ...")
        cmd = ["npm", "run", "dev"]

    return _spawn(cmd, WEB_TAG, cwd=str(FRONTEND_DIR), shell=IS_WIN)


# ---------------------------------------------------------------------------
# Shutdown
# ---------------------------------------------------------------------------
def _kill_tree(pid: int) -> None:
    """Kill the entire process tree (works on Windows and Unix)."""
    if IS_WIN:
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            capture_output=True,
        )
    else:
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass


def shutdown(*, stop_db: bool) -> None:
    global _shutting_down
    if _shutting_down:
        return
    _shutting_down = True

    print()
    log(SYS_TAG, "Shutting down ...")

    for proc in _children:
        try:
            _kill_tree(proc.pid)
        except Exception:
            pass

    for proc in _children:
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        except Exception:
            pass

    if stop_db:
        stop_postgis()

    log(SYS_TAG, "Goodbye.\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the Climate Anomaly Engine locally (no Docker Compose).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            examples:
              python run_local.py                  Start DB + API + frontend
              python run_local.py --no-db          Bring your own PostgreSQL
              python run_local.py --skip-install   Skip pip/npm install for fast restarts
              python run_local.py --build          Production build + vite preview
        """),
    )
    parser.add_argument("--no-db", action="store_true",
                        help="skip starting the PostGIS Docker container")
    parser.add_argument("--skip-install", action="store_true",
                        help="skip pip install and npm install steps")
    parser.add_argument("--build", action="store_true",
                        help="production build + vite preview instead of dev server")
    parser.add_argument("--seed", action="store_true",
                        help="seed the database with sample data for local dev")
    args = parser.parse_args()

    banner()
    check_prerequisites(need_docker=not args.no_db)

    # --- database -----------------------------------------------------------
    if args.no_db:
        log(DB_TAG, "Skipping database (--no-db).\n")
    else:
        start_postgis()

    # --- install dependencies -----------------------------------------------
    setup_backend(args.skip_install)
    setup_frontend(args.skip_install)

    # --- seed database ------------------------------------------------------
    if args.seed:
        log(DB_TAG, "Seeding database with sample data ...")
        result = subprocess.run(
            [_venv_python(), str(SEED_SCRIPT)],
            cwd=str(ROOT),
            env=_backend_env(),
        )
        if result.returncode != 0:
            log(DB_TAG, f"{RED}Seed script failed (exit code {result.returncode}).{RESET}")
            sys.exit(1)
        log(DB_TAG, "Database seeded.\n")

    # --- start services -----------------------------------------------------
    api_proc = start_backend()
    web_proc = start_frontend(args.build)

    print(
        f"\n{BOLD}{'=' * 60}\n"
        f"  Frontend : http://localhost:5173\n"
        f"  API      : http://localhost:8000\n"
        f"  API Docs : http://localhost:8000/docs\n"
        f"\n"
        f"  Press Ctrl+C to stop all services.\n"
        f"{'=' * 60}{RESET}\n"
    )

    # --- wait / watch -------------------------------------------------------
    stop_db = not args.no_db

    def on_signal(sig, _frame):
        shutdown(stop_db=stop_db)
        sys.exit(0)

    signal.signal(signal.SIGINT, on_signal)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, on_signal)

    try:
        while True:
            for proc in _children:
                rc = proc.poll()
                if rc is not None:
                    name = "Backend" if proc is api_proc else "Frontend"
                    log(SYS_TAG, f"{RED}{name} exited (code {rc}).{RESET}")
                    shutdown(stop_db=stop_db)
                    sys.exit(rc or 1)
            time.sleep(0.5)
    except KeyboardInterrupt:
        shutdown(stop_db=stop_db)


if __name__ == "__main__":
    main()
