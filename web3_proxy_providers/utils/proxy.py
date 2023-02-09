# noinspection PyPackageRequirements
import socks
from python_socks import ProxyType

PROXY_TYPE_TO_INT_MAP = {
    ProxyType.SOCKS5: socks.SOCKS5,
    ProxyType.SOCKS4: socks.SOCKS4,
    ProxyType.HTTP: socks.HTTP
}

INT_TO_PROXY_TYPE_MAP = {
    socks.SOCKS5: ProxyType.SOCKS5,
    socks.SOCKS4: ProxyType.SOCKS4,
    socks.HTTP: ProxyType.HTTP
}
