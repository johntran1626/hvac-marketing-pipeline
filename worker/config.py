"""Read the worker's secrets. Never print them.

GitHub Actions passes them as environment variables. Locally they come from .env.local.
"""
import os

REQUIRED = ("LAB_API_KEY", "SUPABASE_URL", "SUPABASE_SECRET_KEY")


def load_env(path=".env.local"):
    env = {k: os.environ[k] for k in REQUIRED if os.environ.get(k)}
    if len(env) < len(REQUIRED) and os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    if k in REQUIRED and k not in env:
                        env[k] = v.strip().strip("\"'")
    missing = [k for k in REQUIRED if not env.get(k)]
    if missing:
        raise SystemExit(f"Missing {', '.join(missing)} (set them as env vars or in {path})")
    return env
