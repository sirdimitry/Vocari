"""Single source of truth for the app version (semver: MAJOR.MINOR.PATCH).

Bump PATCH for fixes, MINOR when a roadmap stage lands, MAJOR once the app is
stable post-v1.0 — see README "Версионирование". Shown in the tray tooltip and
the settings window title so it's always visible which build is running.
"""
__version__ = "0.16.0"
