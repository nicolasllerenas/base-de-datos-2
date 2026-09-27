#!/usr/bin/env bash
set -euo pipefail

ZIP="${1:-employee_db.zip}"
DB="employees"
TRABAJO="$(mktemp -d)"
trap 'rm -rf "$TRABAJO"' EXIT

unzip -o -q "$ZIP" -d "$TRABAJO"
TAR="$(find "$TRABAJO" -name '*.tar' | head -1)"

mkdir -p "$TRABAJO/dump"
tar -xf "$TAR" -C "$TRABAJO/dump"

psql -d postgres -v ON_ERROR_STOP=1 <<'SQL'
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'postgres') THEN
    CREATE ROLE postgres LOGIN SUPERUSER PASSWORD '123456';
  END IF;
END $$;
SQL

psql -d postgres -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS $DB;"
psql -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE $DB OWNER postgres;"

python3 - "$TRABAJO/dump" <<'PY'
import os, re, sys

d = sys.argv[1]
src = open(os.path.join(d, 'restore.sql')).read()
i = src.index('\\connect')
body = src[src.index('\n', i) + 1:]
body = body.replace('SET transaction_timeout = 0;', '')
body = re.sub(r'^\\(unrestrict|restrict).*$', '', body, flags=re.M)
body = re.sub(r'^COPY [^\n]*FROM stdin;\n\\\.\n', '', body, flags=re.M)
body = re.sub(r"^COPY ([^\n]*) FROM '\$\$PATH\$\$/([0-9]+\.dat)';",
              lambda m: f"\\copy {m.group(1)} FROM '{d}/{m.group(2)}'", body, flags=re.M)
open(os.path.join(d, 'restore_local.sql'), 'w').write(body)
PY

psql -U postgres -d "$DB" -v ON_ERROR_STOP=1 -q -f "$TRABAJO/dump/restore_local.sql"
psql -U postgres -d "$DB" -c "ANALYZE;"
psql -U postgres -d "$DB" -c "\dt employees.*"
