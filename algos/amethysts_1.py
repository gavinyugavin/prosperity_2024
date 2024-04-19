from typing import List
import string
import json
from datamodel import UserId, Listing, Observation, Order, OrderDepth, ProsperityEncoder, Symbol, Trade, TradingState
from typing import Any
from math import floor, ceil

# https://jmerle.github.io/imc-prosperity-2-visualizer/

class Logger:
    def __init__(self) -> None:
        self.logs = ""
        self.max_log_length = 3750

    def print(self, *objects: Any, sep: str = " ", end: str = "\n") -> None:
        self.logs += sep.join(map(str, objects)) + end

    def flush(self, state: TradingState, orders: dict[Symbol, list[Order]], conversions: int, trader_data: str) -> None:
        base_length = len(self.to_json([
            self.compress_state(state, ""),
            self.compress_orders(orders),
            conversions,
            "",
            "",
        ]))

        # We truncate state.traderData, trader_data, and self.logs to the same max. length to fit the log limit
        max_item_length = (self.max_log_length - base_length) // 3

        print(self.to_json([
            self.compress_state(state, self.truncate(state.traderData, max_item_length)),
            self.compress_orders(orders),
            conversions,
            self.truncate(trader_data, max_item_length),
            self.truncate(self.logs, max_item_length),
        ]))

        self.logs = ""

    def compress_state(self, state: TradingState, trader_data: str) -> list[Any]:
        return [
            state.timestamp,
            trader_data,
            self.compress_listings(state.listings),
            self.compress_order_depths(state.order_depths),
            self.compress_trades(state.own_trades),
            self.compress_trades(state.market_trades),
            state.position,
            self.compress_observations(state.observations),
        ]

    def compress_listings(self, listings: dict[Symbol, Listing]) -> list[list[Any]]:
        compressed = []
        for listing in listings.values():
            compressed.append([listing["symbol"], listing["product"], listing["denomination"]])

        return compressed

    def compress_order_depths(self, order_depths: dict[Symbol, OrderDepth]) -> dict[Symbol, list[Any]]:
        compressed = {}
        for symbol, order_depth in order_depths.items():
            compressed[symbol] = [order_depth.buy_orders, order_depth.sell_orders]

        return compressed

    def compress_trades(self, trades: dict[Symbol, list[Trade]]) -> list[list[Any]]:
        compressed = []
        for arr in trades.values():
            for trade in arr:
                compressed.append([
                    trade.symbol,
                    trade.price,
                    trade.quantity,
                    trade.buyer,
                    trade.seller,
                    trade.timestamp,
                ])

        return compressed

    def compress_observations(self, observations: Observation) -> list[Any]:
        conversion_observations = {}
        for product, observation in observations.conversionObservations.items():
            conversion_observations[product] = [
                observation.bidPrice,
                observation.askPrice,
                observation.transportFees,
                observation.exportTariff,
                observation.importTariff,
                observation.sunlight,
                observation.humidity,
            ]

        return [observations.plainValueObservations, conversion_observations]

    def compress_orders(self, orders: dict[Symbol, list[Order]]) -> list[list[Any]]:
        compressed = []
        for arr in orders.values():
            for order in arr:
                compressed.append([order.symbol, order.price, order.quantity])

        return compressed

    def to_json(self, value: Any) -> str:
        return json.dumps(value, cls=ProsperityEncoder, separators=(",", ":"))

    def truncate(self, value: str, max_length: int) -> str:
        if len(value) <= max_length:
            return value

        return value[:max_length - 3] + "..."

logger = Logger()

all_products = ["AMETHYSTS", "STARFRUIT"]

position_limits = {
    "AMETHYSTS": 20,
    "STARFRUIT": 20,
}

class Trader:
    def run(self, state: TradingState):
        # Only method required. It takes all buy and sell orders for all symbols as an input, and outputs a list of orders to be sent
        traderData = ""
        conversions = 1

        for product in all_products:
            if product not in state.position:
                state.position[product] = 0

        result = {}
        for product in state.order_depths:
            order_depth: OrderDepth = state.order_depths[product]
            if product == "AMETHYSTS":
                orders: List[Order] = []

                fair = 10000;  # Participant should calculate this value

                max_buy_amount = position_limits[product] - state.position[product]
                max_sell_amount = position_limits[product] + state.position[product]

                taking_width = 2
                making_width = 2

                # market taking algorithm
                # orders.append(Order(product, fair - half_width, buy_amount))
                # orders.append(Order(product, fair + half_width, -sell_amount))

                if len(order_depth.sell_orders) != 0:
                    best_ask, best_ask_amount = list(order_depth.sell_orders.items())[0]
                    best_ask_amount = -best_ask_amount # now best_ask_amount is positive
                    if int(best_ask) < fair - taking_width:
                        orders.append(Order(product, best_ask, best_ask_amount))
                        max_buy_amount -= best_ask_amount

                if len(order_depth.buy_orders) != 0:
                    best_bid, best_bid_amount = list(order_depth.buy_orders.items())[0]
                    if int(best_bid) > fair + taking_width:
                        orders.append(Order(product, best_bid, -best_bid_amount))
                        max_sell_amount -= best_bid_amount

                # market making algorithm
                if max_buy_amount > 0:
                    bid_price = int(floor(fair - making_width))
                    orders.append(Order(product, bid_price, max_buy_amount))
                if max_sell_amount > 0:
                    ask_price = int(ceil(fair + making_width))
                    orders.append(Order(product, ask_price, -max_sell_amount))
                
                result[product] = orders
                
        

        logger.flush(state, result, conversions, traderData)
        return result, conversions, traderData