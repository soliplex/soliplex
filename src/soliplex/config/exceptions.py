# ============================================================================
#   Exceptions raised during YAML config processing
# ============================================================================


class FromYamlException(ValueError):
    def __init__(self, _config_path, kind: str, config_dict: dict):
        self._config_path = _config_path
        self.kind = kind
        self.config_dict = config_dict

        if config_dict is not None and "_installation_config" in config_dict:
            elide_ic = {"_installation_config": "<elided>"}
            tb_config = config_dict | elide_ic
        else:
            tb_config = config_dict

        super().__init__(
            f"Error in YAML configuration: {_config_path}; "
            f"Kind: {kind}; "
            f"Config: {tb_config}; "
        )


class NoConfigPath(ValueError):
    def __init__(self):
        super().__init__("No '_config_path' set")


class NoSuchConfig(ValueError):
    def __init__(self, _config_path):
        self._config_path = _config_path
        super().__init__(f"Config path is not a YAML file: {_config_path}")


class NotADict(ValueError):
    def __init__(self, found):
        self.found = found
        super().__init__(f"YAML did not parse as a dict: {found}")
