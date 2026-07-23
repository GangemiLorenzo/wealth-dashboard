#!/usr/bin/env python3
"""Cron entrypoint: fetch balances from all sources and store in DB."""
import logging
import os
import httpx

from db import get_conn, init_db, insert_snapshot
from connectors import kraken, ibkr

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
log = logging.getLogger("fetch")

COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"

KRAKEN_TO_CG = {
    # Bitcoin / Ethereum
    "XXBT": "bitcoin", "XBT": "bitcoin",
    "XETH": "ethereum", "ETH": "ethereum",
    # Stablecoins / fiat (price = 1 USD)
    "ZUSD": None, "ZEUR": None, "USDT": None, "USDC": None, "DAI": None,
    # Altcoins
    "SOL": "solana",
    "DOT": "polkadot",
    "ADA": "cardano",
    "ALGO": "algorand",
    "ARB": "arbitrum",
    "AVAX": "avalanche-2",
    "BNB": "binancecoin",
    "CAKE": "pancakeswap-token",
    "CHZ": "chiliz",
    "OP": "optimism",
    "POL": "matic-network",
    "MATIC": "matic-network",
    "WLD": "worldcoin-wld",
    "XETC": "ethereum-classic",
    "ETC": "ethereum-classic",
    "LINK": "chainlink",
    "UNI": "uniswap",
    "AAVE": "aave",
    "ATOM": "cosmos",
    "XRP": "ripple",
    "XXRP": "ripple",
    "LTC": "litecoin",
    "XLTC": "litecoin",
}


def get_crypto_prices(assets: list[str]) -> dict[str, float]:
    ids = [KRAKEN_TO_CG.get(a) for a in assets if KRAKEN_TO_CG.get(a)]
    if not ids:
        return {}
    resp = httpx.get(COINGECKO_URL, params={"ids": ",".join(set(ids)), "vs_currencies": "usd"}, timeout=10)
    resp.raise_for_status()
    return {k: v["usd"] for k, v in resp.json().items()}


def fetch_kraken(conn):
    log.info("Fetching Kraken balances...")
    balances = kraken.get_balances()
    prices = get_crypto_prices(list(balances.keys()))

    rows = []
    for asset, amount in balances.items():
        cg_id = KRAKEN_TO_CG.get(asset)
        price = prices.get(cg_id, 1.0) if cg_id else 1.0
        is_stable = asset in ("ZUSD", "USDT", "USDC", "ZEUR")
        rows.append({
            "asset": asset,
            "amount": amount,
            "value_usd": amount * price if not is_stable else amount,
            "currency": "USD",
        })
    insert_snapshot(conn, "kraken", rows)
    log.info("Kraken: %d assets stored", len(rows))


def fetch_ibkr(conn):
    log.info("Fetching IBKR portfolio...")
    portfolio = ibkr.get_portfolio()

    rows = []
    for pos in portfolio["positions"]:
        rows.append({
            "asset": pos["symbol"],
            "amount": pos["quantity"],
            "value_usd": pos["market_value"],
            "currency": pos["currency"],
        })
    for c in portfolio["cash"]:
        if c["ending_cash"] != 0:
            rows.append({
                "asset": f"CASH_{c['currency']}",
                "amount": c["ending_cash"],
                "value_usd": c["ending_cash"] if c["currency"] == "USD" else None,
                "currency": c["currency"],
            })
    insert_snapshot(conn, "ibkr", rows)
    log.info("IBKR: %d rows stored", len(rows))


def main():
    conn = get_conn()
    init_db(conn)

    errors = []

    if os.environ.get("KRAKEN_API_KEY"):
        try:
            fetch_kraken(conn)
        except Exception as e:
            log.error("Kraken fetch failed: %s", e)
            errors.append(f"kraken: {e}")
    else:
        log.warning("KRAKEN_API_KEY not set, skipping")

    if os.environ.get("IBKR_FLEX_TOKEN"):
        try:
            fetch_ibkr(conn)
        except Exception as e:
            log.error("IBKR fetch failed: %s", e)
            errors.append(f"ibkr: {e}")
    else:
        log.warning("IBKR_FLEX_TOKEN not set, skipping")

    conn.close()

    if errors:
        raise SystemExit(f"Some fetchers failed: {errors}")
    log.info("All fetchers done.")


if __name__ == "__main__":
    main()
