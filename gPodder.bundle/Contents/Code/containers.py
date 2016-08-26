from .plex_framework_api import ObjectContainer as PlexObjectContainer
from .shortcuts import L


class ObjectContainer(PlexObjectContainer):
    """
    A container with conveniently chainable methods
    """
    def add(self, *args, **kwargs):
        super(ObjectContainer, self).add(*args, **kwargs)
        return self


class AlertContainer(ObjectContainer):
    """
    A historyless container that flashes a message
    """
    def __init__(self, header="", message="", *args, **kwargs):
        kwargs.update(header=header, message=message, no_history=True)
        return super(AlertContainer, self).__init__(*args, **kwargs)


class ErrorContainer(AlertContainer):
    """
    A historyless container that flashes a message with an error header
    """
    def __init__(self, message="", *args, **kwargs):
        kwargs.update(header=L("Error"), message=message, no_history=True)
        return super(ErrorContainer, self).__init__(*args, **kwargs)
