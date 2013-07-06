import cerealizer
from functools import wraps
from posixpath import basename
from time import time
from urllib2 import URLError
from urlparse import urlparse

from mygpoclient import api
from mygpoclient.http import Unauthorized, NotFound

from session import Session


NAME = 'gPodder'
ICON = 'icon-default.png'
DEVICE_ID = 'plex-gpodder-plugin.%s' % Network.Hostname
CACHE_TIME = 86400 # one day

cerealizer.register(api.simple.Podcast)

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
            return InvalidPrefs(L('invalid_public_client'))
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
            return InvalidPrefs(L('invalid_client'))
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


def Error(message):
    oc = ObjectContainer(no_history=True, header='Error',
                         message=message)
    return oc


def InvalidPrefs(message):
    '''mygpo API error with current preferences
    '''
    oc = ObjectContainer(no_history=True, header='Preferences Error',
                         message=message)
    oc.add(PrefsObject(title='Preferences'))
    return oc


def ValidatePrefs():
    global session

    server = Prefs['server']
    device_name = Prefs['device_name']
    username = Prefs['username']
    password = Prefs['password']

    if not (server and device_name and username and password):
        return InvalidPrefs(L('prefs_incomplete'))

    session.set_prefs(server, device_name, username, password)

    if session.public_client_is_dirty:
        if not session.set_public_client():
            return InvalidPrefs(L('prefs_bad_public_client'))
        else:
            remove_public_client_cache()

    if session.client_is_dirty:
        if not session.set_client():
            return InvalidPrefs(L('prefs_bad_client'))
        else:
            remove_client_cache()

    if session.device_name_is_dirty:
        session.update_device()


def Start():
    global session

    session = Session(DEVICE_ID)
    session.set_prefs(Prefs['server'], Prefs['device_name'], Prefs['username'],
                      Prefs['password'])

#==============================================================================
# Containers
#==============================================================================

@handler('/music/gpodder', NAME, thumb=ICON)
def MainMenu():
    oc = ObjectContainer(title1=NAME, no_cache=True)
    oc.add(DirectoryObject(key=Callback(Subscriptions), title='My Subscriptions'))
    oc.add(DirectoryObject(key=Callback(Recommendations), title='My Recommendations'))
    oc.add(DirectoryObject(key=Callback(Toplist), title='Most Popular'))
    oc.add(InputDirectoryObject(key=Callback(Search), title='Search',
                                prompt='Search Podcasts'))
    oc.add(PrefsObject(title='Preferences'))
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

    oc = ObjectContainer(title1=NAME, title2='Search Results')
    for entry in search_results:
        oc.add(TVShowObject(
            key=Callback(Podcast, entry=entry),
            rating_key=entry.url,
            summary=entry.description,
            thumb=Resource.ContentsOfURLWithFallback(url=entry.logo_url, fallback=ICON),
            title=entry.title,
        ))
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
    try:
        since = Dict['subscriptions_accessed'] or 0
        subscriptions_changes = session.client.pull_subscriptions(DEVICE_ID, since)
    except Exception, e:
        return Error(L('error_subscriptions'))

    if Data.Exists('subscriptions') and since > 0:
        Log('Using cached subscriptions')

        subscriptions = cerealizer.loads(Data.Load('subscriptions'))
        initial_subscriptions = subscriptions[:]
        # remove urls from subscriptions changes
        for url in subscriptions_changes.remove:
            if url in subscriptions:
                subscriptions.remove(url)
        # add urls from subscriptions changes
        subscriptions += subscriptions_changes.add
        # if subscriptions list has changed at all from the above two
        # operations, write subscriptions to disk
        if initial_subscriptions != subscriptions:
            Data.Save('subscriptions', cerealizer.dumps(subscriptions))
    else:
        Log('Using requested subscriptions')

        subscriptions = subscriptions_changes.add[:]
        Data.Save('subscriptions', cerealizer.dumps(subscriptions))

    Dict['subscriptions_accessed'] = subscriptions_changes.since

    oc = ObjectContainer(title1=NAME, title2='My Subscriptions', no_cache=True)
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
    else:
        Log('Using cached toplist')

        toplist = Data.LoadObject('toplist')

    Dict['toplist_accessed'] = now

    oc = ObjectContainer(title1=NAME, title2='Most Popular')
    for index, entry in enumerate(toplist):
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

    oc = ObjectContainer(title1=NAME, title2='My Recommendations')
    for index, entry in enumerate(recommendations):
        Log('%4d. %s (%d)' % (index+1, entry.title, entry.subscribers))
        oc.add(TVShowObject(
            key=Callback(Podcast, entry=entry),
            rating_key=entry.url,
            summary=entry.description,
            thumb=Resource.ContentsOfURLWithFallback(url=entry.logo_url, fallback=ICON),
            title=entry.title,
        ))
    return oc


@public_client_required
def Podcast(entry):
    oc = ObjectContainer(title1=NAME, title2=entry.title)

    oc.add(DirectoryObject(
        thumb=Resource.ContentsOfURLWithFallback(url=entry.logo_url, fallback=ICON),
        summary=entry.description,
        title='Subscribe',
    ))

    if session.client:
        oc.add(DirectoryObject(
            key=Callback(Unsubscribe, entry=entry),
            title='Unsubscribe',
        ))
    else:
        oc.add(DirectoryObject(
            key=Callback(Subscribe, entry=entry),
            title='Subscribe',
        ))
    return oc


@client_required
def Subscribe(entry):
    try:
        session.client.update_subscriptions(DEVICE_ID, to_add=[entry.url])
    except Exception, e:
        raise

    success_message = ' '.join((L('subscribed'), entry.title))
    return ObjectContainer(no_history=True, header='Subscriptions',
                           message=success_message)


@client_required
def Unsubscribe(entry):
    try:
        session.client.update_subscriptions(DEVICE_ID, to_remove=[entry.url])
    except Exception, e:
        raise

    success_message = ' '.join((L('unsubscribed'), entry.title))
    return ObjectContainer(no_history=True, header='Subscriptions',
                           message=success_message)
