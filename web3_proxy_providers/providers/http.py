import requests
from typing import (
    Optional,
    Any
)
from web3 import HTTPProvider


class HttpWithProxyProvider(HTTPProvider):
    # accepts socks or http proxy
    def __init__(
            self,
            endpoint_uri: str,
            proxy_url: Optional[str],
            request_kwargs: Optional[Any] = None,
            session: Optional[Any] = None
    ):
        session = session or requests.Session()
        if proxy_url is not None:
            session.proxies = {
                'http': proxy_url,
                'https': proxy_url,
            }
        super().__init__(
            endpoint_uri=endpoint_uri,
            request_kwargs=request_kwargs,
            session=session
        )
