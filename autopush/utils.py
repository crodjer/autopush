import configargparse
import socket

default_ports = {
    "ws": 80,
    "http": 80,
    "wss": 443,
    "https": 443,
}

true_values = ("1", "t", "T", "true", "TRUE", "True")


def str2bool(v):
    return v in true_values


def canonical_url(scheme, hostname, port=None):
    if port is None or port == default_ports.get(scheme):
        return "%s://%s" % (scheme, hostname)
    return "%s://%s:%s" % (scheme, hostname, port)


def resolve_ip(hostname):
    interfaces = socket.getaddrinfo(hostname, 0, socket.AF_INET,
                                    socket.SOCK_STREAM,
                                    socket.IPPROTO_TCP)
    if len(interfaces) == 0:
        return hostname
    addr = interfaces[0][-1]
    return addr[0]


class ArgumentParser(configargparse.ArgumentParser):
    """A subclass of ``configargparse.ArgumentParser`` that allows Booleans to
    be specified in config files."""
    def convert_setting_to_command_line_arg(self, action, key, value):
        if value in true_values:
            return [action.option_strings[-1], value]
        return super(ArgumentParser, self).convert_setting_to_command_line_arg(
            action, key, value)
