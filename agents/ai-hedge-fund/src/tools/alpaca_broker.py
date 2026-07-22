import os

from src.backtesting.types import Action, ActionLiteral

# Paper-only for now: no code path here ever targets Alpaca's live trading
# endpoint. Flipping to live money is a deliberate future change, not a
# config flag.
_PAPER = True


def get_alpaca_trading_client():
    """Build an Alpaca paper-trading client from env-var credentials."""
    try:
        from alpaca.trading.client import TradingClient
    except ImportError as e:
        raise ImportError(
            "alpaca-py is required for trade execution. Install it with `poetry add alpaca-py`."
        ) from e

    api_key = os.environ.get("ALPACA_API_KEY")
    secret_key = os.environ.get("ALPACA_SECRET_KEY")
    if not api_key or not secret_key:
        raise RuntimeError(
            "ALPACA_API_KEY and ALPACA_SECRET_KEY must be set to execute trades. "
            "Generate paper trading keys at https://app.alpaca.markets/"
        )

    return TradingClient(api_key, secret_key, paper=_PAPER)


def get_account_state(tickers: list[str]) -> dict:
    """Fetch live (paper) cash and positions, shaped like the CLI's portfolio dict."""
    client = get_alpaca_trading_client()
    account = client.get_account()
    positions_by_symbol = {p.symbol: p for p in client.get_all_positions()}

    positions = {}
    for ticker in tickers:
        position = positions_by_symbol.get(ticker)
        if position is None:
            positions[ticker] = {
                "long": 0,
                "short": 0,
                "long_cost_basis": 0.0,
                "short_cost_basis": 0.0,
                "short_margin_used": 0.0,
            }
            continue

        qty = float(position.qty)
        if qty >= 0:
            positions[ticker] = {
                "long": int(qty),
                "short": 0,
                "long_cost_basis": float(position.avg_entry_price),
                "short_cost_basis": 0.0,
                "short_margin_used": 0.0,
            }
        else:
            positions[ticker] = {
                "long": 0,
                "short": int(-qty),
                "long_cost_basis": 0.0,
                "short_cost_basis": float(position.avg_entry_price),
                "short_margin_used": 0.0,
            }

    return {
        "cash": float(account.cash),
        "margin_requirement": 0.0,
        "margin_used": 0.0,
        "positions": positions,
        "realized_gains": {ticker: {"long": 0.0, "short": 0.0} for ticker in tickers},
    }


class AlpacaTradeExecutor:
    """Submits real (paper) orders to Alpaca. Mirrors TradeExecutor's interface
    from src/backtesting/trader.py so it can be swapped in wherever that is used."""

    def __init__(self):
        self._client = get_alpaca_trading_client()

    def execute_trade(
        self,
        ticker: str,
        action: ActionLiteral,
        quantity: float,
        current_price: float,
        portfolio: dict | None = None,
    ) -> int:
        if quantity is None or quantity <= 0:
            return 0

        try:
            action_enum = Action(action) if not isinstance(action, Action) else action
        except Exception:
            action_enum = Action.HOLD

        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest

        side_by_action = {
            Action.BUY: OrderSide.BUY,
            Action.SELL: OrderSide.SELL,
            Action.SHORT: OrderSide.SELL,
            Action.COVER: OrderSide.BUY,
        }
        side = side_by_action.get(action_enum)
        if side is None:
            return 0

        order_request = MarketOrderRequest(
            symbol=ticker,
            qty=int(quantity),
            side=side,
            time_in_force=TimeInForce.DAY,
        )
        order = self._client.submit_order(order_request)
        print(
            f"[Alpaca paper] {action_enum.value.upper()} {ticker} x{int(quantity)} "
            f"submitted (order id {order.id}, status {order.status})"
        )
        return int(quantity)
