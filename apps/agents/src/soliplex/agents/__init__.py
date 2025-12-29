#
__version__ = "0.1.0"


class ValidationError(Exception):
    def __init__(self, config):
        super().__init__(f"Invalid config: {config}")
