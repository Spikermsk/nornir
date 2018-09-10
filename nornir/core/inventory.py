import getpass
from collections import Mapping
from typing import Any, Dict, Optional

from nornir.core.configuration import Config
from nornir.core.connections import Connections
from nornir.core.exceptions import ConnectionAlreadyOpen, ConnectionNotOpen


VarsDict = Dict[str, Any]
HostsDict = Dict[str, VarsDict]
GroupsDict = Dict[str, VarsDict]


class Host(object):
    """
    Represents a host.

    Arguments:
        name (str): Name of the host
        group (:obj:`Group`, optional): Group the host belongs to
        nornir (:obj:`nornir.core.Nornir`): Reference to the parent nornir object
        **kwargs: Host data

    Attributes:
        name (str): Name of the host
        groups (list of :obj:`Group`): Groups the host belongs to
        defaults (``dict``): Default values for host/group data
        data (dict): data about the device
        connections (``dict``): Already established connections

    Note:

        You can access the host data in two ways:

        1. Via the ``data`` attribute - In this case you will get access
           **only** to the data that belongs to the host.
           2. Via the host itself as a dict - :obj:`Host` behaves like a
           dict. The difference between accessing data via the ``data`` attribute
           and directly via the host itself is that the latter will also
           return the data if it's available via a parent :obj:`Group`.

        For instance::

            ---
            # hosts
            my_host:
                ip: 1.2.3.4
                groups: [bma]

            ---
            # groups
            bma:
                site: bma

            defaults:
                domain: acme.com

        * ``my_host.data["ip"]`` will return ``1.2.3.4``
        * ``my_host["ip"]`` will return ``1.2.3.4``
        * ``my_host.data["site"]`` will ``fail``
        * ``my_host["site"]`` will return ``bma``
        * ``my_host.data["domain"]`` will ``fail``
        * ``my_host.group.data["domain"]`` will ``fail``
        * ``my_host["domain"]`` will return ``acme.com``
        * ``my_host.group["domain"]`` will return ``acme.com``
        * ``my_host.group.group.data["domain"]`` will return ``acme.com``
    """

    def __init__(self, name, groups=None, nornir=None, defaults=None, **kwargs):
        self.nornir = nornir
        self.name = name
        self.groups = groups if groups is not None else []
        self.data = {}
        self.data["name"] = name
        self.connections = Connections()
        self.defaults = defaults if defaults is not None else {}

        if len(self.groups):
            if isinstance(groups[0], str):
                self.data["groups"] = groups
            else:
                self.data["groups"] = [g.name for g in groups]

        for k, v in kwargs.items():
            self.data[k] = v

    def _resolve_data(self):
        processed = []
        result = {}
        for k, v in self.data.items():
            processed.append(k)
            result[k] = v
        for g in self.groups:
            for k, v in g.items():
                if k not in processed:
                    processed.append(k)
                    result[k] = v
        for k, v in self.defaults.items():
            if k not in processed:
                processed.append(k)
                result[k] = v
        return result

    def keys(self):
        """Returns the keys of the attribute ``data`` and of the parent(s) groups."""
        return self._resolve_data().keys()

    def values(self):
        """Returns the values of the attribute ``data`` and of the parent(s) groups."""
        return self._resolve_data().values()

    def items(self):
        """
        Returns all the data accessible from a device, including
        the one inherited from parent groups
        """
        return self._resolve_data().items()

    def to_dict(self):
        """ Return a dictionary representing the object. """
        return self.data

    def has_parent_group(self, group):
        """Retuns whether the object is a child of the :obj:`Group` ``group``"""
        if isinstance(group, str):
            return self._has_parent_group_by_name(group)

        else:
            return self._has_parent_group_by_object(group)

    def _has_parent_group_by_name(self, group):
        for g in self.groups:
            if g.name == group or g.has_parent_group(group):
                return True

    def _has_parent_group_by_object(self, group):
        for g in self.groups:
            if g is group or g.has_parent_group(group):
                return True

    def __getitem__(self, item):
        try:
            return self.data[item]

        except KeyError:
            for g in self.groups:
                r = g.get(item)
                if r:
                    return r

            r = self.defaults.get(item)
            if r:
                return r

            raise

    def __setitem__(self, item, value):
        self.data[item] = value

    def __len__(self):
        return len(self.keys())

    def __iter__(self):
        return self.data.__iter__()

    def __str__(self):
        return self.name

    def __repr__(self):
        return "{}: {}".format(self.__class__.__name__, self.name)

    def get(self, item, default=None):
        """
        Returns the value ``item`` from the host or hosts group variables.

        Arguments:
            item(``str``): The variable to get
            default(``any``): Return value if item not found
        """
        try:
            return self.__getitem__(item)

        except KeyError:
            return default

    @property
    def nornir(self):
        """Reference to the parent :obj:`nornir.core.Nornir` object"""
        return self._nornir

    @nornir.setter
    def nornir(self, value):
        # If it's already set we don't want to set it again
        # because we may lose valuable information
        if not getattr(self, "_nornir", None):
            self._nornir = value

    @property
    def hostname(self):
        """String used to connect to the device. Either ``hostname`` or ``self.name``"""
        return self.get("hostname", self.name)

    @hostname.setter
    def hostname(self, value):
        self.data["hostname"] = value

    @property
    def port(self):
        """Either ``port`` or ``None``."""
        return self.get("port")

    @port.setter
    def port(self, value):
        self.data["port"] = value

    @property
    def username(self):
        """Either ``username`` or user running the script."""
        return self.get("username", getpass.getuser())

    @username.setter
    def username(self, value):
        self.data["username"] = value

    @property
    def password(self):
        """Either ``password`` or empty string."""
        return self.get("password", "")

    @password.setter
    def password(self, value):
        self.data["password"] = value

    @property
    def platform(self):
        """OS the device is running. Defaults to ``platform``."""
        return self.get("platform")

    @platform.setter
    def platform(self, value):
        self.data["platform"] = value

    def get_connection_parameters(
        self, conn_name: Optional[str] = None
    ) -> Dict[str, Any]:
        if not conn_name:
            return {
                "hostname": self.hostname,
                "port": self.port,
                "username": self.username,
                "password": self.password,
                "platform": self.platform,
                "connection_options": {},
            }
        else:
            conn_params = self.get(f"{conn_name}_options", {})
            return {
                "hostname": conn_params.get("hostname", self.hostname),
                "port": conn_params.get("port", self.port),
                "username": conn_params.get("username", self.username),
                "password": conn_params.get("password", self.password),
                "platform": conn_params.get("platform", self.platform),
                "plugin": conn_params.get("plugin"),
                "connection_options": conn_params.get("connection_options", {}),
            }

    def get_connection(self, name: str) -> Any:
        """
        The function of this method is twofold:

            1. If an existing connection is already established for the given type return it
            2. If none exists, establish a new connection of that type with default parameters
               and return it

        Raises:
            AttributeError: if it's unknown how to establish a connection for the given type

        Arguments:
            name: Name of the connection, for instance, netmiko, paramiko, napalm...

        Returns:
            An already established connection
        """
        if self.nornir:
            config = self.nornir.config
        else:
            config = None
        if name not in self.connections:
            self.open_connection(
                name, **self.get_connection_parameters(name), configuration=config
            )
        return self.connections[name].connection

    def get_connection_state(self, name: str) -> Dict[str, Any]:
        """
        For an already established connection return its state.
        """
        if name not in self.connections:
            raise ConnectionNotOpen(name)

        return self.connections[name].state

    def open_connection(
        self,
        name: str,
        plugin: Optional[str] = None,
        hostname: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        port: Optional[int] = None,
        platform: Optional[str] = None,
        connection_options: Optional[Dict[str, Any]] = None,
        configuration: Optional[Config] = None,
        default_to_host_attributes: bool = True,
    ) -> None:
        """
        Open a new connection.

        If ``default_to_host_attributes`` is set to ``True`` arguments will default to host
        attributes if not specified.

        Raises:
            AttributeError: if it's unknown how to establish a connection for the given type

        Returns:
            An already established connection
        """
        if plugin is None:
            plugin = name

        if name in self.connections:
            raise ConnectionAlreadyOpen(name)

        self.connections[name] = self.connections.get_plugin(plugin)()
        if default_to_host_attributes:
            conn_params = self.get_connection_parameters(name)
            self.connections[name].open(
                hostname=hostname if hostname is not None else conn_params["hostname"],
                username=username if username is not None else conn_params["username"],
                password=password if password is not None else conn_params["password"],
                port=port if port is not None else conn_params["port"],
                platform=platform if platform is not None else conn_params["platform"],
                connection_options=connection_options
                if connection_options is not None
                else conn_params["connection_options"],
                configuration=configuration
                if configuration is not None
                else self.nornir.config,
            )
        else:
            self.connections[name].open(
                hostname=hostname,
                username=username,
                password=password,
                port=port,
                platform=platform,
                connection_options=connection_options,
                configuration=configuration,
            )
        return self.connections[name]

    def close_connection(self, name: str) -> None:
        """ Close the connection"""
        if name not in self.connections:
            raise ConnectionNotOpen(name)

        self.connections.pop(name).close()

    def close_connections(self) -> None:
        # Decouple deleting dictionary elements from iterating over connections dict
        existing_conns = list(self.connections.keys())
        for connection in existing_conns:
            self.close_connection(connection)


class Group(Host):
    """Same as :obj:`Host`"""

    def children(self):
        return {
            n: h
            for n, h in self.nornir.inventory.hosts.items()
            if h.has_parent_group(self)
        }


class Inventory(object):
    """
    An inventory contains information about hosts and groups.

    Arguments:
        hosts (dict): keys are hostnames and values are either :obj:`Host` or a dict
            representing the host data.
        groups (dict): keys are group names and values are either :obj:`Group` or a dict
            representing the group data.
        transform_function (callable): we will call this function for each host. This is useful
            to manipulate host data and make it more consumable.

    Attributes:
        hosts (dict): keys are hostnames and values are :obj:`Host`.
        groups (dict): keys are group names and the values are :obj:`Group`.
    """

    def __init__(
        self, hosts, groups=None, defaults=None, transform_function=None, nornir=None
    ):
        self._nornir = nornir

        self.defaults = defaults or {}

        self.groups: Dict[str, Group] = {}
        if groups is not None:
            for group_name, group_details in groups.items():
                if group_details is None:
                    group = Group(name=group_name, nornir=nornir)
                elif isinstance(group_details, Mapping):
                    group = Group(name=group_name, nornir=nornir, **group_details)
                elif isinstance(group_details, Group):
                    group = group_details
                else:
                    raise ValueError(
                        f"Parsing group {group_name}: "
                        f"expected dict or Group object, "
                        f"got {type(group_details)} instead"
                    )

                self.groups[group_name] = group

        for group in self.groups.values():
            group.groups = self._resolve_groups(group.groups)

        self.hosts = {}
        for n, h in hosts.items():
            if isinstance(h, Mapping):
                h = Host(name=n, nornir=nornir, defaults=self.defaults, **h)

            if transform_function:
                transform_function(h)

            h.groups = self._resolve_groups(h.groups)
            self.hosts[n] = h

    def _resolve_groups(self, groups):
        r = []
        if len(groups):
            if not isinstance(groups[0], Group):
                r = [self.groups[g] for g in groups]
            else:
                r = groups
        return r

    def filter(self, filter_obj=None, filter_func=None, *args, **kwargs):
        """
        Returns a new inventory after filtering the hosts by matching the data passed to the
        function. For instance, assume an inventory with::

            ---
            host1:
                site: bma
                role: http
            host2:
                site: cmh
                role: http
            host3:
                site: bma
                role: db

        * ``my_inventory.filter(site="bma")`` will result in ``host1`` and ``host3``
        * ``my_inventory.filter(site="bma", role="db")`` will result in ``host3`` only

        Arguments:
            filter_obj (:obj:nornir.core.filter.F): Filter object to run
            filter_func (callable): if filter_func is passed it will be called against each
              device. If the call returns ``True`` the device will be kept in the inventory
        """
        filter_func = filter_obj or filter_func
        if filter_func:
            filtered = {n: h for n, h in self.hosts.items() if filter_func(h, **kwargs)}
        else:
            filtered = {
                n: h
                for n, h in self.hosts.items()
                if all(h.get(k) == v for k, v in kwargs.items())
            }
        return Inventory(hosts=filtered, groups=self.groups, nornir=self.nornir)

    def __len__(self):
        return self.hosts.__len__()

    @property
    def nornir(self):
        """Reference to the parent :obj:`nornir.core.Nornir` object"""
        return self._nornir

    @nornir.setter
    def nornir(self, value):
        if not getattr(self, "_nornir", None):
            self._nornir = value

        for h in self.hosts.values():
            h.nornir = value

        for g in self.groups.values():
            g.nornir = value

    def to_dict(self):
        """ Return a dictionary representing the object. """
        groups = {k: v.to_dict() for k, v in self.groups.items()}
        groups["defaults"] = self.defaults
        return {
            "hosts": {k: v.to_dict() for k, v in self.hosts.items()},
            "groups": groups,
        }
