import httpx
import xml.etree.ElementTree as ET
import os
from datetime import date


FLEX_URL = "https://gdcdyn.interactivebrokers.com/Universal/servlet/FlexStatementService.SendRequest"
GET_URL = "https://gdcdyn.interactivebrokers.com/Universal/servlet/FlexStatementService.GetStatement"


def _request_statement(token: str, query_id: str) -> str:
    resp = httpx.get(FLEX_URL, params={"t": token, "q": query_id, "v": "3"}, timeout=30)
    resp.raise_for_status()
    root = ET.fromstring(resp.text)
    status = root.findtext("Status")
    if status != "Success":
        raise RuntimeError(f"IBKR Flex request failed: {root.findtext('ErrorMessage')}")
    return root.findtext("ReferenceCode")


def _get_statement(token: str, reference: str) -> ET.Element:
    import time
    for _ in range(12):
        resp = httpx.get(GET_URL, params={"t": token, "q": reference, "v": "3"}, timeout=30)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
        status = root.findtext("Status")
        if status == "Success":
            return root
        error_code = root.findtext("ErrorCode")
        if status in ("Warn", "Fail") and error_code in ("1001", "1002", "1003"):
            time.sleep(10)
            continue
        raise RuntimeError(f"IBKR Flex error {error_code}: {root.findtext('ErrorMessage')}")
    raise TimeoutError("IBKR Flex statement never became ready")


def get_portfolio() -> dict:
    token = os.environ["IBKR_FLEX_TOKEN"]
    query_id = os.environ["IBKR_FLEX_QUERY_ID"]

    ref = _request_statement(token, query_id)
    root = _get_statement(token, ref)

    positions = []
    for pos in root.iter("OpenPosition"):
        positions.append({
            "symbol": pos.get("symbol"),
            "currency": pos.get("currency"),
            "quantity": float(pos.get("position", 0)),
            "market_value": float(pos.get("markPrice", 0)) * float(pos.get("position", 0)),
            "cost_basis": float(pos.get("costBasisMoney", 0)),
            "unrealized_pnl": float(pos.get("fifoPnlUnrealized", 0)),
        })

    cash = []
    for c in root.iter("CashReport"):
        cash.append({
            "currency": c.get("currency"),
            "ending_cash": float(c.get("endingCash", 0)),
        })

    return {"positions": positions, "cash": cash}
