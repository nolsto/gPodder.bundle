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
        self.client_is_dirty = True
        self.public_client_is_dirty = True
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
            self.client_is_dirty = True
        if name in ('username', 'password', 'server'):
            self.public_client_is_dirty = True
        if name is 'device_name':
            self.update_device()

    def create_public_client(self):
        client = PublicClient(self.server)
        # Plex Framework does not allow varible names preceded by an underscore
        self.public_client_ = client
        self.public_client_is_dirty = False
        return self.public_client_

    def create_client(self):
        client = Client(self.device_id, self.username, self.password,
                        self.server)
        # Plex Framework does not allow varible names preceded by an underscore
        self.client_ = client
        self.client_is_dirty = False
        return self.client_

    def get_or_create_public_client(self):
        client = getattr(self, 'public_client_', None)
        created = False
        if self.public_client_is_dirty:
            client = self.create_public_client()
            created = True
        return (client, created)

    def get_or_create_client(self):
        client = getattr(self, 'client_', None)
        created = False
        if self.client_is_dirty:
            client = self.create_client()
            created = True
            if getattr(self, 'device_updated', False):
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
            updated = self.client_.update_device_settings(
                self.device_id,
                type='server',
                caption=self.device_name
            )
        except:
            updated = False
        if updated:
            self.device_updated = False
        else:
            self.device_updated = True
