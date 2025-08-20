"""
Centralized Sentry ASCII art banner for all utilities.
"""


def get_sentry_banner() -> str:
    """Get the Sentry ASCII art banner."""
    return r"""╔────────────────────────────────────────────╗
│  _________              __                 │
│ /   _____/ ____   _____/  |________ ___.__.│
│ \_____  \_/ __ \ /    \   __\_  __ <   |  |│
│ /        \  ___/|   |  \  |  |  | \/\___  |│
│/_______  /\___  >___|  /__|  |__|   / ____|│
│        \/     \/     \/             \/     │
╚────────────────────────────────────────────╝"""


def show_sentry_banner():
    """Display the Sentry ASCII art banner."""
    print(get_sentry_banner())
    print()
