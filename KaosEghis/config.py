from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    eghis_process_name: str = "Eghis.exe"
    eghis_window_title_contains: str = "Eghis"
    kaosgdd_url: str = "https://kaosgdd.net"
    credential_reference_name: str = "default"


DEFAULT_CONFIG = AppConfig()

