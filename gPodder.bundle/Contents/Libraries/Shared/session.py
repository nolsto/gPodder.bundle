from mygpoclient.api import MygPodderClient
from mygpoclient.feeds import FeedserviceClient
from mygpoclient.public import PublicClient


class UnviablePublicClient(Exception):
    """docstring for UnviablePublicClient"""


class UnviableClient(Exception):
    """docstring for UnviableClient"""


class Session(object):
    '''docstring for Session
    '''

    def __init__(self, device_id, feedservice_url):
        self._device_id = device_id
        self._feedservice_url = feedservice_url
        self._server = ''
        self._device_name = ''
        self._username = ''
        self._password = ''
        self._feedservice_client = None
        self._public_client = None
        self._client = None
        self._public_client_is_dirty = True
        self._client_is_dirty = True
        self._device_name_is_dirty = True


    def server():
        def fset(self, value):
            if self._server == value:
                return
            self._server = value
            self._public_client_is_dirty = True
            self._client_is_dirty = True
        return locals()
    server = property(**server())


    def device_name():
        def fset(self, value):
            if self._device_name == value:
                return
            self._device_name = value
            self._device_name_is_dirty = True
        return locals()
    device_name = property(**device_name())


    def username():
        def fset(self, value):
            if self._username == value:
                return
            self._username = value
            self._client_is_dirty = True
        return locals()
    username = property(**username())


    def password():
        def fset(self, value):
            if self._password == value:
                return
            self._password = value
            self._client_is_dirty = True
        return locals()
    password = property(**password())


    @property
    def feedservice_client(self):
        return self._feedservice_client


    @property
    def public_client(self):
        return self._public_client


    @property
    def client(self):
        return self._client


    @property
    def public_client_is_dirty(self):
        return self._public_client_is_dirty


    @property
    def client_is_dirty(self):
        return self._client_is_dirty


    @property
    def device_name_is_dirty(self):
        return self._device_name_is_dirty


    def set_vars(self, server, device_name, username, password):
        self.server = server
        self.device_name = device_name
        self.username = username
        self.password = password


    def create_feedservice_client(self):
        '''Create and return a new feedservice client
        '''
        self._feedservice_client = FeedserviceClient(self._username,
                                                     self._password,
                                                     self._feedservice_url)


    def create_public_client(self):
        '''Create and return a new public client
        '''
        self._public_client = None
        client = PublicClient(self._server)
        try:
            # attempt a minimal-effort API call to test client viability
            client.get_toplist(1)
        except Exception, e:
            raise UnviablePublicClient()
        else:
            self._public_client = client
            self._public_client_is_dirty = False


    def create_client(self):
        '''Create and return a new client
        '''
        self._client = None
        client = MygPodderClient(self._username, self._password, self._server)
        try:
            # attempt a minimal-effort API call to test client viability
            client.get_suggestions(1)
        except Exception, e:
            raise UnviableClient()
        else:
            self._client = client
            self._client_is_dirty = False


    def update_device(self):
        try:
            self._client.update_device_settings(self._device_id, type='server',
                                                caption=self._device_name)
        except Exception, e:
            raise e
        else:
            pass
