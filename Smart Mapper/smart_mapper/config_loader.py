from __future__ import annotations

import hashlib
from pathlib import Path

import yaml
from pydantic import BaseModel, ValidationError


class ColumnMapping(BaseModel):
    id: str | None = None
    name: str | None = None
    address: str | None = None
    city: str | None = None
    phone: str | None = None
    distributor_id: str | None = None
    distributor_code: str | None = None
    company_customer_id: str | None = None
    distributor_name_raw: str | None = None
    distributor_address_raw: str | None = None


class TableConfig(BaseModel):
    table: str
    columns: ColumnMapping


class CoreDbConfig(BaseModel):
    customer_master: TableConfig
    historical_mapping: TableConfig


class MatchingWeights(BaseModel):
    name: float = 0.5
    address: float = 0.35
    city: float = 0.15
    phone: float = 0.3


class MatchingConfig(BaseModel):
    weights: MatchingWeights = MatchingWeights()
    candidate_limit: int = 20


class PathsConfig(BaseModel):
    output_dir: str = "outputs"
    log_dir: str = "logs"


class SettingsConfig(BaseModel):
    core_db: CoreDbConfig
    matching: MatchingConfig = MatchingConfig()
    known_cities: dict[str, list[str]] = {}
    paths: PathsConfig = PathsConfig()


class ThresholdSpec(BaseModel):
    auto_accept_threshold: float
    review_lower_threshold: float


class ThresholdsConfig(BaseModel):
    default: ThresholdSpec
    overrides: dict[str, ThresholdSpec] = {}

    def for_distributor(self, distributor_id: str) -> ThresholdSpec:
        return self.overrides.get(distributor_id, self.default)


class DistributorColumns(BaseModel):
    customer_code: str
    customer_name: str
    customer_address: str
    city: str | None = None
    phone: str | None = None


class DistributorAdapterConfig(BaseModel):
    distributor_id: str
    display_name: str
    file_type: str = "xlsx"
    sheet_name: str | None = None
    header_row_index: int = 0
    encoding: str = "utf-8"
    columns: DistributorColumns
    skip_rows_where_code_blank: bool = True
    thresholds_override: ThresholdSpec | None = None


class SynonymGroup(BaseModel):
    canonical: str
    variants: list[str]


class SynonymsFile(BaseModel):
    groups: list[SynonymGroup]

    def to_lookup(self) -> dict[str, str]:
        lookup: dict[str, str] = {}
        seen: dict[str, str] = {}
        for group in self.groups:
            for variant in group.variants + [group.canonical]:
                if variant in seen and seen[variant] != group.canonical:
                    raise ValueError(
                        f"Conflicting synonym mapping: '{variant}' maps to both "
                        f"'{seen[variant]}' and '{group.canonical}'"
                    )
                seen[variant] = group.canonical
                lookup[variant] = group.canonical
        return lookup


class StopwordsFile(BaseModel):
    stopwords: list[str] = []
    down_weight_factor: float = 0.3


def _load_yaml(path: str | Path) -> dict:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_settings(path: str | Path = "config/settings.yaml") -> SettingsConfig:
    return SettingsConfig(**_load_yaml(path))


def load_thresholds(path: str | Path = "config/thresholds.yaml") -> ThresholdsConfig:
    return ThresholdsConfig(**_load_yaml(path))


def load_distributor_config(path: str | Path) -> DistributorAdapterConfig:
    return DistributorAdapterConfig(**_load_yaml(path))


def load_synonyms(path: str | Path) -> dict[str, str]:
    return SynonymsFile(**_load_yaml(path)).to_lookup()


def load_stopwords(path: str | Path) -> StopwordsFile:
    return StopwordsFile(**_load_yaml(path))


def validate_all_configs(config_dir: str | Path = "config") -> list[str]:
    """Returns a list of human-readable errors; empty list means everything is valid."""
    config_dir = Path(config_dir)
    errors: list[str] = []

    try:
        load_settings(config_dir / "settings.yaml")
    except (FileNotFoundError, ValidationError) as e:
        errors.append(f"settings.yaml: {e}")

    try:
        load_thresholds(config_dir / "thresholds.yaml")
    except (FileNotFoundError, ValidationError) as e:
        errors.append(f"thresholds.yaml: {e}")

    for synonym_file in ("name_synonyms.yaml", "address_synonyms.yaml"):
        p = config_dir / "synonyms" / synonym_file
        try:
            load_synonyms(p)
        except (FileNotFoundError, ValidationError, ValueError) as e:
            errors.append(f"synonyms/{synonym_file}: {e}")

    try:
        load_stopwords(config_dir / "synonyms" / "stopwords_ar.yaml")
    except (FileNotFoundError, ValidationError) as e:
        errors.append(f"synonyms/stopwords_ar.yaml: {e}")

    distributors_dir = config_dir / "distributors"
    if distributors_dir.exists():
        for p in distributors_dir.glob("*.yaml"):
            if p.name.startswith("_"):
                continue
            try:
                load_distributor_config(p)
            except (FileNotFoundError, ValidationError) as e:
                errors.append(f"distributors/{p.name}: {e}")

    return errors


def config_version_hash(config_dir: str | Path = "config") -> str:
    """Hash of all config file contents, stored per-run for reproducibility."""
    config_dir = Path(config_dir)
    hasher = hashlib.sha256()
    for p in sorted(config_dir.rglob("*.yaml")):
        hasher.update(p.name.encode("utf-8"))
        hasher.update(p.read_bytes())
    return hasher.hexdigest()
