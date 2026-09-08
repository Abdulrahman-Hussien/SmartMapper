from __future__ import annotations

import hashlib
import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

from smart_mapper.config_loader import (
    config_version_hash,
    load_distributor_config,
    load_settings,
    load_synonyms,
    load_thresholds,
)
from smart_mapper.db.core_models import fetch_customer_master, fetch_historical_mappings
from smart_mapper.db.engine import get_core_engine, get_session_factory, get_staging_engine
from smart_mapper.db.repository import fetch_all_mappings, finish_run, start_run, upsert_mapping
from smart_mapper.export.new_customer_queue import build_new_customer_queue
from smart_mapper.export.review_queue import build_review_queue
from smart_mapper.export.run_report import build_run_summary
from smart_mapper.ingestion.adapters import load_distributor_rows
from smart_mapper.matching.candidate_generation import CandidateIndex, MasterCustomer
from smart_mapper.matching.decision import MatchStatus, decide
from smart_mapper.matching.exact_lookup import build_history_index, lookup_exact
from smart_mapper.matching.scoring import score_candidates
from smart_mapper.normalization.address_parser import build_city_lookup
from smart_mapper.normalization.pipeline import process_record
from smart_mapper.normalization.synonyms import build_normalized_lookup


def _file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _build_master_index(settings, name_lookup, address_lookup, city_lookup) -> tuple[CandidateIndex, list[dict]]:
    core_engine = get_core_engine()
    master_rows = fetch_customer_master(core_engine, settings)
    historical_rows = fetch_historical_mappings(core_engine, settings)

    customers = [
        MasterCustomer(
            customer_id=str(row["customer_id"]),
            processed=process_record(
                row.get("name"), row.get("address"), name_lookup, address_lookup, city_lookup, row.get("phone")
            ),
        )
        for row in master_rows
    ]
    return CandidateIndex(customers), historical_rows


def run_distributor(distributor_id: str, input_file: str, config_dir: str = "config") -> dict:
    load_dotenv()
    config_dir_path = Path(config_dir)

    settings = load_settings(config_dir_path / "settings.yaml")
    thresholds_cfg = load_thresholds(config_dir_path / "thresholds.yaml")
    distributor_cfg = load_distributor_config(config_dir_path / "distributors" / f"{distributor_id}.yaml")

    name_lookup = build_normalized_lookup(load_synonyms(config_dir_path / "synonyms" / "name_synonyms.yaml"))
    address_lookup = build_normalized_lookup(load_synonyms(config_dir_path / "synonyms" / "address_synonyms.yaml"))
    city_lookup = build_city_lookup(settings.known_cities)

    thresholds = distributor_cfg.thresholds_override or thresholds_cfg.for_distributor(distributor_id)
    cfg_hash = config_version_hash(config_dir_path)

    logger.info(f"Fetching customer master and historical mappings for distributor '{distributor_id}'")
    candidate_index, historical_rows = _build_master_index(settings, name_lookup, address_lookup, city_lookup)

    staging_engine = get_staging_engine()
    StagingSession = get_session_factory(staging_engine)

    mapped_report_rows: list[dict] = []
    review_rows: list[dict] = []
    new_customer_rows: list[dict] = []
    counts = {"total": 0, "auto_matched": 0, "pending_review": 0, "candidate_new": 0}

    with StagingSession() as session:
        staging_mappings = fetch_all_mappings(session)
        # historical table first, staging table second: a confirmed/updated
        # staging entry takes precedence over the raw historical snapshot.
        history_index = build_history_index(historical_rows + staging_mappings)

        input_hash = _file_sha256(input_file)
        run = start_run(
            session,
            distributor_id=distributor_id,
            input_file_name=os.path.basename(input_file),
            input_file_hash=input_hash,
            config_version_hash=cfg_hash,
        )

        rows = load_distributor_rows(distributor_cfg, input_file)
        logger.info(f"Loaded {len(rows)} row(s) from {input_file}")
        counts["total"] = len(rows)

        for row in rows:
            exact_match = lookup_exact(distributor_id, row.code, history_index)

            if exact_match:
                status = MatchStatus.AUTO_MATCHED
                matched_id: str | None = exact_match
                confidence: float | None = 1.0
                method = "EXACT_CODE_HISTORY"
                alternatives_out: list[dict] = []
            else:
                record = process_record(row.name, row.address, name_lookup, address_lookup, city_lookup, row.phone)
                candidates = candidate_index.candidates_for(record, settings.matching.candidate_limit)
                scored = score_candidates(record, candidates, settings.matching.weights)
                decision = decide(scored, thresholds)

                status = decision.status
                matched_id = decision.matched_customer_id
                confidence = decision.confidence
                method = "FUZZY_AUTO" if status == MatchStatus.AUTO_MATCHED else "FUZZY_CANDIDATE"
                alternatives_out = [
                    {"customer_id": a.customer_id, "score": round(a.composite, 4)} for a in decision.alternatives
                ]

            upsert_mapping(
                session,
                distributor_id=distributor_id,
                distributor_customer_code=row.code,
                distributor_customer_name_raw=row.name,
                distributor_customer_address_raw=row.address,
                company_customer_id=matched_id,
                confidence_score=confidence,
                match_method=method,
                status=status.value,
                candidate_alternatives=alternatives_out,
                run_id=run.id,
            )

            if status == MatchStatus.AUTO_MATCHED:
                counts["auto_matched"] += 1
                mapped_report_rows.append(
                    {
                        "distributor_code": row.code,
                        "distributor_name": row.name,
                        "distributor_address": row.address,
                        "company_customer_id": matched_id,
                        "confidence": confidence,
                        "match_method": method,
                    }
                )
            elif status == MatchStatus.PENDING_REVIEW:
                counts["pending_review"] += 1
                review_rows.append(
                    {
                        "distributor_code": row.code,
                        "distributor_name_raw": row.name,
                        "distributor_address_raw": row.address,
                        "candidate_customer_id": matched_id,
                        "confidence": confidence,
                        "alternatives": alternatives_out,
                    }
                )
            else:
                counts["candidate_new"] += 1
                new_customer_rows.append(
                    {
                        "distributor_code": row.code,
                        "distributor_name_raw": row.name,
                        "distributor_address_raw": row.address,
                        "best_partial_match_score": confidence,
                        "best_partial_match_alternatives": alternatives_out,
                    }
                )

        finish_run(session, run, counts, status="SUCCESS")
        session.commit()

    output_dir = Path(settings.paths.output_dir) / f"{date.today().isoformat()}_{distributor_id}"
    build_run_summary(mapped_report_rows, counts, output_dir / "mapped_report.xlsx")
    if review_rows:
        build_review_queue(review_rows, output_dir / "review_queue.xlsx")
    if new_customer_rows:
        build_new_customer_queue(new_customer_rows, output_dir / "new_customer_onboarding.xlsx")

    logger.info(f"Run complete for '{distributor_id}': {counts}")
    return {"counts": counts, "output_dir": str(output_dir)}
