import cerealizer
from functools import wraps
from time import time
from urllib2 import URLError
from urllib import urlencode

from mygpoclient.simple import Podcast

from session import Session


NAME = 'gPodder'
ICON = 'icon-default.png'
DEVICE_ID = 'plex-gpodder-plugin.%s' % Network.Hostname
FEEDSERVICE_URL = 'http://feeds.gpodder.net'
CACHE_TIME = 86400 # one day

cerealizer.register(Podcast)

session = None


#==============================================================================
# Decorators
#==============================================================================

def public_client_required(func):
    '''Wrapper to check the connection state of the mygpo server
    '''

    @wraps(func)
    def wrapper(*args, **kwargs):
        global session

        if not session.public_client:
            return ErrorInvalidPrefs(L('invalid_public_client'))
        else:
            return func(*args, **kwargs)
    return wrapper


def client_required(func):
    '''Wrapper to check the login state of the mygpo user
    '''

    @wraps(func)
    def wrapper(*args, **kwargs):
        global session

        if not session.client:
            return ErrorInvalidPrefs(L('invalid_client'))
        else:
            return func(*args, **kwargs)
    return wrapper


#==============================================================================
#
#==============================================================================

def use_cache(since, now=None):
    if not now:
        now = int(time())
    diff = now - since
    return diff < CACHE_TIME


def remove_public_client_cache():
    Data.Remove('toplist')
    if 'toplist_accessed' in Dict:
        del Dict['toplist_accessed']
    Dict.Save()


def remove_client_cache():
    Data.Remove('subscriptions')
    if 'subscriptions_accessed' in Dict:
        del Dict['subscriptions_accessed']
    Dict.Save()


def Alert(header, message):
    return ObjectContainer(
        header=header,
        message=message,
        no_history=True,
        no_cache=True,
    )

def Error(message):
    return Alert('Error', message)


def ErrorInvalidPrefs(message):
    '''mygpo API error with current preferences
    '''

    oc = Error(message)
    oc.add(PrefsObject(title=L('preferences')))
    return oc


def ValidatePrefs():
    global session

    server = Prefs['server']
    device_name = Prefs['device_name']
    username = Prefs['username']
    password = Prefs['password']

    # ensure all preference fields are filled out
    if not (server and device_name and username and password):
        return ErrorInvalidPrefs(L('prefs_incomplete'))

    # update session
    session.set_vars(server, device_name, username, password)

    # clear cached public client data if the webservice has successfully changed
    if session.public_client_is_dirty:
        try:
            session.create_public_client()
        except Exception, e:
            return ErrorInvalidPrefs(L('prefs_bad_public_client'))
        finally:
            remove_public_client_cache()

    # clear cached client data if username/password has successfully changed
    if session.client_is_dirty:
        try:
            session.create_client()
        except Exception, e:
            return ErrorInvalidPrefs(L('prefs_bad_client'))
        finally:
            remove_client_cache()

    if session.device_name_is_dirty:
        session.update_device()


def Start():
    global session

    session = Session(DEVICE_ID, FEEDSERVICE_URL)
    ValidatePrefs()
    session.create_feedservice_client()


#==============================================================================
# Containers
#==============================================================================

@handler('/music/gpodder', NAME, thumb=ICON)
def MainMenu():
    oc = ObjectContainer(title1=NAME, no_cache=True)
    oc.add(DirectoryObject(key=Callback(Recent), title=L('recent')))
    oc.add(DirectoryObject(key=Callback(Subscriptions), title=L('subscriptions')))
    oc.add(DirectoryObject(key=Callback(Recommendations), title=L('recommendations')))
    oc.add(DirectoryObject(key=Callback(Toplist), title=L('toplist')))
    oc.add(InputDirectoryObject(key=Callback(Search), title=L('search'),
                                prompt=L('search_prompt')))
    oc.add(PrefsObject(title=L('preferences')))
    return oc


@route('/music/gpodder/search/{query}')
@public_client_required
def Search(query):
    '''Search
    '''

    try:
        search_results = session.public_client.search_podcasts(query)
    except URLError, e:
        return Error(L('error_search'))

    oc = ObjectContainer(title1=NAME, title2=L('search_results'))
    for entry in search_results:
        oc.add(TVShowObject(
            key=Callback(Podcast, entry=entry),
            rating_key=entry.url,
            summary=entry.description,
            thumb=Resource.ContentsOfURLWithFallback(url=entry.logo_url, fallback=ICON),
            title=entry.title,
        ))
    return oc


@route('/music/gpodder/toplist/{page}')
@public_client_required
def Toplist(page=0):
    '''Top List

    List 50 most-popular podcasts and allow user to subscribe to each.
    '''

    since = Dict['toplist_accessed'] or 0
    now = int(time())

    if not use_cache(since, now) or not Data.Exists('toplist'):
        Log('Using requested toplist')

        try:
            toplist = session.public_client.get_toplist()
        except Exception, e:
            return Error(L('error_toplist'))
        Data.SaveObject('toplist', toplist)
        Dict['toplist_accessed'] = now
    else:
        Log('Using cached toplist')

        toplist = Data.LoadObject('toplist')


    oc = ObjectContainer(title1=NAME, title2=L('toplist'))
    for index, entry in enumerate(toplist):
        oc.add(TVShowObject(
            key=Callback(Podcast, entry=entry),
            rating_key=entry.url,
            summary=entry.description,
            thumb=Resource.ContentsOfURLWithFallback(url=entry.logo_url, fallback=ICON),
            title=entry.title,
        ))
    return oc


# @route('/music/gpodder/podcast/{page}')
@public_client_required
def Podcast(entry):
    Log(entry.url)
    oc = ObjectContainer(title1=NAME, title2=entry.title)

    oc.add(TVShowObject(
        key=Callback(Episodes, podcast=entry),
        rating_key=entry.mygpo_link,
        thumb=Resource.ContentsOfURLWithFallback(url=entry.logo_url, fallback=ICON),
        summary=entry.description,
        title='Episodes',
    ))

    # TODO: Check to see if this is in user's subscriptions and present
    # subscribe/unsubscribe button accordingly
    if session.client:
        oc.add(DirectoryObject(
            key=Callback(Subscribe, entry=entry),
            title='Subscribe',
        ))

    return oc


@public_client_required
def Episodes(podcast):

    response = session.feedservice_client.parse_feeds([podcast.url]).get_feed(podcast.url)
    entries = response['episodes']

    oc = ObjectContainer(title1=NAME, title2=podcast.title)
    for entry in entries:
        # TODO: Make additional parser to get all these properties
        # to create the track object
        title = '%s - %s' % (podcast.title, entry.get('title', 'No Title'))

        try:
            duration = int(entry.get('duration', 0)) * 1000
        except Exception, e:
            duration = None

        oc.add(TrackObject(
            key=entry['link'],
            rating_key=entry['link'],
            # TODO: make language-agnostic fallbacks
            title=entry.get('title', 'No Title'),
            summary=entry.get('subtitle', 'No Summary'),
            artist=entry.get('author', 'No Author'),
            # tags=[tag['term'] or None for tag in entry.get('tags', [])],
            items=[MediaObject(
                audio_channels=2,
                audio_codec=AudioCodec.MP3, # parse mimetype for this
                parts=[PartObject(
                    key=entry['files'][0]['urls'][0],
                    duration=duration,
                )]
            )]
        ))
    return oc


@route('/music/gpodder/recent')
@client_required
def Recent():
    '''Recently Aired

    List the most-recently aired episodes in user's subscriptions.
    '''

    oc = ObjectContainer(title1=NAME, title2='Recently Aired')
    return oc


@route('/music/gpodder/subscriptions')
@client_required
def Subscriptions():
    '''Subscriptions

    List all podcasts user is currently subscribed to.
    Allow user to select a podcast and see its episodes or unsubscribe from it.
    '''

    # 1. Pull episode changes since stored 'since' timestamp
    #    (set to zero if nonexistant)
    # 2. Save 'since' timestamp from episode changes
    # If saved subscriptions list exists:
    #   3. append the episode changes add list to subscriptions list
    #   4. remove the episode changes remove list items from subscriptions list
    #   5. Save updated subscriptions
    # If saved subscriptions list doesn't exist:
    #   3. Save subscriptions changes add list as subscriptions

    since = Dict['subscriptions_accessed'] or 0
    try:
        subscriptions_changes = session.client.pull_subscriptions(DEVICE_ID, since)
    except Exception, e:
        return Error(L('error_subscriptions'))
    Dict['subscriptions_accessed'] = subscriptions_changes.since

    if Data.Exists('subscriptions'):
        subscriptions = cerealizer.loads(Data.Load('subscriptions'))
        initial_subscriptions = subscriptions[:]
        # remove urls returned from subscriptions changes
        for url in subscriptions_changes.remove:
            if url in subscriptions:
                subscriptions.remove(url)
        # add urls returned from subscriptions changes
        subscriptions += subscriptions_changes.add
        # if subscriptions list has changed at all from the above two
        # operations, write subscriptions to disk
        if subscriptions != initial_subscriptions:
            Data.Save('subscriptions', cerealizer.dumps(subscriptions))
    else:
        subscriptions = subscriptions_changes.add[:]
        Data.Save('subscriptions', cerealizer.dumps(subscriptions))

    if not len(subscriptions):
        return Alert('Subscriptions', L('alert_no_subscriptions'))

    oc = ObjectContainer(title1=NAME, title2='My Subscriptions')
    for url in subscriptions:
        entry = session.public_client.get_podcast_data(url)
        oc.add(TVShowObject(
            key=Callback(Podcast, entry=entry),
            rating_key=entry.url,
            summary=entry.description,
            thumb=Resource.ContentsOfURLWithFallback(url=entry.logo_url, fallback=ICON),
            title=entry.title,
        ))
    return oc


@route('/music/gpodder/recommendations/{page}')
@client_required
def Recommendations(page=0):
    '''Recommended podcasts
    '''

    recommendations = session.client.get_suggestions()

    if not len(recommendations):
        return ObjectContainer(no_history=True, header=L('recommendations'),
                               message=L('alert_no_recommendations'))

    oc = ObjectContainer(title1=NAME, title2=L('recommendations'))
    for index, entry in enumerate(recommendations):
        Log('%4d. %s (%d)' % (index+1, entry.title, entry.subscribers))
        oc.add(TVShowObject(
            key=Callback(Podcast, entry=entry),
            rating_key=entry.mygpo_link,
            summary=entry.description,
            thumb=Resource.ContentsOfURLWithFallback(url=entry.logo_url, fallback=ICON),
            title=entry.title,
        ))
    return oc


@client_required
def Subscribe(entry):
    try:
        session.client.update_subscriptions(DEVICE_ID, to_add=[entry.url])
    except Exception, e:
        raise

    success_message = ' '.join((L('subscribed'), entry.title))
    return Alert('Subscriptions', success_message)


@client_required
def Unsubscribe(entry):
    try:
        session.client.update_subscriptions(DEVICE_ID, to_remove=[entry.url])
    except Exception, e:
        raise

    success_message = ' '.join((L('unsubscribed'), entry.title))
    return Alert('Subscriptions', success_message)
