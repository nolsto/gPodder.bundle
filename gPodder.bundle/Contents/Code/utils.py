from .plex_framework_api import Data, Dict, JSON, Locale

L = Locale.LocalString
LF = Locale.LocalStringWithFormat

def clear_cache(data_attrs=None, dict_items=None):
    if data_attrs is None:
        data_attrs = ()
    if dict_items is None:
        dict_items = ()
    for attr in data_attrs:
        Data.Remove(attr)
    for item in dict_items:
        if item in Dict:
            del Dict[item]
    Dict.Save()

def encode(o):
    return JSON.StringFromObject(o)

def decode(s):
    return JSON.ObjectFromString(s)

def podcast_to_dict(obj):
    return {i: getattr(obj, i) for i in ['url', 'title', 'description', 'logo_url']}
