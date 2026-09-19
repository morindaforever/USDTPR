"""
Settings package.

Select the environment via DJANGO_SETTINGS_MODULE:
  - config.settings.dev  (default for local development)
  - config.settings.prod (added when deployment is configured)
"""

from .dev import *  # noqa: F401,F403
