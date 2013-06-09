from mygpoclient import api
from mygpoclient.http import Unauthorized, NotFound


class Session(object):
    """docstring for Session
    """

    def __init__(self, *args, **kwargs):
        self._server = None
        self._device_id = None
        self._username = None
        self._password = None
        self._public_client = None
        self._client = None
        self.set_prefs(*args, **kwargs)

    def server():
        def fset(self, value):
            if value is self._server:
                return
            self._server = value
            self._public_client_is_dirty = True
            self._client_is_dirty = True
        return locals()
    server = property(**server())

    def username():
        def fset(self, value):
            if value is self._username:
                return
            self._username = value
            self._client_is_dirty = True
        return locals()
    username = property(**username())

    def password():
        def fset(self, value):
            if value is self._password:
                return
            self._password = value
            self._client_is_dirty = True
        return locals()
    password = property(**password())

    @property
    def public_client(self):
        return self._public_client

    @property
    def client(self):
        return self._client

    def set_prefs(self, server, device_id, username, password):
        self.server = server
        self._device_id = device_id
        self.username = username
        self.password = password

        if self._public_client_is_dirty:
            self.set_public_client()
            self._public_client_is_dirty = False

        if self._client_is_dirty:
            self.set_client()
            self._client_is_dirty = False

    def set_public_client(self):
        public_client = api.public.PublicClient(self._server)
        try:
            public_client.get_toplist(1)
        except Exception, e:
            self._public_client = None
        else:
            self._public_client = public_client

    def set_client(self):
        client = api.MygPodderClient(self._username, self._password, self._server)
        try:
            client.get_suggestions(1)
        except Exception, e:
            self._client = None
        else:
            self._client = client
