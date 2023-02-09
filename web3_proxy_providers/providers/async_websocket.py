import json
import socks
import logging
import asyncio
from eth_typing import URI
from typing import (
    Optional,
    Union,
    Any,
)

from python_socks import ProxyType
from web3.providers.websocket import (
    DEFAULT_WEBSOCKET_TIMEOUT,
    get_default_endpoint,
    RESTRICTED_WEBSOCKET_KWARGS,
    PersistentWebSocket
)
from web3.exceptions import (
    ValidationError
)
from urllib.parse import urlparse
from web3.types import RPCEndpoint, RPCResponse
from web3.providers.async_base import AsyncJSONBaseProvider


def _start_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    asyncio.set_event_loop(loop)
    loop.run_forever()
    loop.close()


class AsyncWebsocketProvider(AsyncJSONBaseProvider):
    logger = logging.getLogger("web3_proxy_providers.providers.AsyncWebsocketProvider")

    def __init__(
            self,
            loop: asyncio.AbstractEventLoop,
            endpoint_uri: Optional[Union[URI, str]] = None,
            websocket_kwargs: Optional[Any] = None,
            websocket_timeout: int = DEFAULT_WEBSOCKET_TIMEOUT,
    ) -> None:
        self.endpoint_uri = URI(endpoint_uri)
        self.websocket_timeout = websocket_timeout
        if self.endpoint_uri is None:
            self.endpoint_uri = get_default_endpoint()
        self.loop = loop
        # if AsyncWebsocketProvider._loop is None:
        #     AsyncWebsocketProvider._loop = _get_threaded_loop()
        if websocket_kwargs is None:
            websocket_kwargs = {}
        else:
            found_restricted_keys = set(websocket_kwargs.keys()).intersection(
                RESTRICTED_WEBSOCKET_KWARGS
            )
            if found_restricted_keys:
                raise ValidationError(
                    '{0} are not allowed in websocket_kwargs, '
                    'found: {1}'.format(RESTRICTED_WEBSOCKET_KWARGS, found_restricted_keys)
                )
        self.conn = PersistentWebSocket(
            self.endpoint_uri, self.loop, websocket_kwargs
        )
        super().__init__()

    def __str__(self) -> str:
        return "WS connection {0}".format(self.endpoint_uri)

    async def coro_make_request(self, request_data: bytes) -> RPCResponse:
        async with self.conn as conn:
            await asyncio.wait_for(
                conn.send(request_data),
                timeout=self.websocket_timeout
            )
            return json.loads(
                await asyncio.wait_for(
                    conn.recv(),
                    timeout=self.websocket_timeout
                )
            )

    async def make_request(self, method: RPCEndpoint, params: Any) -> RPCResponse:
        self.logger.debug("Making request WebSocket. URI: %s, "
                          "Method: %s", self.endpoint_uri, method)
        request_data = self.encode_rpc_request(method, params)
        result = await self.coro_make_request(request_data)
        self.logger.debug("Result for URI: %s, "
                          "Method: %s is %s", self.endpoint_uri, method, result)
        return result


class AsyncWebsocketWithProxyProvider(AsyncWebsocketProvider):
    logger = logging.getLogger("web3_proxy_providers.providers.WebsocketWithHttpProxyProvider")

    def __init__(
            self,
            loop: asyncio.AbstractEventLoop,
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
        proxy.set_proxy(proxy_type, proxy_host, proxy_port)
        proxy.connect((netloc, 443))
        websocket_kwargs['sock'] = proxy
        websocket_kwargs['server_hostname'] = netloc
        super().__init__(loop, endpoint_uri, websocket_kwargs, websocket_timeout)
