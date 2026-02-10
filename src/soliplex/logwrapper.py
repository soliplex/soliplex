import logging


class LogWrapper:
    """Context wrapper for capturing extra logging values"""

    def __init__(self, logger_name, **extra):
        self.logger = logging.getLogger(logger_name)
        self.extra = extra

    def log(self, level, message, *args):
        self.logger.log(level, message, *args, extra=self.extra)

    def critical(self, message, *args):
        self.logger.critical(message, *args, extra=self.extra)

    def exception(self, message, *args):
        self.logger.exception(message, *args, extra=self.extra)

    def error(self, message, *args):
        self.logger.error(message, *args, extra=self.extra)

    def warning(self, message, *args):
        self.logger.warning(message, *args, extra=self.extra)

    def info(self, message, *args):
        self.logger.info(message, *args, extra=self.extra)

    def debug(self, message, *args):
        self.logger.debug(message, *args, extra=self.extra)
