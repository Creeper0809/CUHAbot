# Synology NAS deployment

CUHABot runs as the isolated Compose project `cuhabot-nas` under
`/volume1/docker/cuhabot`. PostgreSQL is reachable only on the private Docker
network and has no host port mapping.

The NAS Compose file pulls the official Docker Library images through
Google's read-only registry mirror because this NAS Docker version does not
fall back from an unreachable IPv6 CloudFront endpoint. The ordinary
`Dockerfile` default remains Docker Hub for local and development builds.

SSH uses the local `dungeonstory-nas` alias on NAS port 9906. The current DDNS
router configuration does not forward that SSH port, so deployment commands
must run from the same LAN (or through a separately configured VPN).

## Layout

- Releases: `/volume1/docker/cuhabot/releases/<UTC timestamp>`
- Active release: `/volume1/docker/cuhabot/current`
- Secrets: `/volume1/docker/cuhabot/.env.nas` (`0600`)
- PostgreSQL data: `/volume1/docker/cuhabot/postgres`
- Backups: `/volume1/docker/cuhabot/backups` (`0700` directory, `0600` files)

## Operations

Run these commands through the configured `dungeonstory-nas` SSH host and
`sudo`. Do not expose PostgreSQL's 5432 port through DSM or the router.

```text
cd /volume1/docker/cuhabot/current
sudo /usr/local/bin/docker-compose -p cuhabot-nas --env-file .env.nas -f docker-compose.nas.yml ps
sudo /usr/local/bin/docker-compose -p cuhabot-nas --env-file .env.nas -f docker-compose.nas.yml logs --tail=200 bot
sudo sh deploy/nas/backup.sh
```

Restore requires an explicit `--execute` flag and stops the bot while the
database is replaced:

```text
sudo sh deploy/nas/restore.sh --execute /volume1/docker/cuhabot/backups/<file>.dump
```

Updates are uploaded to a new timestamped release and activated with
`sudo sh deploy/nas/activate-release.sh <absolute-release-path>`. The `current`
symlink changes only after migrations and the bot health check succeed.

`FORCE_SYNC` is enabled for the first boot only. After Discord reports the
expected guild command count, set it back to `FALSE` and recreate only the bot.
This avoids deleting and recreating application commands on every NAS restart.

The bot account must also be invited to the `CUHAbot-Emoji` guild if custom
emoji rendering is required. Missing that optional guild does not stop the bot,
database, commands, or gameplay services, but it produces a startup warning and
falls back from the custom emoji initialization path.

## Beginner recovery update (2026-09)

`db-init` now runs `scripts/prepare_nas_database.py`. Populated databases use
the targeted, additive `update_beginner_static.py`; CSV installation requires
`seed_from_csv.py --fresh` and refuses an existing account/static dataset.
Never run the legacy reset helper to update a live server.

Before activating this patch, place the passing `beginner-validation.json`,
`beginner-upgrade-verified.json`, and `beginner-discord-verified.json` in the new
release. The PostgreSQL upgrade probe only accepts a restored database whose
name ends in `_beginner_check`; it checks repeated migration and concurrent
registration/legacy repair without modifying production accounts.

Activation builds before freezing admission. It briefly SIGSTOPs the legacy
bot, requires its complete startup/session log to prove zero active runs and
at least 60 seconds since the last session event, takes a fresh custom-format
backup, then compares all preserved table content hashes before/after the
targeted migration. An idle-check failure only resumes the existing process;
it must not restart a bot that still has an active run.

After activation, check fresh Gateway login/static-cache logs and the actual
Discord payload probe as well as container health. The health check alone is
not a gameplay or Gateway proof. Probe results distinguish REST message
validation from a human slash-command/button input.

Existing Lv1--10 users receive the once-only missing starter skills/deck repair
and HP restoration on their first account-required command outside a session.
Custom decks, equipment, enhancement, currency and farming progress survive.
