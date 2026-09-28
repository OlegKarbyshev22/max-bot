#!/bin/sh
set -eu

for migration in /opt/max-bot/migrations/*.sql; do
  echo "Applying $(basename "$migration")"
  psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    --set=ON_ERROR_STOP=1 --file="$migration"
done
