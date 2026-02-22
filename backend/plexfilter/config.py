from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_path: str = "plexfilter.db"
    plex_url: str = ""
    plex_token: str = ""
    plexautoskip_json_path: str = "custom.json"
    vidangel_base_url: str = "https://api.vidangel.com/api"

    class Config:
        env_file = ".env"
        env_prefix = "PLEXFILTER_"


settings = Settings()
