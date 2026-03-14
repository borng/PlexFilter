from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_path: str = "plexfilter.db"
    plex_url: str = ""
    plex_token: str = ""
    plexautoskip_json_path: str = "custom.json"
    vidangel_base_url: str = "https://api.vidangel.com/api"
    local_detection_enabled: bool = True
    local_detection_sample_interval_sec: float = 1.0
    local_detection_merge_gap_sec: float = 1.5
    local_detection_nudenet_threshold: float = 0.40
    local_detection_stage1_model: str = "freepik"
    local_detection_stage1_severity: str = "medium"
    local_detection_stage1_min_vram_gb: float = 3.5
    local_detection_stage1_require_bf16: bool = False

    class Config:
        env_file = ".env"
        env_prefix = "PLEXFILTER_"


settings = Settings()
