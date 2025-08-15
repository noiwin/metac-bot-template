import argparse
import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Literal
import dotenv
import re
import requests
import traceback
from web3 import Web3

dotenv.load_dotenv()


from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType, PostOrdersArgs
from py_clob_client.order_builder.constants import BUY
from py_clob_client.order_builder.constants import SELL

w3 = Web3(Web3.HTTPProvider("https://polygon-rpc.com"))

host: str = "https://clob.polymarket.com"
key: str = os.getenv("PRIVATE_KEY") 
chain_id: int = 137 
POLYMARKET_PROXY_ADDRESS: str = '0x85e7a315271826653C7708ee13654B1f5C62EBaA'
CTF_ADDRESS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
USDC_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
public_key = "0x49AcE7a854ddcddBeB5BBEF11146a3A5E67a66a8" 
client = ClobClient(host, key=key, chain_id=chain_id, signature_type=2, funder=POLYMARKET_PROXY_ADDRESS)
client.set_api_creds(client.create_or_derive_api_creds()) 

logger = logging.getLogger(__name__)


ctf_abi = [{
    "inputs": [
        {"name": "collateralToken", "type": "address"},
        {"name": "parentCollectionId", "type": "bytes32"},
        {"name": "conditionId", "type": "bytes32"},
        {"name": "partition", "type": "uint256[]"},
        {"name": "amount", "type": "uint256"}
    ],
    "name": "splitPosition",
    "type": "function"}]




BASE = "https://clob.polymarket.com"



BASE = "https://clob.polymarket.com"


import time, re, requests

BASE = "https://clob.polymarket.com"


#L'API gamma et le Clob semblent avoir du mal à extraire des marchés actif, c'est à remédier
def fetch_condition_ids(pattern: str | None = None) -> list[str]:
    r = requests.get(f"{BASE}/simplified-markets", timeout=10)
    r.raise_for_status()
    data = r.json().get("data", [])

    
    def tradable(m):
        a = m.get("active", True)
        acc = m.get("accepting_orders", True) or m.get("acceptingOrders", True)
        return bool(a and acc)

    if pattern:
        rx = re.compile(pattern, re.I)
        def match(m):
            s = m.get("market_slug") or m.get("slug") or m.get("title") or ""
            return rx.search(s)
        data = [m for m in data if match(m) and tradable(m)]
    else:
        data = [m for m in data if tradable(m)]

    return [m["condition_id"] for m in data]

def watch_all(interval: float = 3.0, cooldown_sec: int = 300, pattern: str | None = None, dry_run: bool = False):
   
    next_ok = {}  # condition_id -> timestamp autorisant le prochain essai
    while True:
        t0 = time.time()
        try:
            cids = fetch_condition_ids(pattern=pattern)
            for cid in cids:
                if next_ok.get(cid, 0) > t0:

                    continue
                

                try:
                    res = is_longshort(cid)
                except Exception as e:
                    print(f"[ERR] {cid} -> {repr(e)}")
                    traceback.print_exc()   
                    next_ok[cid] = t0 + 30
                    continue


                
                decision = res[0] if isinstance(res, (list, tuple)) else res
                decision = str(decision).upper()

                if decision in ("LONG", "SHORT"):
                    print(f"[HIT] {decision} on {cid}")
                    #dry_run permet de juste voir les opportunités sans trader
                    if dry_run:
                        print("[DRY RUN] pas d'exécution")
                    next_ok[cid] = t0 + cooldown_sec
                else:
                    # petit délai avant de re-checker ce market
                    next_ok[cid] = t0 + min(cooldown_sec // 6, 60)
        except Exception as e:
            print("[WATCH ERR]", e)

        dt = time.time() - t0
        time.sleep(max(0.0, interval - dt))

# la fonction ci_dessous permet d'obtenir les tokens et leurs id pour une condition de marché binaire donné 
def market_from_condition(condition_id: str):
    r = requests.get(f"{BASE}/markets/{condition_id}", timeout=10)
    r.raise_for_status()
    j = r.json()

    m = None
    if isinstance(j, dict):
        if "tokens" in j and isinstance(j["tokens"], list):
            m = j
        elif isinstance(j.get("market"), dict) and "tokens" in j["market"]:
            m = j["market"]
        elif isinstance(j.get("data"), dict) and "tokens" in j["data"]:
            m = j["data"]

    if m:
        slug = m.get("market_slug") or m.get("slug") or m.get("title", "")
        cond = m.get("condition_id", condition_id)
        return [(slug, cond, t["outcome"], t["token_id"]) for t in m["tokens"]]

    
    s = requests.get(f"{BASE}/simplified-markets", timeout=10)
    s.raise_for_status()
    data = s.json().get("data", [])
    target = next((mm for mm in data if mm.get("condition_id") == condition_id), None)
    if target:
        slug = target.get("market_slug") or target.get("slug") or target.get("title", "")
        cond = target["condition_id"]
        return [(slug, cond, t["outcome"], t["token_id"]) for t in target["tokens"]]

    #Debug si condition est introuvable
    raise ValueError(
        f"condition_id introuvable. /markets payload keys={list(j) if isinstance(j, dict) else type(j)} ; "
        f"simplified not found."
    )


def split_position(condition_id,num_outcomes):



    partition = list(range(1, num_outcomes + 1))
    amount = 1 * 10**6  
    
    ctf_contract = w3.eth.contract(address=CTF_ADDRESS, abi=ctf_abi)
    
    txn = ctf_contract.functions.splitPosition(
        USDC_ADDRESS,           # collateralToken
        "0x" + "00" * 32,      # parentCollectionId (null)
        condition_id,           # conditionId
        partition,              # [1,2,3,...,N]
        amount                  # 1000000 for 1 USDC
    ).build_transaction({
        'from': public_key,
        'gas': 500000,
        'gasPrice': w3.to_wei('30', 'gwei'),
        'nonce': w3.eth.get_transaction_count(public_key)
    })
    
    signed_txn = w3.eth.account.sign_transaction(txn, key)
    return w3.eth.send_raw_transaction(signed_txn.raw_transaction)
     

def onshort_binary(condition_id,num_outcomes,token_yes,token_yes_price,token_no,token_no_price):

    tick = 0

    tx_hash = split_position(condition_id, num_outcomes)
    print("Waiting for splitPosition confirmation..")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    if receipt.status != 1:
        raise Exception("splitPosition transaction failed!")

    print("splitPosition confirmed, posting sell orders...")



    resp = client.post_orders([
    PostOrdersArgs(
    
    order=client.create_order(OrderArgs(
        price=token_yes_price + tick,
        size=1,
        side=SELL,
        token_id=token_yes,
    )),
    orderType=OrderType.FOK, 
),
    PostOrdersArgs(
        
        order=client.create_order(OrderArgs(
            price=token_no_price + tick,
            size=1,
            side=SELL,
            token_id=token_no,
        )),
        orderType=OrderType.FOK,
    )
])
    print(resp)



def onlong_binary(token_yes,token_yes_price,token_no,token_no_price):
        tick = 0
        resp = client.post_orders([
        PostOrdersArgs(
        
        order=client.create_order(OrderArgs(
            price=token_yes_price + tick,
            size=5,
            side=BUY,
            token_id=token_yes,
        )),
        orderType=OrderType.FOK, 
    ),
        PostOrdersArgs(
            
            order=client.create_order(OrderArgs(
                price=token_no_price + tick,
                size=5,
                side=BUY,
                token_id=token_no,
            )),
            orderType=OrderType.FOK,
        )
    ])
        print(resp)
    
def onlong_event(tokens_yes_l):
    tick = 0
    orders = []

    for token_id, price in tokens_yes_l:
        order_args = OrderArgs(
            price=price + tick,
            size=5,
            side=BUY,
            token_id=token_id,
        )
        orders.append(PostOrdersArgs(
            order=client.create_order(order_args),
            orderType=OrderType.FOK
        ))

    resp = client.post_orders(orders)
    print(resp)








#la fonction is_longshort_event vérifie si une opportunité d'arbitrage existe dans un Event ( marché à plusieurs issues ) et trade si c'est le cas
def is_long_short_event(condition_ids):
     
        Event = [market_from_condition(condition) for condition in condition_ids]
        tokens_yes=[Market[0][3] for Market in Event]

        tokens_yes_price_long = [float(client.get_price(token_id=Market[0][3], side="SELL")["price"]) for Market in Event]
        tokens_yes_price_short = [float(client.get_price(token_id=Market[0][3], side="BUY")["price"]) for Market in Event]

        total_short = sum(tokens_yes_price_short)
        total_long = sum(tokens_yes_price_long)

        if total_long <= 0.98:

            tokens_yes_l = list(zip(tokens_yes,tokens_yes_price_long))
            tokens_yes_l.sort(key=lambda x: x[1], reverse=True)
            logger.info("Long strategy is possible")
            onlong_event(tokens_yes_l[:5])
            return "Tradable"
        elif total_short >= 1.02:
            
            tokens_yes_l = list(zip(tokens_yes,tokens_yes_price_short,Event))
            tokens_yes_l.sort(key=lambda x: x[1], reverse=True)
            logger.info("Short strategy is possible")
            #onshort_event(tokens_yes[:5]) 
            return "Tradable"
        else:
            return "NONE"

#la fonction is_longshort_market vérifie si une opportunité d'arbitrage exite dans le cas binaire et trade si c'est le cas
def is_longshort_market(condition_id):
    
    Market=market_from_condition(condition_id)  
    token_yes, token_no = Market[0][3], Market[1][3]

    logger.info(f"{token_yes}")
    logger.info(f"{token_no}")


    token_yes_price_long, token_no_price_long = float(client.get_price(token_id=token_yes,side="SELL")["price"]), float(client.get_price(token_id=token_no,side="SELL")["price"])
    token_yes_price_short, token_no_price_short = float(client.get_price(token_id=token_yes,side="BUY")["price"]), float(client.get_price(token_id=token_no,side="BUY")["price"])

    total_long = token_yes_price_long + token_no_price_long
    total_short = token_yes_price_short + token_no_price_short

    logger.info(f"The long price ares :{token_yes_price_long} and {token_no_price_long} so {total_long}")
    logger.info(f"The short prices are :{token_yes_price_short} and {token_no_price_short} so {total_short}")

    if total_long <= 0.98:
        logger.info("Long strategy is possible")
        onlong_binary(token_yes, token_yes_price_long, token_no, token_no_price_long)
    elif total_short >= 1.02:
        logger.info("Short strategy is possible")
        onshort_binary(condition_id, 2 ,token_yes, token_yes_price_short, token_no, token_no_price_short)
    else:
        logger.info("Impossible de trader")
        return "NONE"


# l'option --islongshort suivi d'un condition permet de trader et checker sur une opportunité, l'option --single_watch permet d'observer en continue et de trader sur un seul marché,
# l'option --watch permet de scanner pleins de marchés différents et de saisir des opportunités et ensuite de trader ( pas encore au point à cause d'un soucis avec l'API Gamma 
# et le Clob qui galèrent à trouver des marchés actifs.)

def main():

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
      
    parser = argparse.ArgumentParser()
    parser.add_argument("condition_id", nargs="?")
    parser.add_argument("--islongshort",action="store_true")
    parser.add_argument("--watch", action="store_true", help="scan en continu tous les markets")
    parser.add_argument("--pattern", default=None, help="regex pour filtrer les marchés (slug/title)")
    parser.add_argument("--dry-run", action="store_true", help="ne pas trader, juste log")
    parser.add_argument("--interval", type=float, default=3.0)
    parser.add_argument("--cooldown", type=int, default=300)
    parser.add_argument("--single_watch",action="store_true")
    args=parser.parse_args()
    if args.islongshort and args.single_watch:
        repeter = "NONE"
        while repeter == "NONE":
             repeter = is_longshort_market(args.condition_id)
    elif args.islongshort:
         is_longshort_market(args.condition_id)
        
    elif args.watch:
        watch_all(interval=args.interval,
                cooldown_sec=args.cooldown,
                pattern=args.pattern,
                dry_run=args.dry_run)
        return


        
if __name__ == "__main__":
      
      main()


        

    

    





