"""Where an outbound email goes. In this build: always in-app (Gmail plugs in here later)."""

from typing import Literal

from covora.config import Settings
from covora.workspace.settings import WorkspaceSettings

IN_APP_ADDRESS = "in-app"


def choose_delivery(settings: Settings, ws_settings: WorkspaceSettings, *, sent_today_gmail: int) -> Literal["in_app"]:
    # A Gmail channel would be chosen here when connected and under ws_settings.sending.daily_gmail_cap.
    return "in_app"
