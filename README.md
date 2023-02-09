![alt text][pypi_version] ![alt text][licence_version]

# Proxy Providers for Web3Py

A library for connecting to Web3 RPC providers using a proxy

Tested with:
* Python 3.6+

Supports Proxy usage for:
* Http RPC (Sync, Async)
* Websocket RPC (Sync, Async)
* Websocket RPC with subscription (Sync, Async)

Use the following command to install using pip:
```
pip install web3-proxy-providers
```

To use the providers, you need web3 with version above 6.0.0, current version is 6.0.0b9 (beta)

```
pip install web3==6.0.09b
```

## Usage example
### Http Provider with Proxy
Use `HttpWithProxyProvider` class which supports http and socks proxy

```python
from web3 import Web3
from web3_proxy_providers import HttpWithProxyProvider

provider = HttpWithProxyProvider(
    endpoint_uri='https://eth-mainnet.g.alchemy.com/v2/<YourAlchemyKey>',
    proxy_url='socks5h://localhost:1080'
)
web3 = Web3(
    provider=provider,
)
print(web3.eth.block_number)
```

### Async Http Provider with Proxy
Use `AsyncHTTPWithProxyProvider` class to connect to an RPC with asyncio using a proxy. both http proxy and socks proxy are supported

```python
import asyncio
from web3 import Web3
from web3.eth import AsyncEth
from python_socks import ProxyType
from web3_proxy_providers import AsyncHTTPWithProxyProvider

async def main():
    provider = AsyncHTTPWithProxyProvider(
        proxy_type=ProxyType.SOCKS5,
        proxy_host='localhost',
        proxy_port=1080,
        endpoint_uri='https://eth-mainnet.g.alchemy.com/v2/<YourAlchemyKey>',
    )
    web3 = Web3(
        provider=provider,
        modules={'eth': (AsyncEth,)},
    )
    print(await web3.eth.block_number)

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
```

### Async Websocket Provider with Proxy
Use `AsyncWebsocketWithProxyProvider` class to connect to a websocket RPC with asyncio using a proxy. both http proxy and socks proxy are supported

```python
import asyncio
from web3 import Web3
from web3.eth import AsyncEth
from python_socks import ProxyType
from web3_proxy_providers import AsyncWebsocketWithProxyProvider

async def main(loop: asyncio.AbstractEventLoop):
    provider = AsyncWebsocketWithProxyProvider(
        loop=loop,
        proxy_type=ProxyType.SOCKS5,
        proxy_host='localhost',
        proxy_port=1080,
        endpoint_uri='wss://eth-mainnet.g.alchemy.com/v2/<YourAlchemyKey>',
    )
    web3 = Web3(
        provider=provider,
        modules={'eth': (AsyncEth,)},
    )
    print(await web3.eth.block_number)

if __name__ == '__main__':
    async_loop = asyncio.get_event_loop()
    async_loop.run_until_complete(main(loop=async_loop))
```

### Async Websocket Provider with Proxy with Subscription support
Use `AsyncSubscriptionWebsocketWithProxyProvider` class to connect to a websocket RPC with asyncio using a proxy. both http proxy and socks proxy are supported

Learn more about realtime events and eth_subscribe:
* [Ethereum/Geth Docs](https://geth.ethereum.org/docs/interacting-with-geth/rpc/pubsub)
* [Alchemy Docs](https://docs.alchemy.com/reference/eth-subscribe-polygon)


```python
import asyncio
from Crypto.Hash import keccak
from web3 import Web3
from python_socks import ProxyType
from web3_proxy_providers import AsyncSubscriptionWebsocketWithProxyProvider

async def callback(subs_id: str, json_result):
    print(json_result)

async def main(loop: asyncio.AbstractEventLoop):
    provider = AsyncSubscriptionWebsocketWithProxyProvider(
        loop=loop,
        proxy_type=ProxyType.SOCKS5,
        proxy_host='localhost',
        proxy_port=1080,
        endpoint_uri='wss://eth-mainnet.g.alchemy.com/v2/<YourAlchemyKey>',
    )
    
    # subscribe to Deposit and Withdrawal events for WETH contract
    weth_contract_address = Web3.to_checksum_address('0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2')
    deposit_topic = "0x" + keccak.new(data=b'Deposit(address,uint256)', digest_bits=256).hexdigest()
    withdrawal_topic = "0x" + keccak.new(data=b'Withdrawal(address,uint256)', digest_bits=256).hexdigest()
    subscription_id = await provider.subscribe(
        [
            'logs',
            {
                "address": weth_contract_address,
                "topics": [deposit_topic, withdrawal_topic]
            }
        ],
        callback
    )
    print(f'Subscribed with id {subscription_id}')
    
    # unsubscribe after 30 seconds
    await asyncio.sleep(30)
    await provider.unsubscribe(subscription_id)

if __name__ == '__main__':
    async_loop = asyncio.get_event_loop()
    async_loop.run_until_complete(main(loop=async_loop))
```


[pypi_version]: https://img.shields.io/pypi/v/web3-proxy-providers.svg "PYPI version"
[licence_version]: https://img.shields.io/badge/license-MIT%20v2-brightgreen.svg "MIT Licence"
