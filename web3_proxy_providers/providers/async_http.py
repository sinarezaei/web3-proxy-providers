import aiohttp
import logging
from aiohttp_socks import (
    ProxyConnector,
)

from typing import (
    Any,
    Dict,
    Iterable,
    Optional,
    Tuple,
    Union,
)

from eth_typing import (
    URI,
)
from eth_utils import (
    to_dict,
)
from python_socks import ProxyType

from web3._utils.http import (
    construct_user_agent,
)
from web3._utils.request import (
    get_default_http_endpoint,
    DEFAULT_TIMEOUT
)
from web3.types import (
    RPCEndpoint,
    RPCResponse,
)

from web3.providers.async_base import (
    AsyncJSONBaseProvider,
)


class AsyncHTTPWithProxyProvider(AsyncJSONBaseProvider):
    logger = logging.getLogger("web3_proxy_providers.providers.AsyncHTTPWithProxyProvider")
    endpoint_uri = None
    _request_kwargs = None

    def __init__(
            self,
            proxy_type: Optional[ProxyType],
            proxy_host: Optional[str],
            proxy_port: Optional[int],
            endpoint_uri: Optional[Union[URI, str]] = None,
            request_kwargs: Optional[Any] = None
    ) -> None:
        if endpoint_uri is None:
            self.endpoint_uri = get_default_http_endpoint()
        else:
            self.endpoint_uri = URI(endpoint_uri)

        self._request_kwargs = request_kwargs or {}
        if proxy_type is not None:
            connector = ProxyConnector(
                proxy_type=proxy_type,
                host=proxy_host,
                port=proxy_port
            )
        else:
            connector = aiohttp.TCPConnector(ssl=False)
        self.session = aiohttp.ClientSession(connector=connector)

        super().__init__()

    def __str__(self) -> str:
        return "RPC connection {0}".format(self.endpoint_uri)

    @to_dict
    def get_request_kwargs(self) -> Iterable[Tuple[str, Any]]:
        if 'headers' not in self._request_kwargs:
            yield 'headers', self.get_request_headers()
        for key, value in self._request_kwargs.items():
            yield key, value

    def get_request_headers(self) -> Dict[str, str]:
        return {
            'Content-Type': 'application/json',
            'User-Agent': construct_user_agent(str(type(self))),
        }

    async def async_make_post_request(
            self, endpoint_uri: URI, data: bytes, **kwargs: Any
    ) -> bytes:
        kwargs.setdefault("timeout", aiohttp.ClientTimeout(DEFAULT_TIMEOUT))
        # https://github.com/ethereum/go-ethereum/issues/17069
        async with self.session.post(endpoint_uri, data=data, **kwargs) as response:
            return await response.read()

    async def make_request(self, method: RPCEndpoint, params: Any) -> RPCResponse:
        self.logger.debug("Making request HTTP. URI: %s, Method: %s",
                          self.endpoint_uri, method)
        request_data = self.encode_rpc_request(method, params)
        raw_response = await self.async_make_post_request(
            self.endpoint_uri,
            request_data,
            **self.get_request_kwargs()
        )
        response = self.decode_rpc_response(raw_response)
        self.logger.debug("Getting response HTTP. URI: %s, "
                          "Method: %s, Response: %s",
                          self.endpoint_uri, method, response)
        return response
