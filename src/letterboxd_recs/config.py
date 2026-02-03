from dataclasses import dataclass
from pathlib import Path
import tomllib


@dataclass(frozen=True)
class AppConfig:
    region: str
    database_path: str
    cache_dir: str
    user_agent: str


@dataclass(frozen=True)
class ScrapeConfig:
    rate_limit_seconds: float
    max_retries: int
    cache_ttl_days: int
    use_browser: bool
    max_pages: int = 100


@dataclass(frozen=True)
class GraphConfig:
    max_depth: int
    decay: float


@dataclass(frozen=True)
class WeightsConfig:
    liked: float
    rated: float
    watched: float
    watchlist: float


@dataclass(frozen=True)
class BlendConfig:
    alpha_content: float
    beta_social: float
    gamma_novelty: float
    delta_diversity: float


@dataclass(frozen=True)
class SocialConfig:
    watched_weight: float
    watchlist_weight: float
    time_weight_min: float
    time_weight_years: int


@dataclass(frozen=True)
class SocialRatingsConfig:
    negative_min: float
    negative_max: float
    positive_min: float
    positive_max: float
    unrated: float
    watchlist_multiplier: float


@dataclass(frozen=True)
class SocialSimilarityConfig:
    jaccard_weight: float
    rating_weight: float
    rating_prior: float
    rating_k: float
    default_similarity: float
    stretch_power: float
    normalize_top: bool


@dataclass(frozen=True)
class SocialNormalizeConfig:
    enabled: bool
    followee_weight: float
    similarity_weight: float
    interaction_weight: float
    time_weight: float


@dataclass(frozen=True)
class Config:
    app: AppConfig
    scrape: ScrapeConfig
    graph: GraphConfig
    weights: WeightsConfig
    blend: BlendConfig
    social: SocialConfig
    social_ratings: SocialRatingsConfig
    social_similarity: SocialSimilarityConfig
    social_normalize: SocialNormalizeConfig

    @property
    def database_path(self) -> str:
        return self.app.database_path


DEFAULT_CONFIG_PATH = Path("config.toml")


def load_config(path: Path | None = None) -> Config:
    config_path = path or DEFAULT_CONFIG_PATH
    if not config_path.exists():
        raise FileNotFoundError(
            "Missing config.toml. Copy config.example.toml to config.toml and edit it."
        )

    raw = tomllib.loads(config_path.read_text(encoding="utf-8"))

    app = raw["app"]
    scrape = raw["scrape"]
    graph = raw["graph"]
    weights = raw["weights"]
    blend = raw["blend"]
    social = raw["social"]
    social_ratings = raw["social_ratings"]
    social_similarity = raw["social_similarity"]
    social_normalize = raw["social_normalize"]

    return Config(
        app=AppConfig(**app),
        scrape=ScrapeConfig(**scrape),
        graph=GraphConfig(**graph),
        weights=WeightsConfig(**weights),
        blend=BlendConfig(**blend),
        social=SocialConfig(**social),
        social_ratings=SocialRatingsConfig(**social_ratings),
        social_similarity=SocialSimilarityConfig(**social_similarity),
        social_normalize=SocialNormalizeConfig(**social_normalize),
    )
