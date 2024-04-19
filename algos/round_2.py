from typing import List
import string
import json
from datamodel import UserId, Listing, Observation, Order, OrderDepth, ProsperityEncoder, Symbol, Trade, TradingState
from typing import Any
from math import floor, ceil
import jsonpickle


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

all_products = ["AMETHYSTS", "STARFRUIT", "ORCHIDS"]

position_limits = {
    "AMETHYSTS": 20,
    "STARFRUIT": 20,
    "ORCHIDS": 100,
}

starfruit_coefficients = {
    "intercept": 1.055972221150114,
    "c0": 0.29442524,   
    "c1": 0.20159055,
    "c2": 0.13868933,
    "c3": 0.10046593,
    "c4": 0.09045292,
    "c5": 0.06165871,
    "c6": 0.04568246,
    "c7": 0.01178657,
    "c8": 0.03091662,
    "c9": 0.02412062,
}

class Trader:
    def run(self, state: TradingState):
        # Only method required. It takes all buy and sell orders for all symbols as an input, and outputs a list of orders to be sent
        traderData = {"starfruit_0" : 0,
                      "starfruit_1" : 0,
                      "starfruit_2" : 0,
                      "starfruit_3" : 0, 
                      "starfruit_4" : 0,
                      "starfruit_5" : 0,
                      "starfruit_6" : 0,
                      "starfruit_7" : 0,
                      "starfruit_8" : 0,
                      "starfruit_9" : 0,
                      }
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

                buy_amount = position_limits[product] - state.position[product]
                sell_amount = position_limits[product] + state.position[product]

                half_width = 2

                orders.append(Order(product, fair - half_width, buy_amount))
                orders.append(Order(product, fair + half_width, -sell_amount))
                
                result[product] = orders

            # products that require previous data
            #_______________________________________________________________________________________#

            if state.traderData == None or state.traderData == "":
                continue
            previous_data = jsonpickle.decode(state.traderData)

            if product == "STARFRUIT":
                orders: List[Order] = []

                best_bid, best_bid_amount = list(order_depth.buy_orders.items())[0]
                best_ask, best_ask_amount = list(order_depth.sell_orders.items())[0]
                best_ask_amount = -best_ask_amount # now best_ask_amount is positive
                starfruit_mid = (best_bid + best_ask) / 2

                # update traderData
                traderData["starfruit_0"] = starfruit_mid
                for i in range(1, 10):
                    traderData[f"starfruit_{i}"] = previous_data[f"starfruit_{i - 1}"]

                # skip if traderData is empty
                if traderData["starfruit_9"] == 0:
                    continue

                # fair price is the last mid price
                fair = starfruit_coefficients["intercept"]

                for i in range(0, 10):
                    fair += starfruit_coefficients[f"c{i}"] * traderData[f"starfruit_{i}"]

                taking_width = 0
                making_width = 2

                max_buy_amount = position_limits[product] - state.position[product]
                max_sell_amount = position_limits[product] + state.position[product]

                # market taking algorithm
                if len(order_depth.sell_orders) != 0:
                    best_ask, best_ask_amount = list(order_depth.sell_orders.items())[0]
                    best_ask_amount = -best_ask_amount # now best_ask_amount is positive
                    if int(best_ask) < fair - taking_width:
                        print("BUY", str(best_ask_amount) + "x", best_ask)
                        orders.append(Order(product, best_ask, best_ask_amount))
                        max_buy_amount -= best_ask_amount
        
                if len(order_depth.buy_orders) != 0:
                    best_bid, best_bid_amount = list(order_depth.buy_orders.items())[0]
                    if int(best_bid) > fair + taking_width:
                        print("SELL", str(best_bid_amount) + "x", best_bid)
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

        encoded_trader_data = str(jsonpickle.encode(traderData))
        logger.flush(state, result, conversions, encoded_trader_data)
        return result, conversions, encoded_trader_data