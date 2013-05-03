# from mygpoclient import simple

# VIDEO_PREFIX = '/music/gpodder'
# NAME = 'gPodder Plugin'

# def authenticate():
#   pass

# def Start():
#   client = simple.SimpleClient('nolsto', '5vN#jJY!A&')
#   Log(client)

from mygpoclient import public, simple


NAME = 'gPodder'
MUSIC_PREFIX = '/music/gpodder'
VIDEO_PREFIX = '/video/gpodder'

ICON = 'icon-default.png'
# ART = 'art-default.png'

PREF_SERVER = 'server'
PREF_USERNAME = 'username'
PREF_PASSWORD = 'password'
PREF_DEVICE_ID = 'device_id'

gpo_clients = {'public': None, 'simple': None}

# @handler(MUSIC_PREFIX, NAME, thumb=ICON)
def Start():
    gpo_clients['public'] = public.PublicClient()
    # simple_client = simple.SimpleClient(Prefs[PREF_USERNAME],
    #                                     Prefs[PREF_PASSWORD],
    #                                     Prefs[PREF_SERVER])

    # toplist = public_client.get_toplist()
    # for index, entry in enumerate(toplist):
    #     Log('%4d. %s (%d)' % (index+1, entry.title, entry.subscribers))

    # Plugin.AddViewGroup('Top List', viewMode='List', mediaType='items')

    # Initialize the plugin
    Plugin.AddPrefixHandler(MUSIC_PREFIX, MainMenu, NAME, ICON)
    Plugin.AddViewGroup('List', viewMode='List', mediaType='items')

    # Setup the artwork associated with the plugin
    # MediaContainer.art = R(ART)
    MediaContainer.title1 = NAME
    MediaContainer.viewGroup = 'List'

    DirectoryItem.thumb = R(ICON)

def MainMenu():
    container = ObjectContainer()
    # dir = MediaContainer(viewMode="List")
    container.add(PrefsObject(title='Preferences'))
    container.add(DirectoryObject(key = Callback(TopListMenu),
                                  title = 'Most Popular'))

    return container

def TopListMenu():
    pass
