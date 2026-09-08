# Smart Mapper

Maps pharmaceutical distributor sales-report customer records (Arabic name/address,
distributor-specific codes) onto the company's own customer master, despite
inconsistent coding, abbreviations, and address formatting between distributors.

## Safety model

- The database credential in `CORE_DB_URL` should be **read-only at the DB grant
  level** against the core customer master and historical mapping tables. This
  codebase never issues INSERT/UPDATE/DELETE against those tables - see
  `smart_mapper/db/core_models.py`.
- All mapper output goes into three new tables it owns
  (`distributor_customer_mapping`, `run_audit_log`, `review_decisions`),
  created only by the explicit `smart-mapper init-staging-db` command - never
  automatically, and never touching any existing table.
- Nothing is ever auto-created in the core customer database. Genuinely new
  customers are written to `new_customer_onboarding.xlsx` for a human to
  verify and create manually.

## Setup

```bash
pip install -e ".[dev,postgres]"   # or ".[dev,mysql]" depending on your DB
cp .env.example .env                # fill in CORE_DB_URL (read-only!) and STAGING_DB_URL
```

### Phase 0 - discovery (do this before anything else)

The table/column names in `config/settings.yaml` are placeholders. Find the
real ones with the read-only introspection script:

```bash
python scripts/inspect_schema.py                  # lists all visible tables
python scripts/inspect_schema.py --table customers # lists a table's columns
```

Update `config/settings.yaml` accordingly, then:

```bash
smart-mapper validate-config
smart-mapper init-staging-db   # one-time; creates only the mapper's own tables
```

### Add a distributor

Copy `config/distributors/_template.yaml` to `config/distributors/<id>.yaml`
and fill in that distributor's real column headers/layout (get a real sample
file from them first - header row position and column names vary a lot).

### Calibrate thresholds before trusting live output

```bash
smart-mapper backtest
```

This replays your historical mapping table through the matching pipeline as
if the answers were unknown, measures actual precision/recall at a sweep of
confidence thresholds, and recommends `auto_accept_threshold` /
`review_lower_threshold` values for `config/thresholds.yaml`. Requires
`core_db.historical_mapping.columns.distributor_name_raw` /
`distributor_address_raw` to be set (i.e. the history table stores the
original distributor text, not just the code-to-code result) - if it doesn't,
this needs another data source (e.g. archived old distributor files).

Review the resulting `outputs/backtest_report.xlsx` and update
`config/thresholds.yaml` by hand - thresholds are never auto-applied.

## Running a distributor report

```bash
smart-mapper run --distributor <id> --input path/to/report.xlsx
```

Writes to `outputs/<date>_<id>/`:
- `mapped_report.xlsx` - auto-matched rows
- `review_queue.xlsx` - medium-confidence rows for a human to confirm/reject/reassign
- `new_customer_onboarding.xlsx` - likely-new customers for manual verification

After a human fills in the `decision` column in `review_queue.xlsx`:

```bash
smart-mapper ingest-review --distributor <id> --file path/to/reviewed_review_queue.xlsx
```

This updates the staging table so a confirmed match is recognized instantly
(via the exact-code fast path) on every future run for that distributor code.

## Improving accuracy over time

Arabic abbreviation/discrepancy handling lives entirely in editable config,
not code:
- `config/synonyms/name_synonyms.yaml` - e.g. "ص" / "صيدلية"
- `config/synonyms/address_synonyms.yaml` - e.g. "ش" / "شارع"
- `config/settings.yaml` (`known_cities`) - city name spelling variants

Add an entry whenever a discrepancy slips through, then re-run
`smart-mapper validate-config` to catch typos/conflicts.

## Tests

```bash
pytest tests/unit
```
