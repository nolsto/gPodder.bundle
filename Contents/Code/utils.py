from mygpoclient.simple import Podcast

from .plex_framework_api import AudioCodec, Container, Data, Dict, JSON


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
    return {i: getattr(obj, i) for i in Podcast.REQUIRED_FIELDS}


M4A_EXTENSIONS = ( 'm4a', 'm4b', 'm4p', 'm4v', 'm4r', '3gp', 'mp4', 'aac' )

def get_mime_type_from_ext(ext):
    if ext in M4A_EXTENSIONS:
        return 'audio/x-m4a'
    return 'audio/mpeg'


AAC_MIME_TYPES = ('audio/aac', 'audio/aacp', 'audio/3gpp', 'audio/3gpp2',
                  'audio/mp4', 'audio/MP4A-LATM', 'audio/mpeg4-generic',
                  'audio/aac', 'audio/x-m4a')

def get_audio_codec_from_mime_type(mime_type):
    if mime_type in AAC_MIME_TYPES:
        return AudioCodec.AAC
    else:
        return AudioCodec.MP3


def get_container_from_audio_codec(audio_codec):
    return Container.MP4 if audio_codec == AudioCodec.AAC else 'mp3'
