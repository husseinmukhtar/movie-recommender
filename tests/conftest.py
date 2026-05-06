"""Shared pytest configuration for warning policy exceptions."""
import sys
import warnings

import python_multipart

warnings.filterwarnings(
    "ignore",
    message=r"Please use `import python_multipart` instead\.",
    category=PendingDeprecationWarning,
)

# Starlette imports `multipart`; map it to the non-deprecated module path.
sys.modules.setdefault("multipart", python_multipart)
