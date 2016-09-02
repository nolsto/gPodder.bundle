import cerealizer
import re
from time import time
from urllib2 import HTTPError, urlopen

import podcastparser
from mygpoclient.simple import Podcast

from .plex_framework_api import (
    Callback,
    Data,
    Datetime,
    Dict,
    DirectoryObject,
    InputDirectoryObject,
    Log,
    MediaObject,
    Network,
    PartObject,
    Prefs,
    PrefsObject,
    R,
    Resource,
    TrackObject,
    TVShowObject,
    handler,
)
from .shortcuts import L, LF
from .utils import (clear_cache, get_audio_codec_from_mime_type,
                    get_container_from_audio_codec, get_mime_type_from_ext,
                    podcast_to_dict)
from .containers import AlertContainer, ErrorContainer, ObjectContainer
from .exceptions import InvalidPrefsError
from .decorators import (
    app_route, client_required, public_client_required, use_cache,
)

from session import (Client, PublicClient, Session, InvalidClientError,
                     InvalidPublicClientError)


cerealizer.register(Podcast)
cerealizer.register(Client)
cerealizer.register(PublicClient)
cerealizer.register(Session)


PREFIX = '/music/gpodder'
NAME = 'gPodder'
ICON = 'icon-default.png'
DEVICE_ID = 'plex-gpodder-plugin.%s' % Network.Hostname

TOPLIST_CACHE_TIME = 86400 # one day
SUBSCRIPTIONS_CACHE_TIME = 3600 # one hour

# TODO: See if undocumented Plex Regex() can work
EXCLUDE_REGEX = re.compile(r'[^\w\d]|the\s')
AUDIO_URL_REGEX = re.compile(r"""
    (\/\/                                # scheme
    (?:[^/\s]+)                          # domain name
    \/(?:[^\s]*\/)?                      # path
    (?:[^\s\/]*(?<=[^\/])\.              # filename
    (?P<ext>m4[abpvr]|mp[34]|3gp|aac)))  # extension
""")

if Data.Exists('session'):
    Log.Info('Using saved session')
    session = Data.LoadObject('session')
else:
    session = Session(DEVICE_ID)


def validate_prefs():
    try:
        # update session properties
        session.server = Prefs['server']
        session.device_name = Prefs['device_name']
        session.username = Prefs['username']
        session.password = Prefs['password']
        # get/create mygpo clients and clear caches if clients are new
        _, created = session.get_or_create_public_client()
        if created:
            clear_cache(data_attrs=('subscriptions',),
                        dict_items=('subscriptions_accessed',))
            Log.Info("public client cache cleared")
        _, created = session.get_or_create_client()
        if created:
            clear_cache(data_attrs=('toplist',),
                        dict_items=('toplist_accessed',))
            Log.Info("client cache cleared")
        Data.SaveObject('session', session)
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
        InputDirectoryObject(
            key=Callback(subscribe),
            title=L('subscribe'),
            prompt=L('subscribe prompt'),
            summary=L('subscribe summary'),
            thumb=R('icon-add.png'),
        ),
        InputDirectoryObject(
            key=Callback(search),
            title=L('search'),
            prompt=L('search prompt'),
            summary=L('search summary'),
            thumb=R('icon-search.png'),
        ),
        PrefsObject(
            title=L('preferences'),
            summary=L('preferences summary'),
        ),
    ))
    # )).add(DirectoryObject(
    #     key=Callback(Recommendations),
    #     title=L('recommendations'),
    #     summary=L('recommendations summary')


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
    # Remove urls returned from subscriptions changes.
    subscriptions = [s for s in subscriptions
                     if s.url not in changes.remove]
    # Add urls returned from subscriptions changes.
    subscriptions += [session.public_client.get_podcast_data(url)
                      for url in changes.add]

    Data.SaveObject('subscriptions', subscriptions)
    return subscriptions


def update_subscriptions(add_entries=None, remove_entries=None):
    if add_entries is None:
        add_entries = ()
    if remove_entries is None:
        remove_entries = ()

    result = session.client.update_subscriptions(
        add_urls=[entry['url'] for entry in add_entries],
        remove_urls=[entry['url'] for entry in remove_entries],
    )
    subscriptions = get_subscriptions(use_cache=True)

    # Add new entries to subscriptions
    for entry in add_entries:
        for s in subscriptions:
            if s.url == entry['url']:
                break
        else:
            subscriptions.append(Podcast.from_dict(entry))

    # Update subscriptions who's urls have changed.
    for old_url, new_url in result.update_urls:
        for s in subscriptions:
            if s.url == old_url:
                s.url = new_url
                break

    Data.SaveObject('subscriptions', subscriptions)
    return subscriptions


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


@app_route('/subcribe_to', entry=dict)
@client_required
def subscribe_to(entry):
    try:
        update_subscriptions(add_entries=(entry,))
    except:
        return podcast(
            entry=entry,
            container=AlertContainer(L('subscriptions'),
                                     L('subscriptions update error')),
        )
    return episodes(
        entry=entry,
        container=AlertContainer(L('subscriptions'),
                                 LF('subscribed', entry['title'])),
    )


@app_route('/unsubscribe_from', entry=dict)
@client_required
def unsubscribe_from(entry):
    try:
        update_subscriptions(remove_entries=(entry,))
    except:
        return podcast(
            entry=entry,
            container=AlertContainer(L('subscriptions'),
                                     L('subscriptions update error')),
        )
    return podcast(
        entry=entry,
        container=AlertContainer(L('subscriptions'),
                                 LF('unsubscribed', entry['title'])),
    )


@app_route('/podcast', entry=dict)
def podcast(entry, container=None):
    """
    """
    if not session.client:
        # if the user is not logged in, just show the episodes
        return episodes(entry, container)

    if not container:
        container = ObjectContainer()
    else:
        container.replace_parent = True
    container.title2 = entry['title']
    container.no_cache = True
    container.add(DirectoryObject(
        key=Callback(episodes, entry=entry),
        thumb=Resource.ContentsOfURLWithFallback(url=entry['logo_url'],
                                                 fallback=ICON),
        summary=entry['description'],
        title=LF('episodes', entry['title'])
    ))

    # Check to see if podcast is in user's subscriptions and present
    # subscribe/unsubscribe objects accordingly
    subscriptions = get_subscriptions()
    if entry['url'] in [s.url for s in subscriptions]:
        obj = DirectoryObject(
            key=Callback(unsubscribe_from, entry=entry),
            title=L('Unsubscribe'),
            summary=L('unsubscribe from summary'),
            thumb=R('icon-remove.png'),
        )
    else:
        obj = DirectoryObject(
            key=Callback(subscribe_to, entry=entry),
            title=L('Subscribe'),
            summary=L('subscribe to summary'),
            thumb=R('icon-add.png'),
        )
    container.add(obj)
    return container


@app_route('/episodes', entry=dict, allow_sync=True)
def episodes(entry, container=None):
    """
    """
    try:
        # TODO: Use Plex's HTTP API
        response = podcastparser.parse(entry['url'], urlopen(entry['url']))
    except HTTPError:
        return ErrorContainer(L('url error'))

    if not len(response['episodes']):
        return AlertContainer(L('Episodes'), L('no episodes'))

    if not container:
        container = ObjectContainer()
    else:
        container.replace_parent = True
    container.title2 = entry['title']

    for e in response['episodes']:
        summary = podcastparser.remove_html_tags(e.get('description',
                                                       e.get('subtitle')))
        published_date = Datetime.FromTimestamp(e['published']).strftime("%x")
        published = LF('published', published_date)

        data = {k: e[k] for k in {'enclosures', 'guid'}}
        data.update(
            logo_url=entry['logo_url'],
            summary="%s %s" % (published, summary),
            title=e.get('title', L('no title')),
            total_time=e['total_time'] * 1000,
        )
        container.add(episode(entry=data))

    return container


def create_media_objects(entry):
    Log.Debug("%s", entry)
    enclosures = entry['enclosures']

    # look for audio files in entry description if no enclosures are found
    summary = entry.get('summary')
    if not len(enclosures) and summary:
        matches = AUDIO_URL_REGEX.findall(summary)
        enclosures = [{'url': m[0], 'mime_type': get_mime_type_from_ext(m[1])}
                      for m in matches]

    # Throw away duplicate enclosures.
    enclosures = [dict(t) for t in set([tuple(e.items()) for e in enclosures])]
    Log.Debug("%s", enclosures)

    objects = []
    for e in enclosures:
        audio_codec = get_audio_codec_from_mime_type(e['mime_type'])
        container = get_container_from_audio_codec(audio_codec)
        objects.append(
            MediaObject(
                audio_channels=2,
                audio_codec=audio_codec,
                container=container,
                parts=[PartObject(key=e['url'])],
            )
        )
    return objects


@app_route('/episode', entry=dict)
def episode(entry, include_container=False):
    """
    """
    obj = TrackObject(
        key=Callback(episode, entry=entry, include_container=True),
        rating_key=entry['guid'],
        title=entry.get('title', L('No Title')),
        summary=entry['summary'],
        duration=entry['total_time'],
        source_title=NAME,
        thumb=Resource.ContentsOfURLWithFallback(url=entry['logo_url'],
                                                 fallback=ICON),
        items=create_media_objects(entry),
    )

    if include_container:
        return ObjectContainer(objects=[obj])
    else:
        return obj


@app_route('/subscriptions')
@client_required
def subscriptions(container=None):
    """
    List all podcasts user is currently subscribed to.
    Allow user to select a podcast and see its episodes or unsubscribe from it.
    """
    subscriptions = get_subscriptions()
    if not len(subscriptions):
        return AlertContainer(L('subscriptions'), L('no subscriptions'))

    if not container:
        container = ObjectContainer(no_cache=True)
    container.title2 = L('subscriptions')

    for s in subscriptions:
        container.add(DirectoryObject(
            key=Callback(podcast, entry=podcast_to_dict(s)),
            title=s.title,
            summary=s.description,
            thumb=Resource.ContentsOfURLWithFallback(url=s.logo_url,
                                                     fallback=ICON),
        ))

    # Sort subscriptions on title.
    container.objects.sort(
        key=lambda x: EXCLUDE_REGEX.sub('', str(x.title).lower()),
    )
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
            key=Callback(podcast, entry=podcast_to_dict(item)),
            title=item.title,
            summary=item.description,
            thumb=Resource.ContentsOfURLWithFallback(url=item.logo_url,
                                                     fallback=ICON),
        ))
    return container


@app_route('/subscribe/{query}')
@client_required
def subscribe(query):
    """
    """
    # if the user is already subscribed to the feed, alert and return
    if query in [i.url for i in get_subscriptions()]:
        return AlertContainer(L('subscribe'), LF('already subscribed', query))
    try:
        item = session.public_client.get_podcast_data(query)
    except:
        return ErrorContainer(L('url error'))
    return subscribe_to(entry=podcast_to_dict(item))


@app_route('/search/{query}')
@public_client_required
def search(query):
    """
    """
    try:
        search_results = session.public_client.search_podcasts(query)
    except:
        return ErrorContainer(L('search error'))

    container = ObjectContainer(title2=L('search results'))
    for item in search_results:
        container.add(TVShowObject(
            key=Callback(podcast, entry=podcast_to_dict(item)),
            rating_key=item.url,
            title=item.title,
            summary=item.description,
            thumb=Resource.ContentsOfURLWithFallback(url=item.logo_url,
                                                     fallback=ICON),
        ))
    return container
