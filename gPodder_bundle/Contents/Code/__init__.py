import cerealizer
from functools import wraps

from mygpoclient import api
from mygpoclient.http import Unauthorized, NotFound

from session import Session


NAME = 'gPodder'
ICON = 'icon-default.png'

cerealizer.register(api.simple.Podcast)

session = None


def public_client_required(func):
    '''Wrapper to check the connection state of the mygpo server
    '''

    @wraps(func)
    def wrapper(*args, **kwargs):
        global session

        if not session.public_client:
            return InvalidPrefs('Please set mygpo webservice in Preferences.')
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
            return InvalidPrefs('Please set username and password in Preferences.')
        else:
            return func(*args, **kwargs)
    return wrapper


def ValidatePrefs():
    global session

    server = Prefs['server']
    device_id = Prefs['device_id']
    username = Prefs['username']
    password = Prefs['password']

    if not (server and device_id and username and password):
        return InvalidPrefs('Please set all fields in Preferences.')

    session.set_prefs(server, device_id, username, password)

    if not session.public_client:
        return InvalidPrefs('Could not connect to mygpo webservice.')

    if not session.client:
        return InvalidPrefs('Could not authenticate username & password.')


def Start():
    global session

    session = Session(Prefs['server'], Prefs['device_id'], Prefs['username'],
                      Prefs['password'])


@handler('/music/gpodder', NAME, thumb=ICON)
def MainMenu():
    oc = ObjectContainer()
    oc.add(DirectoryObject(key=Callback(Subscriptions), title='My Subscriptions'))
    oc.add(DirectoryObject(key=Callback(Toplist), title='My Recommendations'))
    oc.add(DirectoryObject(key=Callback(Toplist), title='Most Popular'))
    oc.add(DirectoryObject(key=Callback(Search), title='Search'))
    oc.add(PrefsObject(title='Preferences'))
    return oc


def InvalidPrefs(message):
    '''mygpo API error with current preferences
    '''
    oc = ObjectContainer(no_history=True, header='Preferences Error',
                         message=message)
    oc.add(PrefsObject(title='Preferences'))
    return oc


@route('/music/gpodder/search/{query}')
def Search(query=None):
    '''Search
    '''
    pass


@client_required
@route('/music/gpodder/subscriptions')
def Subscriptions():
    '''Subscriptions
    List all podcasts user is currently subscribed to.
    Allow user to select a podcast and see its episodes or unsubscribe from it.
    '''
    global session

    try:
        urls = session.client.get_subscriptions(Prefs['device_id'])
    except NotFound, e:
        urls = []
    finally:
        pass

    Log(urls)

    oc = ObjectContainer(title1=NAME, title2='My Subscriptions')
    for url in urls:
        # Log('%4d. %s (%d)' % (index+1, entry.title, entry.subscribers))
        oc.add(DirectoryObject(
            title=url,
        ))
    return oc

@public_client_required
@route('/music/gpodder/toplist/{page}')
def Toplist(page=0):
    '''Top List
    List 50 most-popular podcasts and allow user to subscribe to each.
    '''
    global session

    toplist = session.public_client.get_toplist()

    oc = ObjectContainer(title1=NAME, title2='Most Popular')
    for index, entry in enumerate(toplist):
        # Log('%4d. %s (%d)' % (index+1, entry.title, entry.subscribers))
        oc.add(TVShowObject(
            key=Callback(Podcast, entry=entry),
            rating_key=entry.url,
            summary=entry.description,
            thumb=Resource.ContentsOfURLWithFallback(url=entry.logo_url, fallback=ICON),
            title=entry.title,
        ))
    return oc


def Podcast(entry):
    Log('%s (%d), %s' % (entry.title, entry.subscribers, entry.logo_url))
    oc = ObjectContainer(title1=NAME, title2=entry.title)
    oc.add(DirectoryObject(
        key=Callback(Subscribe, title=entry.title),
        thumb=Resource.ContentsOfURLWithFallback(url=entry.logo_url, fallback=ICON),
        summary=entry.description,
        title='Subscribe',
    ))
    return oc


@client_required
def Subscribe(title):
    success_message = 'Subscribed to %s' % title
    return ObjectContainer(no_history=True, header='Subscriptions',
                           message=success_message)

