from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # Core
    secret_key: str = Field(default="change_me", alias="ORCHESTRATOR_SECRET_KEY")
    admin_user: str = Field(default="admin", alias="ORCHESTRATOR_ADMIN_USER")
    admin_password: str = Field(default="admin", alias="ORCHESTRATOR_ADMIN_PASSWORD")
    log_level: str = Field(default="INFO", alias="ORCHESTRATOR_LOG_LEVEL")

    database_url: str = Field(default="postgresql+psycopg://dp:dp@postgres/digital_printing")
    redis_url: str = Field(default="redis://redis:6379/0")
    celery_broker_url: str = Field(default="redis://redis:6379/1")
    celery_result_backend: str = Field(default="redis://redis:6379/2")

    # SOAR
    thehive_url: str = ""
    thehive_api_key: str = ""
    thehive_org: str = "digital-printing"
    cortex_url: str = ""
    cortex_api_key: str = ""
    misp_url: str = ""
    misp_api_key: str = ""
    misp_verify_ssl: bool = False

    # SpiderFoot
    spiderfoot_url: str = ""
    spiderfoot_user: str = "spiderfoot"
    spiderfoot_password: str = ""

    # AIL / LACUS
    ail_url: str = ""
    ail_api_key: str = ""
    ail_verify_ssl: bool = False
    lacus_url: str = ""

    # DRPS commerciaux
    intelx_api_key: str = ""
    intelx_base_url: str = "https://2.intelx.io"
    dehashed_email: str = ""
    dehashed_api_key: str = ""

    # Scanners (images Docker invoquees par le worker)
    scanner_pd_image: str = Field(default="digital_printing/projectdiscovery:latest", alias="SCANNER_PD_IMAGE")
    scanner_harvester_image: str = Field(default="digital_printing/theharvester:latest", alias="SCANNER_HARVESTER_IMAGE")

    # Scanner tuning
    nuclei_rate_limit: int = 150
    nuclei_templates_path: str = "/root/nuclei-templates"
    httpx_threads: int = 50
    naabu_rate: int = 1000
    katana_depth: int = 3

    # Rapports
    report_output_dir: str = "/data/reports"
    report_brand_name: str = "Digital Printing MSSP"
    report_brand_logo: str = "/app/reports/templates/logo.png"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
