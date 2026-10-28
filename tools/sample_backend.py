"""A small sample backend project for the dev-backend smoke test: files, and a repository built from them.

Nothing here is a real secret: the database is a throw-away container that trusts local connections.
"""

import subprocess
from pathlib import Path

ENCODING = "utf-8"
MAIN, DEVELOP = "main", "develop"
MIGRATIONS_DIR = "db/migrations"
UP_FILE = f"{MIGRATIONS_DIR}/0001_items.up.sql"
DOWN_FILE = f"{MIGRATIONS_DIR}/0001_items.down.sql"
SERVER_FILE = "app/server.py"
SPEC_FILE = "openapi.yaml"
CHECK_FILE = "tests/check_items.py"
GIT_IDENTITY = {"user.name": "Smoke", "user.email": "smoke@example.invalid", "commit.gpgsign": "false"}

# What the project looks like before the task: a service that answers 404 to everything.
SKELETON = {
    "README.md": "# Sample service\n\nA tiny HTTP service used to test dev-backend. The database is a throw-away container.\n",
    ".gitignore": "__pycache__/\n.env\n.claude/\n",
    "requirements.txt": "psycopg[binary]>=3.2\n",
    "Dockerfile": (
        "FROM python:3.12-slim\nWORKDIR /srv\nCOPY requirements.txt .\n"
        "RUN pip install --no-cache-dir -r requirements.txt\nCOPY app app\nCMD [\"python\", \"-m\", \"app.server\"]\n"
    ),
    "compose.yaml": (
        "services:\n"
        "  db:\n"
        "    image: postgres:16-alpine\n"
        "    environment:\n"
        "      POSTGRES_USER: app\n"
        "      POSTGRES_DB: app\n"
        "      # A throw-away local database: it trusts connections, so there is no password to keep.\n"
        "      POSTGRES_HOST_AUTH_METHOD: trust\n"
        "    volumes:\n"
        "      - ./db/migrations:/migrations:ro\n"
        "    healthcheck:\n"
        "      test: [\"CMD-SHELL\", \"pg_isready -U app -d app\"]\n"
        "      interval: 2s\n"
        "      timeout: 3s\n"
        "      retries: 30\n"
        "  api:\n"
        "    build: .\n"
        "    environment:\n"
        "      DATABASE_URL: postgresql://app@db:5432/app\n"
        "    ports:\n"
        "      - \"127.0.0.1:${API_PORT:-8000}:8000\"\n"
        "    depends_on:\n"
        "      db:\n"
        "        condition: service_healthy\n"
    ),
    "app/__init__.py": "",
    "db/migrations/.gitkeep": "",
    "tests/.gitkeep": "",
    SPEC_FILE: "openapi: 3.0.3\ninfo:\n  title: Items\n  version: 1.0.0\npaths: {}\n",
    SERVER_FILE: '''"""A small HTTP service: routes are functions that return (status, JSON body)."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROUTES = {}


class Handler(BaseHTTPRequestHandler):
    def send_json(self, status, payload, headers=None):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        route = ROUTES.get(self.path.split("?")[0])
        if route is None:
            self.send_json(404, {"error": "not found"})
            return
        status, payload = route()
        self.send_json(status, payload)

    def method_not_allowed(self):
        self.send_json(405, {"error": "method not allowed"}, {"Allow": "GET"})

    def __getattr__(self, name):
        # Any method but GET (POST, TRACE, OPTIONS, ...) is answered with 405 instead of the library's HTML 501 page.
        if name.startswith("do_"):
            return self.method_not_allowed
        raise AttributeError(name)

    def log_message(self, format, *args):
        pass


def main():
    ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()


if __name__ == "__main__":
    main()
''',
}

# What the db-engineer item adds.
MIGRATION_UP = """SET lock_timeout = '5s';
SET statement_timeout = '30s';

CREATE TABLE IF NOT EXISTS items (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name text NOT NULL
);
"""
MIGRATION_DOWN = """SET lock_timeout = '5s';
SET statement_timeout = '30s';

DROP TABLE IF EXISTS items;
"""

# What the implementer item adds.
SERVER_WITH_ITEMS = SKELETON[SERVER_FILE].replace(
    "import json\nfrom http.server",
    "import json\nimport os\nfrom http.server",
).replace(
    "ROUTES = {}\n",
    '''ROUTES = {}


def list_items():
    import psycopg

    with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
        rows = connection.execute("SELECT id, name FROM items ORDER BY id").fetchall()
    return 200, [{"id": row[0], "name": row[1]} for row in rows]


ROUTES["/items"] = list_items
''',
)
SPEC_WITH_ITEMS = """openapi: 3.0.3
info:
  title: Items
  version: 1.0.0
paths:
  /items:
    get:
      operationId: listItems
      responses:
        "200":
          description: All items.
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: "#/components/schemas/Item"
components:
  schemas:
    Item:
      type: object
      required: [id, name]
      properties:
        id:
          type: integer
          format: int64
        name:
          type: string
"""
CHECK_ITEMS = '''"""Calls the running service: GET /items must answer 200 with a JSON list."""

import json
import os
import urllib.request

with urllib.request.urlopen(os.environ["API_URL"] + "/items", timeout=10) as response:
    assert response.status == 200
    assert isinstance(json.load(response), list)
print("ok")
'''


def write_files(root: Path, files: dict[str, str]) -> None:
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode(ENCODING))


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, encoding=ENCODING, check=False)
    if done.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {done.stderr}")
    return done.stdout.strip()


def create_repo(base: Path) -> Path:
    """The sample project as a git repository with ``main`` and ``develop``, ``develop`` checked out."""
    repo = base / "sample-backend"
    repo.mkdir(parents=True)
    git(repo, "init", "-q", "-b", MAIN)
    for key, value in GIT_IDENTITY.items():
        git(repo, "config", key, value)
    write_files(repo, SKELETON)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "initial service")
    git(repo, "switch", "-q", "-c", DEVELOP)
    return repo
