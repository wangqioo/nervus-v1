#!/bin/bash
set -e

PGDATA="${PGDATA:-/var/lib/postgresql/data/pgdata}"
PGBIN="/usr/lib/postgresql/16/bin"
PG_USER="${POSTGRES_USER:-nervus}"
PG_DB="${POSTGRES_DB:-nervus}"
PG_PASS="${POSTGRES_PASSWORD:-nervus_secret}"

echo "==> PGDATA=$PGDATA"

mkdir -p "$PGDATA"
chown postgres:postgres "$PGDATA"
chmod 700 "$PGDATA"

if [ ! -f "$PGDATA/PG_VERSION" ]; then
    echo "==> Initializing PostgreSQL 16 database..."

    su -s /bin/bash postgres -c "$PGBIN/initdb -D $PGDATA --encoding=UTF8 --locale=C"

    echo "host all all 0.0.0.0/0 md5" >> "$PGDATA/pg_hba.conf"
    echo "host all all ::/0 md5" >> "$PGDATA/pg_hba.conf"
    sed -i "s/#listen_addresses = 'localhost'/listen_addresses = '*'/" "$PGDATA/postgresql.conf"

    echo "==> Starting temporary server for setup..."
    su -s /bin/bash postgres -c "$PGBIN/pg_ctl -D $PGDATA start -w -l /tmp/pg_init.log"

    echo "==> Creating user and database..."
    cat > /tmp/pg_setup.sql << SQL
CREATE USER "$PG_USER" WITH PASSWORD '$PG_PASS';
CREATE DATABASE "$PG_DB" WITH OWNER = "$PG_USER" ENCODING = 'UTF8';
GRANT ALL PRIVILEGES ON DATABASE "$PG_DB" TO "$PG_USER";
SQL
    su -s /bin/bash postgres -c "$PGBIN/psql -v ON_ERROR_STOP=1 -f /tmp/pg_setup.sql"
    rm /tmp/pg_setup.sql

    if [ -f "/docker-entrypoint-initdb.d/init.sql" ]; then
        echo "==> Running init.sql..."
        su -s /bin/bash postgres -c "$PGBIN/psql -v ON_ERROR_STOP=1 -U postgres -d $PG_DB -f /docker-entrypoint-initdb.d/init.sql"
    fi

    echo "==> Stopping temporary server..."
    su -s /bin/bash postgres -c "$PGBIN/pg_ctl -D $PGDATA stop -m fast"
    echo "==> Initialization complete."
fi

echo "==> Starting PostgreSQL 16..."
exec su -s /bin/bash postgres -c "exec $PGBIN/postgres -D $PGDATA"
