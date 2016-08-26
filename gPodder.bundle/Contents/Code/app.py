import cerealizer
import re
from time import time

from mygpoclient.simple import Podcast

from .plex_framework_api import (
    Callback,
    Data,
    Dict,
    DirectoryObject,
    Log,
    Network,
    Prefs,
    PrefsObject,
    R,
    Resource,
    handler,
)
from .utils import L, LF, clear_cache, encode, decode, podcast_to_dict
from .containers import AlertContainer, ErrorContainer, ObjectContainer
from .exceptions import InvalidPrefsError
from .decorators import (
    app_route, client_required, public_client_required, use_cache,
)

from session import Session, InvalidClientError, InvalidPublicClientError


cerealizer.register(Podcast)


PREFIX = '/music/gpodder'
NAME = 'gPodder'
ICON = 'icon-default.png'
DEVICE_ID = 'plex-gpodder-plugin.%s' % Network.Hostname

TOPLIST_CACHE_TIME = 86400 # one day
SUBSCRIPTIONS_CACHE_TIME = 60 # one minute

EXCLUDE_REGEX = re.compile(r'[^\w\d]|the\s')
AUDIO_URL_REGEX = re.compile(r'(https?\:\/\/(?:[^/\s]+)?(?:(?:\/[^\s]*)*\/)?(?:[^\s]*?\.(?P<ext>m4[abpvr]|3gp|mp4|aac|mp3)))')

session = Session(DEVICE_ID)


@use_cache('subscriptions_accessed', SUBSCRIPTIONS_CACHE_TIME)
def get_subscriptions(use_cache=False):
    if use_cache:
        if Data.Exists('subscriptions'):
            Log.Info('Using cached subscriptions')
            return Data.LoadObject('subscriptions')
        else:
            return get_subscriptions(use_cache=False)

    Log.Info('Requesting subscriptions')
    since = Dict['subscriptions_accessed'] or 0
    try:
        changes = session.client.pull_subscriptions(since)
    except:
        return ErrorContainer(L('subscriptions error'))
    Dict['subscriptions_accessed'] = changes.since

    Log.Info('Added: %s', changes.add)
    Log.Info('Removed: %s', changes.remove)

    if Data.Exists('subscriptions'):
        subscriptions = Data.LoadObject('subscriptions')
    else:
        subscriptions = []
    # remove urls returned from subscriptions changes
    subscriptions = [s for s in subscriptions
                     if s.url not in changes.remove]
    # add urls returned from subscriptions changes
    subscriptions += [session.public_client.get_podcast_data(url)
                      for url in changes.add]
    # sort subscriptions on title
    subscriptions = sorted(
        subscriptions,
        key=lambda x: EXCLUDE_REGEX.sub('', str(x.title).lower()),
    )
    Data.SaveObject('subscriptions', subscriptions)

    return subscriptions


def validate_prefs():
    try:
        # update session properties
        session.server = Prefs['server']
        session.device_name = Prefs['device_name']
        session.username = Prefs['username']
        session.password = Prefs['password']
        # create mygpo clients and clear caches if clients are new
        _, created = session.get_or_create_public_client()
        if created:
            clear_cache(
                ('subscriptions',),
                ('subscriptions_accessed',),
            )
            Log.Info("public client cache cleared")
        _, created = session.get_or_create_client()
        if created:
            clear_cache(
                ('toplist',),
                ('toplist_accessed',),
            )
            Log.Info("client cache cleared")
    except InvalidPrefsError as e:
        error_message = e.message
    except InvalidPublicClientError as e:
        Log.Warn("%s", e)
        error_message = L('public client error')
    except InvalidClientError as e:
        Log.Warn("%s", e)
        error_message = L('client error')
    else:
        return True
    return ErrorContainer(error_message, objects=(
        PrefsObject(title=L('preferences')),
    ))


def start():
    ObjectContainer.title1 = NAME
    DirectoryObject.thumb = R(ICON)
    validate_prefs()


@handler(PREFIX, NAME, ICON)
def main():
    return ObjectContainer(objects=(
        DirectoryObject(
            key=Callback(subscriptions),
            title=L('subscriptions'),
            summary=L('subscriptions summary'),
            thumb=R('icon-subscriptions.png')
        ),
        DirectoryObject(
            key=Callback(recent),
            title=L('recent'),
            summary=L('recent summary'),
            thumb=R('icon-recent.png'),
        ),
        DirectoryObject(
            key=Callback(toplist, page=0),
            title=L('toplist'),
            summary=L('toplist summary'),
            thumb=R('icon-popular.png'),
        ),
    ))
    # return container.add(DirectoryObject(
    #     key=Callback(recent),
    #     title=L('recent'),
    #     summary=L('recent summary'),
    #     thumb=R('icon-recent.png')
    # )).add(DirectoryObject(
    #     key=Callback(Subscriptions),
    #     title=L('subscriptions'),
    #     summary=L('subscriptions summary'),
    #     thumb=R('icon-subscriptions.png')
    # )).add(DirectoryObject(
    #     key=Callback(Recommendations),
    #     title=L('recommendations'),
    #     summary=L('recommendations summary')
    # )).add(DirectoryObject(
    #     key=Callback(Toplist),
    #     title=L('toplist'),
    #     summary=L('toplist summary'),
    #     thumb=R('icon-popular.png')
    # )).add(InputDirectoryObject(
    #     key=Callback(Search),
    #     title=L('search'),
    #     prompt=L('search prompt'),
    #     summary=L('search summary'),
    #     thumb=R('icon-search.png')
    # )).add(InputDirectoryObject(
    #     key=Callback(Subscribe),
    #     title=L('subscribe'),
    #     prompt=L('subscribe prompt'),
    #     summary=L('subscribe summary'),
    #     thumb=R('icon-add.png')
    # )).add(PrefsObject(
    #     title=L('preferences'),
    #     summary=L('preferences summary')
    # ))


@app_route('/recent')
@client_required
def recent(container=None):
    """
    List the most-recently-aired episodes in user's subscriptions.
    """
    if not container:
        container = ObjectContainer()
    container.title2 = L('recent')
    return container


@app_route('/subcribe_to')
@client_required
def subscribe_to(podcast_data):
    podcast = decode(podcast_data)
    try:
        session.client.update_subscriptions(add_urls=[podcast['url']])
    except:
        raise

    get_subscriptions(use_cache=True)
    return episodes(
        podcast_data,
        container=AlertContainer(L('subscriptions'),
                                 LF('subscribed', podcast['title'])),
    )


@app_route('/unsubscribe_from')
@client_required
def unsubscribe_from(podcast_data):
    podcast = decode(podcast_data)
    try:
        session.client.update_subscriptions(remove_urls=[podcast['url']])
    except:
        raise

    get_subscriptions(use_cache=True)
    return podcast(
        podcast_data,
        container=AlertContainer(L('subscriptions'),
                                 LF('unsubscribed', podcast['title'])),
    )


# @app_route('/podcast', entry_data=dict)
@app_route('/podcast')
@public_client_required
def podcast(entry_data, container=None):
    """
    """
    if not session.client:
        # if the user is not logged in, just show the episodes
        return episodes(entry_data, container)

    entry = decode(entry_data)

    if not container:
        container = ObjectContainer()
    container.title2 = entry['title']
    container.no_cache = True
    container.add(DirectoryObject(
        key=Callback(episodes, podcast_data=entry_data),
        thumb=Resource.ContentsOfURLWithFallback(url=entry['logo_url'],
                                                 fallback=ICON),
        summary=entry['description'],
        title=LF('episodes', entry['title'])
    ))

    # Check to see if podcast is in user's subscriptions and present
    # subscribe/unsubscribe objects accordingly
    podcasts = get_subscriptions()
    if entry['url'] in [i.url for i in podcasts]:
        obj = DirectoryObject(
            key=Callback(unsubscribe_from, podcast_data=encode(entry)),
            title=L('Unsubscribe'),
            summary=L('unsubscribe from summary'),
            thumb=R('icon-remove.png'),
        )
    else:
        obj = DirectoryObject(
            key=Callback(subscribe_to, podcast_data=encode(entry)),
            title=L('Subscribe'),
            summary=L('subscribe to summary'),
            thumb=R('icon-add.png'),
        )
    container.add(obj)
    return container


# @app_route('/episodes', podcast_data=dict, allow_sync=True)
@app_route('/episodes', allow_sync=True)
def episodes(podcast_data, container=None):
    """
    """
    Log.Debug("%s", podcast_data)
    # podcast = decode(podcast_data)

    # try: response = podcastparser.parse(podcast['url'], urlopen(podcast['url']))
    # except HTTPError:
    #     return Error(L('url error'))
    # episodes = response['episodes']

    # if not len(episodes):
    #     return Alert(L('Episodes'), L('no subscriptions'))

    # if not container:
    #     container = ObjectContainer()
    # container.title2 = podcast['title']

    # for entry in episodes:
    #     entry['logo_url'] = podcast['logo_url']
    #     container.add(Episode(encode(entry)))
    # return container
    return ObjectContainer(title2="Episodes")


@app_route('/subscriptions')
@client_required
def subscriptions(container=None):
    """
    List all podcasts user is currently subscribed to.
    Allow user to select a podcast and see its episodes or unsubscribe from it.
    """
    podcasts = get_subscriptions()
    if not len(podcasts):
        return AlertContainer(L('subscriptions'), L('no subscriptions'))

    if not container:
        container = ObjectContainer(no_cache=True)
    container.title2 = L('subscriptions')

    for item in podcasts:
        container.add(DirectoryObject(
            key=Callback(podcast, entry_data=encode(podcast_to_dict(item))),
            title=item.title,
            summary=item.description,
            thumb=Resource.ContentsOfURLWithFallback(url=item.logo_url,
                                                     fallback=ICON),
        ))
    return container


@app_route('/toplist/{page}', page=int)
@use_cache('toplist_accessed', TOPLIST_CACHE_TIME)
@public_client_required
def toplist(page=0, container=None, use_cache=False):
    """
    List 50 most-popular podcasts and allow user to subscribe to each.
    """
    if not use_cache or not Data.Exists('toplist'):
        Log.Info('Requesting toplist')
        try:
            toplist = session.public_client.get_toplist()
        except Exception:
            return ErrorContainer(L('toplist error'))
        Data.SaveObject('toplist', toplist)
        Dict['toplist_accessed'] = time()
    else:
        Log.Info('Using cached toplist')
        toplist = Data.LoadObject('toplist')

    if not container:
        container = ObjectContainer()
    container.title2 = L('toplist')

    for item in toplist:
        container.add(DirectoryObject(
            key=Callback(podcast, entry_data=encode(podcast_to_dict(item))),
            title=item.title,
            summary=item.description,
            thumb=Resource.ContentsOfURLWithFallback(url=item.logo_url,
                                                     fallback=ICON),
        ))
    return container
