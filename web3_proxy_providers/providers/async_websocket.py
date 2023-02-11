import json
from types import TracebackType

import socks
import logging
import asyncio
from eth_typing import URI
from typing import (
    Optional,
    Union,
    Any,
    Type, Tuple,
)

from python_socks import ProxyType
from web3.providers.websocket import (
    DEFAULT_WEBSOCKET_TIMEOUT,
    get_default_endpoint,
    RESTRICTED_WEBSOCKET_KWARGS,
)
from web3.exceptions import (
    ValidationError
)
from websockets.legacy.client import (
    WebSocketClientProtocol,
)
import websockets
from urllib.parse import urlparse
from web3.types import RPCEndpoint, RPCResponse
from web3.providers.async_base import AsyncJSONBaseProvider

from web3_proxy_providers.utils.proxy import PROXY_TYPE_TO_INT_MAP


def _start_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    asyncio.set_event_loop(loop)
    loop.run_forever()
    loop.close()


class _ProxySupportingPersistentWebSocket:
    def __init__(
            self,
            endpoint_uri: URI,
            websocket_kwargs: Any,
            proxy: Optional[Tuple[ProxyType, str, int]] = None
    ) -> None:
        self.ws: WebSocketClientProtocol = None
        self.endpoint_uri = endpoint_uri
        self.websocket_kwargs = websocket_kwargs
        self.proxy = proxy

    async def __aenter__(self) -> WebSocketClientProtocol:
        if self.ws is None:
            if self.proxy:
                netloc = urlparse(self.endpoint_uri).netloc
                proxy = socks.socksocket()
                proxy.set_proxy(PROXY_TYPE_TO_INT_MAP[self.proxy[0]], self.proxy[1], self.proxy[2])
                proxy.connect((netloc, 443))
                self.websocket_kwargs['sock'] = proxy
                self.websocket_kwargs['server_hostname'] = netloc
            self.ws = await websockets.connect(uri=self.endpoint_uri, **self.websocket_kwargs)
        return self.ws

    async def __aexit__(
        self,
        exc_type: Type[BaseException],
        exc_val: BaseException,
        exc_tb: TracebackType,
    ) -> None:
        if exc_val is not None:
            try:
                await self.ws.close()
            except Exception:
                pass
            self.ws = None


class AsyncWebsocketProvider(AsyncJSONBaseProvider):
    logger = logging.getLogger("web3_proxy_providers.providers.AsyncWebsocketProvider")

    def __init__(
            self,
            loop: asyncio.AbstractEventLoop,
            endpoint_uri: Optional[Union[URI, str]] = None,
            websocket_kwargs: Optional[Any] = None,
            websocket_timeout: int = DEFAULT_WEBSOCKET_TIMEOUT,
            proxy: Optional[Tuple[ProxyType, str, int]] = None
    ) -> None:
        self.endpoint_uri = URI(endpoint_uri)
        self.websocket_timeout = websocket_timeout
        if self.endpoint_uri is None:
            self.endpoint_uri = get_default_endpoint()
        self.loop = loop
        self.proxy = proxy
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
        self.conn = _ProxySupportingPersistentWebSocket(
            self.endpoint_uri, proxy, websocket_kwargs
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
        super().__init__(loop, endpoint_uri, websocket_kwargs, websocket_timeout, (proxy_type, proxy_host, proxy_port))
