"""DEPRECATED: use 'soliplex.authn' instead

This module will be removed after 'soliplex v0.31'.
"""

import warnings

from soliplex.authn import *  # noqa: F403

warnings.warn(__doc__, DeprecationWarning, stacklevel=2)
