from .plex_framework_api import Log


class ChannelError(Exception):
    logger = Log.Error

    def __init__(self, message):
        self.message = message
        self.logger(message)


class InvalidPrefsError(ChannelError):
    logger = Log.Warn
