import socks
import logging
from typing import Optional, Any
from urllib.parse import urlparse

from python_socks import ProxyType
from web3.providers.websocket import WebsocketProvider, DEFAULT_WEBSOCKET_TIMEOUT

from web3_proxy_providers.utils.proxy import PROXY_TYPE_TO_INT_MAP


class WebsocketWithProxyProvider(WebsocketProvider):
    logger = logging.getLogger("web3_proxy_providers.providers.WebsocketWithSocksProxyProvider")

    def __init__(
            self,
            endpoint_uri: str,
            proxy_type: ProxyType,
            proxy_host: str,
            proxy_port: int,
            websocket_kwargs: Optional[Any] = None,
            websocket_timeout: int = DEFAULT_WEBSOCKET_TIMEOUT
    ):
        websocket_kwargs = websocket_kwargs or {}
        netloc = urlparse(endpoint_uri).netloc
        proxy = socks.socksocket()
        proxy.set_proxy(PROXY_TYPE_TO_INT_MAP[proxy_type], proxy_host, proxy_port)
        proxy.connect((netloc, 443))
        websocket_kwargs['sock'] = proxy
        websocket_kwargs['server_hostname'] = netloc
        super().__init__(endpoint_uri, websocket_kwargs, websocket_timeout)
