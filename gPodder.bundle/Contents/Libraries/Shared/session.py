from mygpoclient import api
from mygpoclient.http import Unauthorized, NotFound


class Session(object):
    """docstring for Session
    """

    def __init__(self, device_id):
        self._device_id = device_id
        self._server = ''
        self._device_name = ''
        self._username = ''
        self._password = ''
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

    def set_prefs(self, server, device_name, username, password):
        self.server = server
        self.device_name = device_name
        self.username = username
        self.password = password

    def set_public_client(self):
        public_client = api.public.PublicClient(self._server)
        try:
            public_client.get_toplist(1)
        except Exception, e:
            self._public_client = None
        else:
            self._public_client = public_client
        self._public_client_is_dirty = False
        return self._public_client

    def set_client(self):
        client = api.MygPodderClient(self._username, self._password, self._server)
        try:
            client.get_suggestions(1)
        except Exception, e:
            self._client = None
        else:
            self._client = client
        self._client_is_dirty = False
        return self._client

    def update_device(self):
        try:
            self._client.update_device_settings(self._device_id, type='server',
                                                caption=self._device_name)
        except Exception, e:
            raise
        else:
            pass
        finally:
            pass
