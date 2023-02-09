import json
import socks
import asyncio
import logging
import inspect
import itertools
from abc import ABC
from typing import (
    Any,
    Callable,
    Tuple,
    Dict,
    Optional,
    Union,
    cast,
)
import websockets
from eth_typing import (
    URI
)

from eth_utils import (
    to_bytes, to_text,
)
from urllib.parse import urlparse

from python_socks import ProxyType
from web3.providers import AsyncBaseProvider
from websockets.legacy.client import WebSocketClientProtocol

from web3_proxy_providers.utils.encoding import (
    FriendlyJsonSerde,
)
from web3.types import (
    RPCEndpoint,
    RPCResponse,
)
from web3.providers.websocket import (
    DEFAULT_WEBSOCKET_TIMEOUT,
    get_default_endpoint,
    RESTRICTED_WEBSOCKET_KWARGS,
)
from web3.exceptions import (
    ValidationError
)

from web3_proxy_providers.utils.proxy import PROXY_TYPE_TO_INT_MAP


# def construct_user_agent(class_name: str) -> str:
#     from web3 import __version__ as web3_version
#
#     user_agent = 'Web3.py/{version}/{class_name}'.format(
#         version=web3_version,
#         class_name=class_name,
#     )
#     return user_agent


# async def async_combine_middlewares(
#     middlewares: Sequence[Middleware],
#     web3: 'Web3',
#     provider_request_fn: Callable[[RPCEndpoint, Any, Callable], Any]
# ) -> Callable[..., RPCResponse]:
#     """
#     Returns a callable function which will call the provider.provider_request
#     function wrapped with all the middlewares.
#     """
#     accumulator_fn = provider_request_fn
#     for middleware in reversed(middlewares):
#         accumulator_fn = await construct_middleware(middleware, accumulator_fn, web3)
#     return accumulator_fn


# # noinspection PyPep8Naming
# class AsyncSubscriptionBaseProvider:
#     _middlewares: Tuple[Middleware, ...] = ()
#     # a tuple of (all_middlewares, request_func)
#     _request_func_cache: Tuple[Tuple[Middleware, ...], Callable[..., RPCResponse]] = (None, None)
#
#     def __init__(self) -> None:
#         warnings.warn(
#             "Async providers are still being developed and refined. Expect breaking changes in minor releases."
#         )
#
#     @property
#     def middlewares(self) -> Tuple[Middleware, ...]:
#         return self._middlewares
#
#     @middlewares.setter
#     def middlewares(
#         self, values: MiddlewareOnion
#     ) -> None:
#         # tuple(values) converts to MiddlewareOnion -> Tuple[Middleware, ...]
#         self._middlewares = tuple(values)  # type: ignore
#
#     async def request_func(
#         self, web3: "Web3", outer_middlewares: MiddlewareOnion
#     ) -> Callable[[RPCEndpoint], Any]:
#         all_middlewares: Tuple[Middleware] = tuple(outer_middlewares) + tuple(self.middlewares)  # type: ignore # noqa: E501
#
#         cache_key = self._request_func_cache[0]
#         if cache_key is None or cache_key != all_middlewares:
#             self._request_func_cache = (
#                 all_middlewares,
#                 await self._generate_request_func(web3, all_middlewares)
#             )
#         return self._request_func_cache[-1]
#
#     async def _generate_request_func(
#         self, web3: "Web3", middlewares: Sequence[Middleware]
#     ) -> Callable[..., RPCResponse]:
#         return await async_combine_middlewares(
#             middlewares=middlewares,
#             web3=web3,
#             provider_request_fn=self.make_request,
#         )
#
#     async def make_request(self, method: RPCEndpoint, params: Any) -> RPCResponse:
#         raise NotImplementedError("Providers must implement this method")
#
#     # async def make_request_async(self, method: RPCEndpoint, params: Any, callback: Callable) -> RPCResponse:
#     #     raise NotImplementedError("Providers must implement this method")
#
#     async def isConnected(self) -> bool:
#         raise NotImplementedError("Providers must implement this method")


class AsyncSubscriptionJSONBaseProvider(AsyncBaseProvider, ABC):
    def __init__(self) -> None:
        super().__init__()
        self.request_counter = itertools.count()

    def encode_rpc_request(self, method: RPCEndpoint, params: Any) -> Tuple[int, bytes]:
        identifier = next(self.request_counter)
        rpc_dict = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or [],
            "id": identifier,
        }
        encoded = FriendlyJsonSerde().json_encode(rpc_dict)
        return identifier, to_bytes(text=encoded)

    async def is_connected(self) -> bool:
        try:
            response = await self.make_request(RPCEndpoint('web3_clientVersion'), [])
        except IOError:
            return False

        assert response['jsonrpc'] == '2.0'
        assert 'error' not in response

        return True


class AsyncSubscriptionWebsocketProvider(AsyncSubscriptionJSONBaseProvider):

    logger = logging.getLogger("web3_proxy_providers.providers.AsyncSubscriptionWebsocketProvider")

    def __init__(
            self,
            loop: asyncio.AbstractEventLoop,
            websocket_endpoint_uri: Optional[Union[URI, str]] = None,
            websocket_kwargs: Optional[Any] = None,
            websocket_timeout: int = DEFAULT_WEBSOCKET_TIMEOUT,
    ) -> None:
        self.websocket_endpoint_uri = URI(websocket_endpoint_uri)
        self.websocket_timeout = websocket_timeout
        if self.websocket_endpoint_uri is None:
            self.websocket_endpoint_uri = get_default_endpoint()
        self.loop = loop
        websocket_kwargs = websocket_kwargs or {}
        found_restricted_keys = set(websocket_kwargs.keys()).intersection(
            RESTRICTED_WEBSOCKET_KWARGS
        )
        if found_restricted_keys:
            raise ValidationError(
                '{0} are not allowed in websocket_kwargs, '
                'found: {1}'.format(RESTRICTED_WEBSOCKET_KWARGS, found_restricted_keys)
            )
        self._websocket_kwargs = websocket_kwargs
        # self.conn = PersistentWebSocket(
        #     self.websocket_endpoint_uri, self.loop, websocket_kwargs
        # )
        self.ws: Optional[WebSocketClientProtocol] = None
        # self._pending_results: Dict[int, Tuple[Callable[[int, Any], Any], Tuple[RPCEndpoint, Any]]] = {}
        self._pending_subscription_callbacks: Dict[str, Callable[[str, Any], Any]] = {}
        self._pending_futures: Dict[int, Any] = {}
        self._initialized = False
        super().__init__()

    def __str__(self) -> str:
        return "WS connection {0}".format(self.websocket_endpoint_uri)

    async def initialize(self):
        self.logger.debug("Initializing")
        self.ws = await websockets.connect(
            uri=self.websocket_endpoint_uri, loop=self.loop, **self._websocket_kwargs
        )
        self.loop.create_task(self._read_websocket_messages())
        self._initialized = True

    async def _read_websocket_messages(self):
        async for message in self.ws:
            self.logger.debug(f"New ws message {message}")
            message_json = json.loads(message)
            message_json_id = message_json.get('id')
            eth_method = message_json.get('method')
            if message_json_id is not None:
                # pending_result = self._pending_results.get(message_json_id)
                pending_future = self._pending_futures.get(message_json_id)
                if pending_future is not None:
                    if message_json.get('error') is not None:
                        self.logger.error(message_json['error'])
                        pending_future.set_result(None)
                    else:
                        message_result = message_json.get('result')
                        if message_result is None:
                            raise Exception(f'No result in response to subscription on request id {message_json_id}: '
                                            f'{message}')

                        pending_future.set_result(message_json)
                else:
                    self.logger.warning(f'Cannot find method callback for response {message}')
            elif eth_method == 'eth_subscription':
                subscription = message_json['params']['subscription']
                subscription_callback = self._pending_subscription_callbacks.get(subscription)
                if subscription_callback is not None:
                    if inspect.iscoroutinefunction(subscription_callback):
                        await subscription_callback(subscription, message_json['params']['result'])
                    else:
                        subscription_callback(subscription, message_json['params']['result'])
                else:
                    self.logger.warning(f'Cannot find subscription callback for {subscription}')
            else:
                self.logger.error(f'Unknown message {message}')

    # noinspection PyMethodMayBeStatic
    def decode_rpc_response(self, raw_response: bytes) -> RPCResponse:
        text_response = to_text(raw_response)
        return cast(RPCResponse, FriendlyJsonSerde().json_decode(text_response))

    async def make_request(self, method: RPCEndpoint, params: Any) -> RPCResponse:
        if self._initialized is False:
            await self.initialize()
        request_id, request_data = self.encode_rpc_request(method, params)
        self.logger.debug("Making request WebSocket. URI: %s, "
                          "Method: %s, request Id: %s", self.websocket_endpoint_uri, method, request_id)

        future = self.loop.create_future()
        self._pending_futures[request_id] = future
        await asyncio.wait_for(
            self.ws.send(request_data),
            timeout=self.websocket_timeout
        )
        result = await future
        return result

    async def subscribe(self, params: Any, callback: Callable[[str, Any], Any]) -> str:
        if self._initialized is False:
            await self.initialize()
        result = await self.make_request(method=RPCEndpoint("eth_subscribe"), params=params)
        subscription_id = result['result']
        self._pending_subscription_callbacks[subscription_id] = callback
        self.logger.debug(f"Subscribed with subscription {subscription_id} to: {params}")
        return subscription_id

    async def unsubscribe(self, subscription_id: str) -> bool:
        if self._initialized is False:
            await self.initialize()
        # noinspection PyTypeChecker
        result = await self.make_request(method="eth_unsubscribe", params=[subscription_id])
        result_success = result['result']
        self.logger.debug(f"Unsubscribed from subscription {subscription_id}, success: {result_success}")
        del self._pending_subscription_callbacks[subscription_id]
        return result_success


class AsyncSubscriptionWebsocketWithProxyProvider(AsyncSubscriptionWebsocketProvider):
    logger = logging.getLogger("web3_proxy_providers.providers.AsyncSubscriptionWebsocketWithProxyProvider")

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
        proxy.set_proxy(PROXY_TYPE_TO_INT_MAP[proxy_type], proxy_host, proxy_port)
        proxy.connect((netloc, 443))
        websocket_kwargs['sock'] = proxy
        websocket_kwargs['server_hostname'] = netloc
        super().__init__(
            loop,
            endpoint_uri,
            websocket_kwargs,
            websocket_timeout
        )
