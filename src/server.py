from flask import Flask, request
import requests
import os
import alpaca_trade_api as tradeapi
from alpaca_trade_api.common import URL
import json
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from waitress import serve
import uuid
import logging
from sys import stdout
import math
import time
from datetime import datetime

# Configure Logging for Docker container
logger = logging.getLogger('mylogger')
logger.setLevel(logging.DEBUG)
logFormatter = logging.Formatter("%(name)-12s %(asctime)s %(levelname)-8s %(filename)s:%(funcName)s %(message)s")
consoleHandler = logging.StreamHandler(stdout)
consoleHandler.setFormatter(logFormatter)
logger.addHandler(consoleHandler)

def watchOrderFilledStatus(ticker, qty, side, order_type, time_in_force, limit_price, order_id, stop):
    time.sleep(10)
    order = get_order_by_client_order_id(order_id)
    count = 0

    while order.status == 'accepted' and count < 2:
        order = get_order_by_client_order_id(order_id)
        api.cancel_order(order_id)

        # Generate new Order ID
        order_id = str(uuid.uuid4())

        # Modify Buy Limit Price by +0.1%
        if side == 'buy':
            new_limit_price = limit_price * 1.001

            new_stop = stop * 1.01

            print(f'Buy Limit Price was changed from {limit_price} to {new_limit_price}')
            print(f'Buy Stop Loss Price was changed from {stop} to {new_stop}')
        # Modify Sell Limit Price by -0.1%
        elif side == 'sell':
            new_limit_price = limit_price * .999

            new_stop = stop * .999

            print(f'Sell Limit Price was changed from {limit_price} to {new_limit_price}')
            print(f'Sell Stop Loss Price was changed from {stop} to {new_stop}')
        
        order = submitOrder(api,ticker, qty, side, order_type, time_in_force, limit_price, order_id, stop)

        time.sleep(10)
        count ++

    if order.status == 'filled' :
        print (f'Success: User: {user} - Order to {side} of {qty} shares of {ticker} at ${limit_price} was {order.status}')
        return f'Success: Order to {side} of {qty} shares of {ticker}  at ${limit_price} was {order.status}', 200
    else:
        print(f'Error: User: {user} - Order to {side} of {qty} shares of {ticker} at ${limit_price} was {order.status}')
        return f'Error: Order to {side} of {qty} shares of {ticker} at ${limit_price} was {order.status}', 500


def submitOrder(api,ticker, qty, side, order_type, time_in_force, limit_price, order_id, stop):
    # Submit Order with Stop Loss
    if stop is not None:
        try:
            order = api.submit_order(
                symbol=ticker,
                qty=qty,
                side=side,
                type=order_type,
                time_in_force=time_in_force,
                limit_price=limit_price,
                client_order_id=order_id,
                order_class='oto',
                stop={'stop_price': stop }
            )
        except tradeapi.rest.APIError as e:
            if e == 'account is not authorized to trade':
                print(f'Error: {e} - Check your API Keys exist')
                return f'Error: {e} - Check your API Keys exist', 500
            else:
                print(e)
                return f'{e}', 500
    # Submit Order without Stop Loss
    else:
        try:
            order = api.submit_order(
                symbol=ticker,
                qty=qty,
                side=side,
                type=order_type,
                time_in_force=time_in_force,
                limit_price=limit_price,
                client_order_id=order_id
            )
        except tradeapi.rest.APIError as e:
            if e == 'account is not authorized to trade':
                print(f'Error: {e} - Check your API Keys exist')
                return f'Error: {e} - Check your API Keys exist', 500
            else:
                print(e)
                return f'{e}', 500
    return order.status

app = Flask(__name__)

app.debug = True

@app.route('/', methods=["POST"])

def alpaca():
    now = datetime.now()
    market_open = now.replace(hour=13, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=20, minute=0, second=0, microsecond=0)

    if now < market_open or now > market_close:
        print(f"Market is Closed - {time.strftime('%l:%M %p')}")
        return f"Market is Closed - {time.strftime('%l:%M %p')}", 404

    APCA_API_KEY_ID = request.args.get('APCA_API_KEY_ID')
    APCA_API_SECRET_KEY = request.args.get('APCA_API_SECRET_KEY')
    user = APCA_API_KEY_ID

    print('\n\n')
    print(f'User is {user}')

    data = request.get_data()

    print(f'Data: {data}')

    if(request.data):
        try:
            json_data = json.loads(data)
        except json.decoder.JSONDecodeError as e:
            print(f'Error parsing JSON: {e}')
            return f'Error parsing JSON: {e}', 500

        if request.args.get('APCA_API_KEY_ID') is None:
            return 'APCA_API_KEY_ID is not set!', 400
        if request.args.get('APCA_API_SECRET_KEY') is None:
            return 'APCA_API_SECRET_KEY is not set!', 400
        if json_data['ticker'] is None:
            return 'ticker is not set!', 400
        if json_data['price'] is None:
            return 'price is not set!', 400
        if json_data['side'] is None:
            return 'side is not set!', 400

        ticker = json_data['ticker']
        price = json_data['price']
        side = json_data['side']
        if side == 'buy':
            limit_price = round(float(price) * float('0.995'),2)
            diff = round(abs(limit_price - price),2)
            print(f'Buying Limit Price is: ${price} + ${diff} = ${limit_price}')
        elif side == 'sell':
            limit_price = round(abs(float(price) * float('1.005')),2)
            diff = round(abs(limit_price - price),2)
            print(f'Selling Limit Price is: ${price} + ${diff} = ${limit_price}')

        # Check if Live or Paper Trading
        if APCA_API_KEY_ID[0:2] == 'PK':
            api = tradeapi.REST(APCA_API_KEY_ID, APCA_API_SECRET_KEY, 'https://paper-api.alpaca.markets')
            #wss_url = 'wss://paper-api.alpaca.markets/stream'
            print('Using Paper Trading API')
        elif APCA_API_KEY_ID[0:2] == 'AK':
            api = tradeapi.REST(APCA_API_KEY_ID, APCA_API_SECRET_KEY, 'https://api.alpaca.markets')
            #wss_url = 'wss://api.alpaca.markets/stream'
            print('Using Live Trading API')
        else:
            return 'Error: API Key is malformed.', 500

        # Get Account information
        account = api.get_account()

        # Get available Buying Power
        buying_power = float(account.buying_power)       
        print(f'Buying Power is ${buying_power}')

        # Get Time-In-Force
        time_in_force_condition = 'time_in_force' not in json_data
        if time_in_force_condition:
            time_in_force = 'day'
        else:
            time_in_force = json_data['time_in_force']

        # Get Order Type
        order_type_condition = 'type' not in json_data
        if order_type_condition:
            order_type = 'limit'
        else:
            order_type = json_data['order_type']

        # Get Quantity
        if 'qty' not in json_data:
            qty = math.floor(buying_power // limit_price)
        else:
            qty = json_data['qty']

        # Get Stop Loss
        if 'stop' not in json_data:
            print('Not using a Stop Loss!')
        else:
            stop = json_data['stop'] - (stop * 0.01)

        # Prin Variables
        print(f'Ticker is {ticker}')
        print(f'Original Price is {price}')
        print(f'Side is {side}')
        print(f'Time-In-Force is {time_in_force}')
        print(f'Order Type is {order_type}')
        print(f'Quantity is {qty}')
        print(f'Stop Loss is {stop}')

        # Check if Account is Blocked
        if account.trading_blocked:
            return 'Account is currently restricted from trading.', 400
        open_orders = api.list_orders()

        # Check if there are any open orders
        if not open_orders:
            print('No Open Orders found')
        else:
            print(f'{len(open_orders)} Open Orders were found!')

        # Generate Order ID
        order_id = str(uuid.uuid4())

        # Get Positions
        portfolio = api.list_positions()

        # Check if there is already a Position for Ticker
        if ticker in portfolio:
            print(f'Error: User: {user} - You already have an Open Position in {ticker}')
            return f'Error: You already have an Open Position in {ticker}', 500

        # Order Flow
        if buying_power > 0:
            print(f'buying power check {math.floor(buying_power // qty > 0)}')
            if qty > 0 and math.floor(buying_power // qty > 0):
                
                order_status = submitOrder(api,ticker, qty, side, order_type, time_in_force, limit_price, order_id, stop)

                print(order_status)
                if order_status == 'accepted':
                    print (f'Pending: User: {user} - Order to {side} of {qty} shares of {ticker} at ${limit_price} was {order.status}')

                    # Check that order if filled
                    watchOrderFilledStatus(ticker, qty, side, order_type, time_in_force, limit_price, order_id, stop)
                else:
                    print(f'Error: User: {user} - Order to {side} of {qty} shares of {ticker} at ${limit_price} was {order.status}')
                    return f'Error: Order to {side} of {qty} shares of {ticker} at ${limit_price} was {order.status}', 500

            else:
                print(f'Error: User: {user} - Not enough Buying Power (${buying_power}) to buy {ticker} at limit price ${limit_price}')
                return f'Error: Not enough Buying Power (${buying_power}) to buy {ticker} at limit price ${limit_price}', 500
        print(f'Error: User: {user} - You have no Buying Power: ${buying_power}')
        return f'Error: You have no Buying Power: ${buying_power}', 500
    else:
        print(f'Error: User {user} - Data Payload was empty!')
        return f'Error: User {user} - Data Payload was empty!', 500 

if __name__ == '__main__':
    serve(app, host="0.0.0.0", port=8080)
