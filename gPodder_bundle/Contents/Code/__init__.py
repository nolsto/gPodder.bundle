import cerealizer
from functools import wraps

from mygpoclient import api
from mygpoclient.http import Unauthorized, NotFound

# from session import Session


NAME = 'gPodder'
ICON = 'icon-default.png'

cerealizer.register(api.simple.Podcast)

mygpo_public_client = None
mygpo_client = None

current_server = Prefs['server']
current_username = Prefs['username']
current_password = Prefs['password']


def client_required(func):
    '''Wrapper to check the login state of the mygpo user
    '''

    @wraps(func)
    def wrapper(*args, **kwargs):
        global mygpo_public_client

        try:
            devices = mygpo_client.get_devices()
        except Unauthorized, e:
            Log('Unauthorized')
            return InvalidPrefs('Please set username and password in Preferences.')
        else:
            return func(*args, **kwargs)
    return wrapper

def login_required(func):
    '''Wrapper to check the login state of the mygpo user
    '''

    @wraps(func)
    def wrapper(*args, **kwargs):
        global mygpo_client

        try:
            devices = mygpo_client.get_devices()
        except Unauthorized, e:
            Log('Unauthorized')
            return InvalidPrefs('Please set username and password in Preferences.')
        else:
            return func(*args, **kwargs)
    return wrapper


def create_mygpo_public_client(server):
    global mygpo_public_client

    mygpo_public_client = api.public.PublicClient(Prefs['server'])


def create_mygpo_client(username, password, server):
    global mygpo_client

    mygpo_client = api.MygPodderClient(
        Prefs['username'],
        Prefs['password'],
        Prefs['server'],
    )


def ValidatePrefs():
    Log('Validating Preferences')

    global current_server, current_username, current_password

    server = Prefs['server']
    device_id = Prefs['device_id']
    username = Prefs['username']
    password = Prefs['password']

    if not (server and device_id and username and password):
        return InvalidPrefs('Please set all fields in Preferences.')

    if server is not current_server:
        # Server has changed. Recreate both mygpo clients
        create_mygpo_public_client(server)
        create_mygpo_client(username, password, server)

    elif (username, password) != (current_username, current_password):
        # Only username and/or password has changed. Recreate mygpo client
        create_mygpo_client(username, password, server)

    current_server = server
    current_username = username
    current_password = password


def Start():
    create_mygpo_public_client(current_server)
    create_mygpo_client(current_username, current_password, current_server)


@handler('/music/gpodder', NAME, thumb=ICON)
def MainMenu():
    oc = ObjectContainer()
    oc.add(DirectoryObject(key=Callback(Subscriptions), title='My Subscriptions'))
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


@login_required
@route('/music/gpodder/subscriptions')
def Subscriptions():
    '''Subscriptions
    List all podcasts user is currently subscribed to.
    Allow user to select a podcast and see its episodes or unsubscribe from it.
    '''
    try:
        urls = mygpo_client.get_subscriptions(Prefs['device_id'])
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


@route('/music/gpodder/toplist/{page}')
def Toplist(page=0):
    '''Top List
    List 50 most-popular podcasts and allow user to subscribe to each.
    '''
    toplist = mygpo_public_client.get_toplist()
    # for index, entry in enumerate(toplist):#
    #     Log('%4d. %s (%d)' % (index+1, entry.title, entry.subscribers))

    oc = ObjectContainer(title1=NAME, title2='Most Popular')
    for index, entry in enumerate(toplist):
        # Log('%4d. %s (%d)' % (index+1, entry.title, entry.subscribers))
        # oc.add(DirectoryObject(key=Callback(podcast, entry=entry),
        #                             title=entry.title))
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
    # oc = ObjectContainer(title2=entry.title, view_group='List')
    oc.add(DirectoryObject(
        key=Callback(Subscribe, title=entry.title),
        thumb=Resource.ContentsOfURLWithFallback(url=entry.logo_url, fallback=ICON),
        summary=entry.description,
        title='Subscribe',
    ))
    return oc


@login_required
def Subscribe(title):
    success_message = 'Subscribed to %s' % title
    return ObjectContainer(no_history=True, header='Subscriptions',
                           message=success_message)

