"""Test settings.

pytest-django imports the settings module before any conftest runs, so the
throwaway SECRET_KEY is set here, before base is imported. Production settings
keep their no-fallback contract untouched.
"""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-insecure-key-not-for-production")

from .base import *
