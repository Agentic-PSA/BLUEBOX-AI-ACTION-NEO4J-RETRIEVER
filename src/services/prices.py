import os

import requests

from src import Neo4jConnector

class Prices:
    def __init__(self):
        self.neo4j = Neo4jConnector()
        self.exchange_rates = {}
        self.prices_headers = {
            "accept": "application/json",
            "CustomerId": os.environ.get("ACTION_API_CUSTOMER_ID"),
            "UserName": "neo",
            "ActionApiKey": os.environ.get("ACTION_API_KEY")
             }

    def get_all_prices(self, currency: str = "PLN") -> list:
        print("services prices get_all_prices")
        url = f"https://api.action.pl/api/ade/v2/Product/GetAll?Language=Polish&Currency={currency}"

        response = requests.get(url, headers=self.prices_headers)
        return response.json().get("data", [])

    def actualize_prices(self, limit=None):
        print("services prices actualize_prices")
        prices = self.get_all_prices(currency="PLN")
        if limit:
            prices = prices[:limit]
        for item in prices:
            self.actualize_price(item)
            price = item.get("price")
            action_code = item.get("productId")
            ean = item.get("ean")
            quantity = item.get("quantity")
            print(ean, action_code, price)

    def actualize_price(self, item):
        print("services prices actualize_price")
        price = item.get("price")
        action_code = item.get("productId")
        quantity = item.get("quantity")
        currency = item.get("currency")
        price_response = self.neo4j.get_product_price(action_code, currency)
        try:
            if not price_response:
                print(f"No product for action code {action_code}")
            elif not price_response[3]:
                print(f"Product {action_code} has no price, creating new price node")
                res = self.neo4j.create_product_price(action_code, price, currency, quantity)
                print(res)
            else:
                price_node = price_response[3]
                if price_node.get('value', -1) == price:
                    print(f"Price for product {action_code} is already up to date")
                else:
                    print(f"Product {action_code} already has a price, updating it")
                    res = self.neo4j.update_price_value(price_node.element_id, price)
                    print(res)
                print(price_response)
        except IndexError:
            print(f"Error receiving product for action code {action_code}")

    def get_exchangerates(self):
        print("services prices get_exchangerates")
        currencies = ["USD", "EUR"]
        for currency in currencies:
            url = f"https://api.nbp.pl/api/exchangerates/rates/A/{currency}/"
            response = requests.get(url, headers={"accept": "application/json"})
            rate = response.json().get("rates", [{}])[0].get("mid", -1)
            self.exchange_rates[currency] = rate
            print(f"{currency} rate: {rate}")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    print(os.environ.get("NEO4J_PORT"))

    prices = Prices()
    prices.actualize_prices()

    # prices.get_exchangerates()