from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    eghis_process_name: str = "Eghis.exe"
    eghis_window_title_contains: str = "Eghis"
    kaosgdd_url: str = "https://kaosgdd.net"
    credential_reference_name: str = "default"
    eghis_db_connection_string: str = ""
    eghis_db_image_study_query: str = ""
    kaospacs_api_base_url: str = "http://127.0.0.1:8055"
    kaospacs_api_timeout_seconds: str = "5"
    pacs_auto_poll_enabled: str = "false"
    pacs_poll_interval_seconds: str = "60"


DEFAULT_CONFIG = AppConfig()

