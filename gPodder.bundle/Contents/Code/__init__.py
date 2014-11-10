import cerealizer
import re
from functools import wraps
from operator import itemgetter
from time import time
from urllib2 import HTTPError, URLError, urlopen
from urllib import urlencode

import podcastparser
from mygpoclient.simple import Podcast
from session import Session, InvalidClientError


PREFIX = '/music/gpodder'
NAME = 'gPodder'
ICON = 'icon-default.png'
DEVICE_ID = 'plex-gpodder-plugin.%s' % Network.Hostname
TOPLIST_CACHE_TIME = 86400 # one day
SUBSCRIPTIONS_CACHE_TIME = 604800 # one week
EXCLUDE_REGEX = re.compile(r'[^\w\d]|the\s')
AUDIO_URL_REGEX = re.compile(r'(https?\:\/\/(?:[^/\s]+)?(?:(?:\/[^\s]*)*\/)?(?:[^\s]*?\.(?P<ext>m4[abpvr]|3gp|mp4|aac|mp3)))')

_ = Locale.LocalString
session = None
cerealizer.register(Podcast)


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
            return ErrorInvalidPrefs(_('invalid public client'))
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
            return ErrorInvalidPrefs(_('invalid client'))
        else:
            return func(*args, **kwargs)
    return wrapper


#==============================================================================
# Helper Functions
#==============================================================================

def use_cache(since, now=None):
    if not now:
        now = int(time())
    diff = now - since
    return diff < 86400


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


def get_updated_subscriptions():
    since = Dict['subscriptions_accessed'] or 0
    try:
        changes = session.client.pull_subscriptions(DEVICE_ID, since)
    except Exception:
        return Error(_('subscriptions error'))
    Dict['subscriptions_accessed'] = changes.since

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


def create_media_objects(episode):
    enclosures = episode['enclosures']

    # look for audio files in episode description if no enclosures are found
    if not len(enclosures) and episode.get('description'):
        matches = AUDIO_URL_REGEX.findall(episode.get('description'))
        enclosures = [{'url': i[0], 'mime_type': determine_mime_type(i[1])} for i in matches]

    # filter enclosures on duplicate urls
    enclosures = {i['url']:i for i in enclosures}.values()
    Log(enclosures)
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
    return Alert(_('Error'), message)


def ErrorInvalidPrefs(message):
    """
    mygpo API error with current preferences
    """

    container = Error(message)
    container.add(PrefsObject(title=_('preferences')))
    return container


def ValidatePrefs():
    global session

    # ensure at least server field is filled out
    if not (Prefs['server']):
        return ErrorInvalidPrefs(_('prefs incomplete'))

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
            return ErrorInvalidPrefs(_('invalid public client'))
        finally:
            remove_public_client_cache()

    # clear cached client data if username/password has successfully changed
    if session.dirty_client:
        try:
            session.create_client()
        except InvalidClientError:
            return ErrorInvalidPrefs(_('invalid client'))
        finally:
            Log(session.client)
            remove_client_cache()

    if session.dirty_device_name:
        session.update_device()


def Start():
    global session

    session = Session(DEVICE_ID)
    ValidatePrefs()


#==============================================================================
# Containers
#==============================================================================

@handler(PREFIX, NAME, thumb=ICON)
def MainMenu():
    container = ObjectContainer(title1=NAME)
    container.add(DirectoryObject(
        key=Callback(Recent),
        title=_('recent'),
        summary=_('recent summary'),
        thumb=Resource.ExternalPath('icon-recent.png')
    ))
    container.add(DirectoryObject(
        key=Callback(Subscriptions),
        title=_('subscriptions'),
        summary=_('subscriptions summary'),
        thumb=Resource.ExternalPath('icon-subscriptions.png')
    ))
    container.add(DirectoryObject(
        key=Callback(Recommendations),
        title=_('recommendations'),
        summary=_('recommendations summary')
    ))
    container.add(DirectoryObject(
        key=Callback(Toplist),
        title=_('toplist'),
        summary=_('toplist summary'),
        thumb=Resource.ExternalPath('icon-popular.png')
    ))
    container.add(InputDirectoryObject(
        key=Callback(Search),
        title=_('search'),
        prompt=_('search prompt'),
        summary=_('search summary'),
        thumb=Resource.ExternalPath('icon-search.png')
    ))
    container.add(InputDirectoryObject(
        key=Callback(Subscribe),
        title=_('subscribe'),
        prompt=_('subscribe prompt'),
        summary=_('subscribe summary'),
        thumb=Resource.ExternalPath('icon-add.png')
    ))
    container.add(PrefsObject(
        title=_('preferences'),
        summary=_('preferences summary')
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
        return Error(_('search error'))

    container = ObjectContainer(title1=NAME, title2=_('search results'))
    for entry in search_results:
        container.add(TVShowObject(
            key=Callback(Podcast, entry=entry),
            rating_key=entry.url,
            summary=entry.description,
            thumb=Resource.ContentsOfURLWithFallback(url=entry.logo_url, fallback=ICON),
            title=entry.title,
        ))
    return container


@route(PREFIX + '/subscribe/{query}')
@client_required
def Subscribe(query):
    """
    Subscribe
    """

    url = query
    podcasts = get_updated_subscriptions()

    # if the user is already subscribed to the feed, alert and return
    if url in [i.url for i in podcasts]:
        message = '%s %s' % (_('already subscribed'), url)
        return Alert(_('subscribe'), message)

    try:
        podcast = session.public_client.get_podcast_data(url)
    except Exception:
        return Error(_('url error'))
    return SubscribeTo(podcast)


@route(PREFIX + '/toplist/{page}')
@public_client_required
def Toplist(page=0, container=None):
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
        except Exception, e:
            return Error(_('toplist error'))
        else:
            Data.SaveObject('toplist', toplist)
            Dict['toplist_accessed'] = now
    else:
        Log('Using cached toplist')

        toplist = Data.LoadObject('toplist')

    if not container:
        container = ObjectContainer()
    container.title1 = NAME
    container.title2 = _('toplist')

    for index, entry in enumerate(toplist):
        container.add(DirectoryObject(
            key=Callback(Podcast, entry=entry),
            summary=entry.description,
            thumb=Resource.ContentsOfURLWithFallback(url=entry.logo_url, fallback=ICON),
            title=entry.title,
        ))
    return container


# @route(PREFIX + '/podcast/{entry}')
@public_client_required
def Podcast(entry, container=None):
    """
    Podcast
    """

    # if the user is not logged in, just show the episodes
    if not session.client:
        return Episodes(entry, container)

    if not container:
        container = ObjectContainer()
    container.title1 = NAME
    container.title2 = entry.title
    container.no_cache = True
    container.add(DirectoryObject(
        key=Callback(Episodes, podcast=entry),
        thumb=Resource.ContentsOfURLWithFallback(url=entry.logo_url, fallback=ICON),
        summary=entry.description,
        title=_('Episodes'),
    ))

    # Check to see if podcast is in user's subscriptions and present
    # subscribe/unsubscribe objects accordingly
    podcasts = get_updated_subscriptions()
    if entry.url in [i.url for i in podcasts]:
        obj = DirectoryObject(
            key=Callback(UnsubscribeFrom, podcast=entry),
            title=_('Unsubscribe'),
            summary=_('unsubscribe from summary'),
            thumb=Resource.ExternalPath('icon-remove.png')
        )
    else:
        obj = DirectoryObject(
            key=Callback(SubscribeTo, podcast=entry),
            title=_('Subscribe'),
            summary=_('subscribe to summary'),
            thumb=Resource.ExternalPath('icon-add.png')
        )
    container.add(obj)
    return container


# @route(PREFIX + '/episodes/{podcast}')
def Episodes(podcast, container=None):
    """
    Episodes
    """

    try:
        response = podcastparser.parse(podcast.url, urlopen(podcast.url))
    except HTTPError:
        return Error(_('url error'))
    episodes = response['episodes']

    if not len(episodes):
        return Alert(_('Episodes'), _('no subscriptions'))

    if not container:
        container = ObjectContainer()
    container.title1 = NAME
    container.title2 = podcast.title

    for entry in episodes:
        container.add(Track(entry, podcast.logo_url))
    return container


# @route(PREFIX + '/track/{episode}')
def Track(episode, logo_url, include_container=False):
    """
    Track
    """

    summary = podcastparser.remove_html_tags(episode.get('description'))
    if not summary:
        summary = episode.get('subtitle', _('No Summary'))

    obj = TrackObject(
        key=Callback(Track, episode=episode, logo_url=logo_url, include_container=True),
        rating_key=episode['guid'],
        title=episode.get('title', _('No Title')),
        thumb=Resource.ContentsOfURLWithFallback(url=logo_url, fallback=ICON),
        summary=summary,
        duration=episode['total_time'] * 1000,
        items=create_media_objects(episode)
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
    container.title1 = NAME
    container.title2 = _('Recently Aired')
    return container


@route(PREFIX + '/subscriptions')
@client_required
def Subscriptions(container=None):
    """
    Subscriptions

    List all podcasts user is currently subscribed to.
    Allow user to select a podcast and see its episodes or unsubscribe from it.
    """

    podcasts = get_updated_subscriptions()
    if not len(podcasts):
        return Alert(_('subscriptions'), _('no subscriptions'))

    if not container:
        container = ObjectContainer(no_cache=True)
    container.title1 = NAME
    container.title2 = _('My Subscriptions')

    for entry in podcasts:
        container.add(DirectoryObject(
            key=Callback(Podcast, entry=entry),
            summary=entry.description,
            thumb=Resource.ContentsOfURLWithFallback(url=entry.logo_url, fallback=ICON),
            title=entry.title,
        ))
    return container


@route(PREFIX + '/recommendations/{page}')
@client_required
def Recommendations(page=0, container=None):
    """
    Recommended podcasts
    """

    recommendations = session.client.get_suggestions()

    if not len(recommendations):
        return Alert(_('recommendations'), _('no recommendations'))

    if not container:
        container = ObjectContainer()
    container.title1 = NAME
    container.title2 = _('recommendations')

    for index, entry in enumerate(recommendations):
        Log('%4d. %s (%d)' % (index+1, entry.title, entry.subscribers))
        container.add(DirectoryObject(
            key=Callback(Podcast, entry=entry),
            summary=entry.description,
            thumb=Resource.ContentsOfURLWithFallback(url=entry.logo_url, fallback=ICON),
            title=entry.title,
        ))
    return container


@client_required
def SubscribeTo(podcast):
    try:
        session.client.update_subscriptions(DEVICE_ID, add_urls=[podcast.url])
    except Exception, e:
        raise

    message = '%s %s' % (_('subscribed'), podcast.title)
    container = Alert(_('subscriptions'), message)
    return Episodes(podcast, container)


@client_required
def UnsubscribeFrom(podcast):
    try:
        session.client.update_subscriptions(DEVICE_ID, remove_urls=[podcast.url])
    except Exception, e:
        raise

    message = '%s %s' % (_('unsubscribed'), podcast.title)
    container = Alert(_('subscriptions'), message)
    return Podcast(podcast, container)
