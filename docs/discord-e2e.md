# Discord E2E control plane

This deployment is intentionally separate from the production bot. It uses a
temporary PostgreSQL filesystem and publishes the API only on the remote
host's loopback interface.

## Server layout

- Root: `/home/vulpo/CUHABot-e2e`
- Secret environment: `/home/vulpo/CUHABot-e2e/.env.e2e` (`0600`)
- Timestamp releases: `/home/vulpo/CUHABot-e2e/releases/<timestamp>`
- Active release: `/home/vulpo/CUHABot-e2e/current`

Never copy the production `.env` into this deployment. Start a release with
`deploy/e2e/deploy-release.sh <absolute-release-path>`.

## Access

Create an SSH tunnel and keep the API on loopback:

```text
ssh -N -L 8765:127.0.0.1:8765 -p 10022 vulpo@cuha.cju.ac.kr
```

Requests other than `/health` require `Authorization: Bearer <E2E_API_TOKEN>`.

```text
GET  /health
GET  /v1/test-suites
POST /v1/test-runs                    {"suite":"all"}
GET  /v1/test-runs/{run_id}
POST /v1/test-runs/{run_id}/visual-results
```

The API returns `202` while the FIFO worker posts a nonce command using the
driver bot. The dev bot must receive that message through the Discord Gateway
before execution begins. In the current deployment the separate driver
credential is invalid, so the DEV bot credential is deliberately configured as
the driver as well; this still proves Discord REST-to-Gateway delivery, but not
cross-bot identity separation.

`all` is the unattended functional gate. It covers real Gateway delivery,
Discord message/embed/component payload retrieval, component callback
execution, application commands, dungeon/tower flow, the deterministic
`semantics` suite, the `roguelike` route-state probe, and the `rewards`
transaction/idempotency probe. The checks use run-specific users in the
temporary database and delete them in `finally`.

The semantic contracts cover:

- attendance, cumulative EXP, level-derived stats, HP-ratio preservation, and healing;
- inventory stacking/consumption, shop buy/sell, equipment, enhancement, and collection;
- skill ownership/decks, combat restrictions, ultimate gauge/cooldown, and damage formulas;
- auction fees, locks, bid escrow/refunds, settlement, transfer, and buy-order refunds;
- mail rewards and duplicate-claim prevention, achievement events/mail, and rankings;
- tower mappings/rewards/progress and raid lobby/entry/clear progress;
- voice-channel/shared-instance transitions, proximity rules, spectator state, and combat history;
- seeded item/skill/dungeon/raid/achievement integrity and all registered minigames.

It does not require a Discord Web login or screenshots.

## Roguelike/reward rollout

The E2E database initializer runs
`scripts/migrate_roguelike_reward_system.py` after CSV seeding. Production must
run that additive migration explicitly before either feature is enabled; the bot
does not call `generate_schemas()` at runtime.

- `ROGUELIKE_DUNGEON_DEFAULT_ENABLED=TRUE|FALSE` controls the default normal
  dungeon route. `/서버설정 로그라이크` can override it per Guild.
- `BOX_REVEAL_ENABLED=TRUE|FALSE` independently controls atomic box opening and
  staged reveal. When disabled, the legacy box path remains active.
- `/서버설정 자랑채널` selects the only channel that can receive notable
  reward and roguelike-record announcements.
- `/상자천장` exposes all four user pity groups.

## Farming and Buildcraft V4 rollout

The initializer also runs `scripts/migrate_itemization_v4.py`. The migration
creates relational affixes, provenance, farming progress, crafting wallets,
integrated presets, protected auto-salvage rules, and idempotent action
receipts. Existing six-key `special_effects` rows are converted without
discarding ownership, grade, enhancement, or auction state.

The independent flags are `ITEMIZATION_V4_ENABLED`, `FARMING_FOCUS_ENABLED`,
`CRAFTING_V4_ENABLED`, `BUILD_PRESETS_V4_ENABLED`, and
`SET_EFFECTS_V4_ENABLED`. `/서버설정 v4기능` supplies an optional Guild
override for each flag. The `farming`, `buildcraft`, and `economy` suites cover
seal progress, integrated preset application, relational affixes, reforge and
salvage receipt replay, and Discord result embeds.

To validate after deployment, run `roguelike`, `rewards`, `farming`,
`buildcraft`, `economy`, then `all`. The
browser-only `visual` suite is deliberately excluded.

The optional `visual` suite stops at `awaiting_visual` until all eight browser
results are submitted. It is retained for manual use but is not part of the
functional completion condition.

Golden files are never updated by a failed comparison. The initial files are
saved only after explicit user approval and the manifest's `approved` flag is
then changed manually.
