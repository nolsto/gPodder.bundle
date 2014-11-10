from mygpoclient.api import MygPodderClient as MygpoClient
from mygpoclient.public import PublicClient as MygpoPublicClient


class InvalidClientError(Exception):
    """docstring for ErrorInvalidClient"""


class BaseClient(object):
    """
    docstring for BaseClient
    """

    def __init__(self):
        try:
            self.validate()
        except Exception:
            raise InvalidClientError()

    def validate(self):
        """attempt a minimal-effort API call to test client viability"""


class Client(MygpoClient, BaseClient):
    """
    docstring for Client
    """

    def __init__(self, username, password, server):
        MygpoClient.__init__(self, username, password, server)
        BaseClient.__init__(self)

    def validate(self):
        self.get_suggestions(1)


class PublicClient(MygpoPublicClient, BaseClient):
    """
    docstring for PublicClient
    """

    def __init__(self, server):
        MygpoPublicClient.__init__(self, server)
        BaseClient.__init__(self)

    def validate(self):
        self.get_toplist(1)


class Session(object):
    """docstring for Session"""

    def __init__(self, device_id):
        self._device_id = device_id

        self._server = ''
        self._device_name = ''
        self._username = ''
        self._password = ''

        self._public_client = None
        self._client = None

    def server():
        def fset(self, value):
            if self._server == value:
                return
            self._server = value
            self.dirty_public_client = True
            self.dirty_client = True
        return locals()
    server = property(**server())

    def device_name():
        def fset(self, value):
            if self._device_name == value:
                return
            self._device_name = value
            self.dirty_device_name = True
        return locals()
    device_name = property(**device_name())

    def username():
        def fset(self, value):
            if self._username == value:
                return
            self._username = value
            self.dirty_client = True
        return locals()
    username = property(**username())

    def password():
        def fset(self, value):
            if self._password == value:
                return
            self._password = value
            self.dirty_client = True
        return locals()
    password = property(**password())

    @property
    def public_client(self):
        return self._public_client

    @property
    def client(self):
        return self._client

    def create_public_client(self):
        try:
            client = PublicClient(self._server)
        except InvalidClientError:
            self._public_client = None
            raise
        else:
            self._public_client = client
        finally:
            self.dirty_public_client = False

    def create_client(self):
        try:
            client = Client(self._username, self._password, self._server)
        except InvalidClientError:
            self._client = None
            raise
        else:
            self._client = client
        finally:
            self.dirty_client = False


    def update_device(self):
        try:
            self._client.update_device_settings(self._device_id,
                                                type='server',
                                                caption=self._device_name)
        except AttributeError:
            pass
