from mygpoclient.api import MygPodderClient as MygpoClient
from mygpoclient.public import PublicClient as MygpoPublicClient


class ClientError(Exception):
    pass

class InvalidClientError(ClientError):
    pass

class InvalidPublicClientError(ClientError):
    pass


class ClientMixin(object):
    """
    docstring for BaseClient
    """
    def __init__(self, *args, **kwargs):
        super(ClientMixin, self).__init__(*args, **kwargs)
        self.validate()

    def validate(self):
        """Attempt a minimal-effort API call to test client viability"""
        raise NotImplementedError()


class Client(ClientMixin, MygpoClient):
    """
    Client for the gpodder.net Simple API
    """
    def __init__(self, device_id, username='', password='', *args, **kwargs):
        self.device_id = device_id
        super(Client, self).__init__(username, password, *args, **kwargs)

    def validate(self):
        try:
            self.get_suggestions(1)
        except Exception:
            raise InvalidClientError()

    def pull_subscriptions(self, *args, **kwargs):
        return super(Client, self).pull_subscriptions(self.device_id,
                                                      *args, **kwargs)

    def update_subscriptions(self, *args, **kwargs):
        return super(Client, self).update_subscriptions(self.device_id,
                                                        *args, **kwargs)


class PublicClient(ClientMixin, MygpoPublicClient):
    """
    Client for the gpodder.net "anonymous" API
    """
    def validate(self):
        try:
            self.get_toplist(1)
        except Exception:
            raise InvalidPublicClientError()


class Session(object):
    def __init__(self, device_id):
        self._client_is_dirty = True
        self._public_client_is_dirty = True
        self.device_id = device_id

    def __setattr__(self, name, value):
        try:
            if value == getattr(self, name):
                return
            else:
                super(Session, self).__setattr__(name, value)
        except AttributeError:
            super(Session, self).__setattr__(name, value)
        if name is 'server':
            self._client_is_dirty = True
        if name in ('username', 'password', 'server'):
            self._public_client_is_dirty = True
        if name is 'device_name':
            self.update_device()

    def create_public_client(self):
        client = PublicClient(self.server)
        self._public_client = client
        self._public_client_is_dirty = False
        return self._public_client

    def create_client(self):
        client = Client(self.device_id, self.username, self.password,
                        self.server)
        self._client = client
        self._client_is_dirty = False
        return self._client

    def get_or_create_public_client(self):
        client = getattr(self, '_public_client', None)
        created = False
        if self._public_client_is_dirty:
            client = self.create_public_client()
            created = True
        return (client, created)

    def get_or_create_client(self):
        client = getattr(self, '_client', None)
        created = False
        if self._client_is_dirty:
            client = self.create_client()
            created = True
            if getattr(self, '_update_device', False):
                # Update device if the `device_name` was changed since a client
                # was created.
                self.update_device()
        return (client, created)

    @property
    def public_client(self):
        return self.get_or_create_public_client()[0]

    @property
    def client(self):
        return self.get_or_create_client()[0]

    def update_device(self):
        try:
            updated = self._client.update_device_settings(
                self.device_id,
                type='server',
                caption=self.device_name
            )
        except:
            updated = False
        if updated:
            self._update_device = False
        else:
            self._update_device = True
