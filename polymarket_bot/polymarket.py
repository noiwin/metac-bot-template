from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY
from py_clob_client.order_builder.constants import SELL
import os
import dotenv
dotenv.load_dotenv()



host: str = "https://clob.polymarket.com"
key: str = os.getenv("PRIVATE_KEY") #This is your Private Key. Export from reveal.polymarket.com or from your Web3 Application
chain_id: int = 137 #No need to adjust this
POLYMARKET_PROXY_ADDRESS: str = '0x85e7a315271826653C7708ee13654B1f5C62EBaA' #This is the address you deposit/send USDC to to FUND your Polymarket account.

### Initialization of a client using a Polymarket Proxy associated with a Browser Wallet(Metamask, Coinbase Wallet, etc)
client = ClobClient(host, key=key, chain_id=chain_id, signature_type=2, funder=POLYMARKET_PROXY_ADDRESS)

### Initialization of a client that trades directly from an EOA. 
client = ClobClient(host, key=key, chain_id=chain_id)

## Create and sign a limit order buying 100 YES tokens for 0.50c each
#Refer to the Markets API documentation to locate a tokenID: https://docs.polymarket.com/developers/gamma-markets-api/get-markets

client.set_api_creds(client.create_or_derive_api_creds()) 

order_args = OrderArgs(
    price=0.08,
    size=20,
    side=SELL,
    token_id="38482832507373896059392405445307398695828388682440920772765087499999175920422", #Token ID you want to purchase goes here. 
)


signed_order = client.create_order(order_args)

## GTC(Good-Till-Cancelled) Order
resp = client.post_order(signed_order, OrderType.GTC)
print(resp)