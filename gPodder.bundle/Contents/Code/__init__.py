import cerealizer
import re
from functools import wraps
from operator import itemgetter
from time import time
from urllib2 import HTTPError, URLError, urlopen

import podcastparser
from mygpoclient.simple import Podcast
from session import Session, InvalidClientError


cerealizer.register(Podcast)

PREFIX = '/music/gpodder'
NAME = 'gPodder'
ICON = 'icon-default.png'
DEVICE_ID = 'plex-gpodder-plugin.%s' % Network.Hostname

TOPLIST_CACHE_TIME = 86400 # one day
SUBSCRIPTIONS_CACHE_TIME = 604800 # one week
SUBSCRIPTIONS_UPDATE_TIME = 60 # one minute

EXCLUDE_REGEX = re.compile(r'[^\w\d]|the\s')
AUDIO_URL_REGEX = re.compile(r'(https?\:\/\/(?:[^/\s]+)?(?:(?:\/[^\s]*)*\/)?(?:[^\s]*?\.(?P<ext>m4[abpvr]|3gp|mp4|aac|mp3)))')

L = Locale.LocalString
LF = Locale.LocalStringWithFormat

session = None


#==============================================================================
# Decorators
#==============================================================================

def public_client_required(func):
    """
    Wrapper to check the connection state of the mygpo server
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        global session

        if not session.public_client:
            return ErrorInvalidPrefs(L('public client error'))
        else:
            return func(*args, **kwargs)
    return wrapper


def client_required(func):
    """
    Wrapper to check the login state of the mygpo user
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        global session

        if not session.client:
            return ErrorInvalidPrefs(L('client error'))
        else:
            return func(*args, **kwargs)
    return wrapper


# def baked(temperature=None, duration=None):
#     def decorator(method):
#         @functools.wraps(method)
#         def f(*args, **kwargs):
#             thing_to_be_baked = method(*args, **kwargs)
#             return bake(thing_to_be_baked, temperature, duration)
#         return f
#     return decorator
def use_cache(since_attr, cache_time=0):
    """
    Wrapper
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            now = int(time())
            since = Dict[since_attr] or 0
            diff = now - since
            use_cache =  diff < cache_time

            return func(use_cache=use_cache, *args, **kwargs)
        return wrapper
    return decorator

# @use_cache('subscriptions_accessed', SUBSCRIPTIONS_CACHE_TIME)
# def get_subscriptions(use_cache=False):

# since = Dict['toplist_accessed'] or 0
# now = int(time())

# if not use_cache(since, now) or not Data.Exists('toplist'):
#     Log('Using requested toplist')

#     try:
#         toplist = session.public_client.get_toplist()
#     except Exception:
#         return Error(L('toplist error'))
#     else:
#         Data.SaveObject('toplist', toplist)
#         Dict['toplist_accessed'] = now


#==============================================================================
# Helper Functions
#==============================================================================

# def use_cache(since, now=None):
#     if not now:
#         now = int(time())
#     diff = now - since
#     return diff < 86400


def remove_public_client_cache():
    Data.Remove('toplist')
    if 'toplist_accessed' in Dict:
        del Dict['toplist_accessed']
    Dict.Save()
    Log('public client cache cleared')


def remove_client_cache():
    Data.Remove('subscriptions')
    if 'subscriptions_accessed' in Dict:
        del Dict['subscriptions_accessed']
    Dict.Save()
    Log('client cache cleared')


@use_cache('subscriptions_accessed', SUBSCRIPTIONS_UPDATE_TIME)
def get_subscriptions(use_cache=False):
    since = Dict['subscriptions_accessed'] or 0
    try:
        changes = session.client.pull_subscriptions(DEVICE_ID, since)
    except Exception:
        return Error(L('subscriptions error'))
    Dict['subscriptions_accessed'] = changes.since

    Log('Added:   %s' % changes.add)
    Log('Removed: %s' % changes.remove)

    podcasts = []
    if Data.Exists('subscriptions'):
        podcasts = Data.LoadObject('subscriptions')
        # remove urls returned from subscriptions changes
        podcasts = [i for i in podcasts if i.url not in changes.remove]
    # add urls returned from subscriptions changes
    podcasts += [session.public_client.get_podcast_data(url) for url in changes.add]
    # sort podcasts on title
    podcasts = sorted(podcasts, key=lambda n: EXCLUDE_REGEX.sub('', str(n.title).lower()))
    Data.SaveObject('subscriptions', podcasts)
    return podcasts


def get_toplist(use_cache=False):
    pass

def create_media_objects(episode):
    enclosures = episode['enclosures']

    # look for audio files in episode description if no enclosures are found
    if not len(enclosures) and episode.get('description'):
        matches = AUDIO_URL_REGEX.findall(episode.get('description'))
        enclosures = [{'url': i[0], 'mime_type': determine_mime_type(i[1])} for i in matches]

    # filter enclosures on duplicate urls
    enclosures = {i['url']:i for i in enclosures}.values()

    duration = episode['total_time'] * 1000

    objects = []
    for item in enclosures:
        objects.append(
            MediaObject(
                audio_codec=determine_audio_codec(item['mime_type']),
                duration=duration,
                parts=[PartObject(key=item['url'], duration=duration)]
            )
        )
    return objects


def determine_mime_type(ext):
    if ext in ['m4a', 'm4b', 'm4p', 'm4v', 'm4r', '3gp', 'mp4', 'aac']:
        return 'audio/x-m4a'
    return 'audio/mpeg'


def determine_audio_codec(mime_type):
    if mime_type in ['audio/aac', 'audio/aacp', 'audio/3gpp', 'audio/3gpp2',
                     'audio/mp4', 'audio/MP4A-LATM', 'audio/mpeg4-generic',
                     'audio/aac', 'audio/x-m4a']:
        return AudioCodec.AAC
    return AudioCodec.MP3


def podcast_to_dict(obj):
    return {i: getattr(obj, i) for i in ['url', 'title', 'description', 'logo_url']}


def encode(d):
    return JSON.StringFromObject(d)


def decode(s):
    return JSON.ObjectFromString(s)


#==============================================================================
# Plex Built-in & Error/Alert Functions
#==============================================================================

def Alert(header, message):
    return ObjectContainer(
        header=header,
        message=message,
        no_history=True
    )

def Error(message):
    Log.Error(message)
    return Alert(L('Error'), message)


def ErrorInvalidPrefs(message):
    """
    mygpo API error with current preferences
    """

    container = Error(message)
    container.add(PrefsObject(title=L('preferences')))
    return container


def ValidatePrefs():
    global session

    # ensure at least server field is filled out
    if not (Prefs['server']):
        return ErrorInvalidPrefs(L('prefs error'))

    # update session properties
    session.server = Prefs['server']
    session.device_name = Prefs['device_name']
    session.username = Prefs['username']
    session.password = Prefs['password']

    # clear cached public client data if the webservice has successfully changed
    if session.dirty_public_client:
        try:
            session.create_public_client()
        except InvalidClientError:
            return ErrorInvalidPrefs(L('public client error'))
        finally:
            remove_public_client_cache()

    # clear cached client data if username/password has successfully changed
    if session.dirty_client:
        try:
            session.create_client()
        except InvalidClientError:
            return ErrorInvalidPrefs(L('client error'))
        finally:
            remove_client_cache()

    if session.dirty_device_name:
        session.update_device()


def Start():
    global session

    # container defaults
    ObjectContainer.title1 = NAME
    DirectoryObject.thumb = R(ICON)

    session = Session(DEVICE_ID)
    ValidatePrefs()


#==============================================================================
# Containers
#==============================================================================

@handler(PREFIX, NAME, thumb=ICON)
def MainMenu():
    container = ObjectContainer()
    container.add(DirectoryObject(
        key=Callback(Recent),
        title=L('recent'),
        summary=L('recent summary'),
        thumb=R('icon-recent.png')
    ))
    container.add(DirectoryObject(
        key=Callback(Subscriptions),
        title=L('subscriptions'),
        summary=L('subscriptions summary'),
        thumb=R('icon-subscriptions.png')
    ))
    container.add(DirectoryObject(
        key=Callback(Recommendations),
        title=L('recommendations'),
        summary=L('recommendations summary')
    ))
    container.add(DirectoryObject(
        key=Callback(Toplist),
        title=L('toplist'),
        summary=L('toplist summary'),
        thumb=R('icon-popular.png')
    ))
    container.add(InputDirectoryObject(
        key=Callback(Search),
        title=L('search'),
        prompt=L('search prompt'),
        summary=L('search summary'),
        thumb=R('icon-search.png')
    ))
    container.add(InputDirectoryObject(
        key=Callback(Subscribe),
        title=L('subscribe'),
        prompt=L('subscribe prompt'),
        summary=L('subscribe summary'),
        thumb=R('icon-add.png')
    ))
    container.add(PrefsObject(
        title=L('preferences'),
        summary=L('preferences summary')
    ))
    return container


@route(PREFIX + '/search/{query}')
@public_client_required
def Search(query):
    """
    Search
    """

    try:
        search_results = session.public_client.search_podcasts(query)
    except URLError, e:
        return Error(L('search error'))

    container = ObjectContainer(title2=L('search results'))
    for item in search_results:
        entry = podcast_to_dict(item)
        container.add(TVShowObject(
            key=Callback(Podcast, entry_data=encode(entry)),
            rating_key=entry['url'],
            summary=entry['description'],
            thumb=Resource.ContentsOfURLWithFallback(url=entry['logo_url'], fallback=ICON),
            title=entry['title'],
        ))
    return container


@route(PREFIX + '/subscribe/{query}')
@client_required
def Subscribe(query):
    """
    Subscribe
    """

    url = query
    podcasts = get_subscriptions()

    # if the user is already subscribed to the feed, alert and return
    if url in [i.url for i in podcasts]:
        return Alert(L('subscribe'), LF('already subscribed', url))

    try:
        podcast = session.public_client.get_podcast_data(url)
    except Exception:
        return Error(L('url error'))
    return SubscribeTo(podcast)


@route(PREFIX + '/toplist/{page}', page=int)
@use_cache('toplist_accessed', TOPLIST_CACHE_TIME)
@public_client_required
def Toplist(page=0, container=None, use_cache=False):
    """
    Top List

    List 50 most-popular podcasts and allow user to subscribe to each.
    """

    since = Dict['toplist_accessed'] or 0
    now = int(time())

    if not use_cache(since, now) or not Data.Exists('toplist'):
        Log('Using requested toplist')

        try:
            toplist = session.public_client.get_toplist()
        except Exception:
            return Error(L('toplist error'))
        else:
            Data.SaveObject('toplist', toplist)
            Dict['toplist_accessed'] = now
    else:
        Log('Using cached toplist')

        toplist = Data.LoadObject('toplist')

    if not container:
        container = ObjectContainer()
    container.title2 = L('toplist')

    for index, item in enumerate(toplist):
        entry = podcast_to_dict(item)
        container.add(DirectoryObject(
            key=Callback(Podcast, entry_data=encode(entry)),
            summary=entry['description'],
            thumb=Resource.ContentsOfURLWithFallback(url=entry['logo_url'], fallback=ICON),
            title=entry['title'],
        ))
    return container


@route(PREFIX + '/podcast', entry_data=dict)
@public_client_required
def Podcast(entry_data, container=None):
    """
    Podcast
    """

    # if the user is not logged in, just show the episodes
    if not session.client:
        return Episodes(entry_data, container)

    entry = decode(entry_data)

    if not container:
        container = ObjectContainer()
    container.title2 = entry['title']
    container.no_cache = True
    container.add(DirectoryObject(
        key=Callback(Episodes, podcast_data=entry_data),
        thumb=Resource.ContentsOfURLWithFallback(url=entry['logo_url'], fallback=ICON),
        summary=entry['description'],
        title=LF('episodes', entry['title'])
    ))

    # Check to see if podcast is in user's subscriptions and present
    # subscribe/unsubscribe objects accordingly
    podcasts = get_subscriptions()
    if entry['url'] in [i.url for i in podcasts]:
        obj = DirectoryObject(
            key=Callback(UnsubscribeFrom, podcast=entry),
            title=L('Unsubscribe'),
            summary=L('unsubscribe from summary'),
            thumb=R('icon-remove.png')
        )
    else:
        obj = DirectoryObject(
            key=Callback(SubscribeTo, podcast=entry),
            title=L('Subscribe'),
            summary=L('subscribe to summary'),
            thumb=R('icon-add.png')
        )
    container.add(obj)
    return container


@route(PREFIX + '/episodes', podcast_data=dict, allow_sync=True)
def Episodes(podcast_data, container=None):
    """
    Episodes
    """

    podcast = decode(podcast_data)

    try:
        response = podcastparser.parse(podcast['url'], urlopen(podcast['url']))
    except HTTPError:
        return Error(L('url error'))
    episodes = response['episodes']

    if not len(episodes):
        return Alert(L('Episodes'), L('no subscriptions'))

    if not container:
        container = ObjectContainer()
    container.title2 = podcast['title']

    for entry in episodes:
        entry['logo_url'] = podcast['logo_url']
        container.add(Episode(encode(entry)))
    return container


@route(PREFIX + '/episode', entry_data=dict)
def Episode(entry_data, include_container=False):
    """
    Episode
    """

    entry = decode(entry_data)

    summary = podcastparser.remove_html_tags(entry.get('description'))
    if not summary:
        summary = entry.get('subtitle', L('No Summary'))

    obj = TrackObject(
        key=Callback(Episode, entry_data=entry_data, include_container=True),
        rating_key=entry['guid'],
        title=entry.get('title', L('No Title')),
        thumb=Resource.ContentsOfURLWithFallback(url=entry['logo_url'], fallback=ICON),
        summary=summary,
        duration=entry['total_time'] * 1000,
        items=create_media_objects(entry)
    )

    if include_container:
        return ObjectContainer(objects=[obj])
    else:
        return obj


@route(PREFIX + '/recent')
@client_required
def Recent(container=None):
    """
    Recently Aired

    List the most-recently aired episodes in user's subscriptions.
    """

    if not container:
        container = ObjectContainer()
    container.title2 = L('Recently Aired')
    return container


@route(PREFIX + '/subscriptions')
@client_required
def Subscriptions(container=None):
    """
    Subscriptions

    List all podcasts user is currently subscribed to.
    Allow user to select a podcast and see its episodes or unsubscribe from it.
    """

    podcasts = get_subscriptions()
    if not len(podcasts):
        return Alert(L('subscriptions'), L('no subscriptions'))

    if not container:
        container = ObjectContainer(no_cache=True)
    container.title2 = L('subscriptions')

    for item in podcasts:
        entry = podcast_to_dict(item)
        container.add(DirectoryObject(
            key=Callback(Podcast, entry_data=encode(entry)),
            summary=entry['description'],
            thumb=Resource.ContentsOfURLWithFallback(url=entry['logo_url'], fallback=ICON),
            title=entry['title'],
        ))
    return container


@route(PREFIX + '/recommendations/{page}', page=int)
@client_required
def Recommendations(page=0, container=None):
    """
    Recommended podcasts
    """

    recommendations = session.client.get_suggestions()

    if not len(recommendations):
        return Alert(L('recommendations'), L('no recommendations'))

    if not container:
        container = ObjectContainer()
    container.title2 = L('recommendations')

    for index, item in enumerate(recommendations):
        entry = podcast_to_dict(item)
        container.add(DirectoryObject(
            key=Callback(Podcast, entry_data=encode(entry)),
            summary=entry['description'],
            thumb=Resource.ContentsOfURLWithFallback(url=entry['logo_url'], fallback=ICON),
            title=entry['title'],
        ))
    return container


@client_required
def SubscribeTo(podcast):
    try:
        session.client.update_subscriptions(DEVICE_ID, add_urls=[podcast['url']])
    except Exception, e:
        raise

    get_subscriptions(True)
    container = Alert(L('subscriptions'), LF('subscribed', podcast['title']))
    return Episodes(encode(podcast), container)


@client_required
def UnsubscribeFrom(podcast):
    try:
        session.client.update_subscriptions(DEVICE_ID, remove_urls=[podcast['url']])
    except Exception, e:
        raise

    get_subscriptions(True)
    container = Alert(L('subscriptions'), LF('unsubscribed', podcast['title']))
    return Podcast(encode(podcast), container)
