"""Modal deploy entry point.

Usage: modal deploy src/policyengine_api/modal/deploy.py

This file imports the app and all functions so Modal discovers them.
The import order matters: app must be defined before functions
register their @app.function decorators.
"""

# Import functions module to register all @app.function decorators
import policyengine_api.modal.functions  # noqa: F401, E402
from policyengine_api.modal.app import app  # noqa: F401
