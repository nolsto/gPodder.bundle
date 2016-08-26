import functools
from time import time

import app
from .plex_framework_api import Dict, PrefsObject, route
from .utils import L
from .exceptions import InvalidPrefsError
from .containers import AlertContainer


wrapper_assignments = functools.WRAPPER_ASSIGNMENTS + (
    'func_code', 'func_defaults', 'func_globals', 'func_name',
)

def app_route(path, method='GET', **kwargs):
    """
    Routes a function as a subpath of the app
    """
    return route(app.PREFIX + path, method, **kwargs)


def use_cache(attr, cache_time=0):
    """
    Run the function with `use_cache` param if the difference of now and the
    given time attribute is less than the given cache time.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            use_cache = kwargs.pop('use_cache', None)
            if use_cache is None:
                now = time()
                since = Dict[attr] or 0
                diff = now - since
                use_cache = diff < cache_time
            return func(*args, use_cache=use_cache, **kwargs)
        return wrapper
    return decorator


class client_required(object):
    """
    Ensures the is-connected state of the mygpo server
    """
    error_message = L('client error')
    client_attr = 'client'

    def __init__(self, func):
        self.func = func
        functools.update_wrapper(self, func, assigned=wrapper_assignments)

    def __call__(self, *args, **kwargs):
        if not getattr(app.session, self.client_attr):
            try:
                raise InvalidPrefsError(self.error_message)
            except InvalidPrefsError as e:
                return AlertContainer(L('Error'), e.message, objects=[
                    PrefsObject(title=L('preferences')),
                ])
        else:
            return self.func(*args, **kwargs)


class public_client_required(client_required):
    """
    Ensures the logged-in state of the mygpo user
    """
    error_message = L('public client error')
    client_attr = 'public_client'
