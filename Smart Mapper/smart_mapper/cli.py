from __future__ import annotations

from pathlib import Path

import click
from dotenv import load_dotenv

from smart_mapper.calibration.backtest import BacktestRow, recommend_thresholds, run_backtest, write_backtest_report
from smart_mapper.config_loader import load_settings, load_synonyms, validate_all_configs
from smart_mapper.db.core_models import fetch_customer_master, fetch_historical_mappings
from smart_mapper.db.engine import get_core_engine, get_session_factory, get_staging_engine
from smart_mapper.db.staging_models import create_staging_tables
from smart_mapper.feedback.ingest_review_decisions import ingest_review_file
from smart_mapper.logging_conf import configure_logging
from smart_mapper.matching.candidate_generation import MasterCustomer
from smart_mapper.normalization.address_parser import build_city_lookup
from smart_mapper.normalization.pipeline import process_record
from smart_mapper.normalization.synonyms import build_normalized_lookup
from smart_mapper.pipeline_runner import run_distributor


@click.group()
def cli():
    """Smart Mapper - maps distributor customer records to the company customer master."""


@cli.command()
@click.option("--distributor", required=True, help="Distributor id (matches config/distributors/<id>.yaml)")
@click.option("--input", "input_file", required=True, type=click.Path(exists=True), help="Path to the distributor's report file")
@click.option("--config-dir", default="config", show_default=True)
def run(distributor: str, input_file: str, config_dir: str):
    """Process one distributor report and write mapped/review/onboarding outputs."""
    settings = load_settings(Path(config_dir) / "settings.yaml")
    configure_logging(settings.paths.log_dir)

    result = run_distributor(distributor, input_file, config_dir)
    click.echo(f"Done. Counts: {result['counts']}")
    click.echo(f"Outputs written to: {result['output_dir']}")


@cli.command("ingest-review")
@click.option("--distributor", required=True)
@click.option("--file", "file_path", required=True, type=click.Path(exists=True))
def ingest_review(distributor: str, file_path: str):
    """Re-import a completed review_queue.xlsx (or new_customer_onboarding.xlsx
    handled manually) and apply CONFIRM/REJECT/REASSIGN decisions to staging."""
    load_dotenv()
    staging_engine = get_staging_engine()
    session_factory = get_session_factory(staging_engine)
    with session_factory() as session:
        counts = ingest_review_file(session, file_path, distributor)
    click.echo(f"Ingested review decisions: {counts}")


@cli.command("validate-config")
@click.option("--config-dir", default="config", show_default=True)
def validate_config_cmd(config_dir: str):
    """Check all YAML config files for syntax/schema errors and synonym conflicts."""
    errors = validate_all_configs(config_dir)
    if errors:
        click.echo("Config validation FAILED:")
        for e in errors:
            click.echo(f"  - {e}")
        raise SystemExit(1)
    click.echo("All config files valid.")


@cli.command("init-staging-db")
@click.confirmation_option(
    prompt=(
        "This creates the mapper's own staging tables (run_audit_log, "
        "distributor_customer_mapping, review_decisions) via STAGING_DB_URL. "
        "It never touches any core/existing table. Continue?"
    )
)
def init_staging_db():
    """One-time setup: create the mapper's staging tables. Run deliberately, once."""
    load_dotenv()
    engine = get_staging_engine()
    create_staging_tables(engine)
    click.echo("Staging tables created (or already existed).")


@cli.command()
@click.option("--config-dir", default="config", show_default=True)
@click.option("--target-precision", default=0.99, show_default=True, type=float)
def backtest(config_dir: str, target_precision: float):
    """Measure real precision/recall of the matching methodology against the
    historical mapping table, and recommend accept/review thresholds.
    Run this BEFORE trusting any live output - see config/thresholds.yaml."""
    load_dotenv()
    config_dir_path = Path(config_dir)
    settings = load_settings(config_dir_path / "settings.yaml")
    configure_logging(settings.paths.log_dir)

    hist_cols = settings.core_db.historical_mapping.columns
    if not hist_cols.distributor_name_raw or not hist_cols.distributor_address_raw:
        click.echo(
            "core_db.historical_mapping.columns.distributor_name_raw / "
            "distributor_address_raw are not set in settings.yaml. The backtest "
            "needs the ORIGINAL distributor name/address text from past "
            "reconciliations to measure fuzzy-matching accuracy - configure "
            "them (Phase 0 discovery) and re-run."
        )
        raise SystemExit(1)

    name_lookup = build_normalized_lookup(load_synonyms(config_dir_path / "synonyms" / "name_synonyms.yaml"))
    address_lookup = build_normalized_lookup(load_synonyms(config_dir_path / "synonyms" / "address_synonyms.yaml"))
    city_lookup = build_city_lookup(settings.known_cities)

    core_engine = get_core_engine()
    master_rows = fetch_customer_master(core_engine, settings)
    historical_rows = fetch_historical_mappings(core_engine, settings)

    customers = [
        MasterCustomer(
            customer_id=str(r["customer_id"]),
            processed=process_record(
                r.get("name"), r.get("address"), name_lookup, address_lookup, city_lookup, r.get("phone")
            ),
        )
        for r in master_rows
    ]

    backtest_rows = [
        BacktestRow(
            distributor_id=r["distributor_id"],
            distributor_code=r["distributor_code"],
            name_raw=r["distributor_name_raw"],
            address_raw=r["distributor_address_raw"],
            true_company_customer_id=r["company_customer_id"],
        )
        for r in historical_rows
        if r.get("distributor_name_raw") and r.get("company_customer_id")
    ]

    if not backtest_rows:
        click.echo("No historical rows with both raw text and a known match were found - cannot backtest.")
        raise SystemExit(1)

    metrics = run_backtest(
        backtest_rows, customers, settings.matching.weights, name_lookup, address_lookup, city_lookup,
        settings.matching.candidate_limit,
    )
    auto_accept, review_lower = recommend_thresholds(metrics, target_precision)

    report_path = Path(settings.paths.output_dir) / "backtest_report.xlsx"
    write_backtest_report(metrics, report_path)

    click.echo(f"Backtest complete on {len(backtest_rows)} historical row(s).")
    click.echo(f"Recommended auto_accept_threshold: {auto_accept}")
    click.echo(f"Recommended review_lower_threshold: {review_lower}")
    click.echo(f"Full precision/recall report written to {report_path}")
    click.echo("Review this report and update config/thresholds.yaml manually before go-live.")


if __name__ == "__main__":
    cli()
