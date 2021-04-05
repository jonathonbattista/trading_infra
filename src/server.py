Skip to content
Search or jump to…

Pull requests
Issues
Marketplace
Explore
 
@jonbattista 
jonbattista
/
trading_infra
1
0
0
Code
Issues
Pull requests
Actions
Projects
Wiki
Security
Insights
Settings
trading_infra/src/server.py /
@jonbattista
jonbattista wip
Latest commit 05df577 20 minutes ago
 History
 1 contributor
230 lines (195 sloc)  8.46 KB
  
from flask import Flask, request
import requests
import os
import alpaca_trade_api as tradeapi
import json
from decimal import Decimal
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

app = Flask(__name__)

app.debug = True

@app.route('/', methods=["POST"])


def alpaca():
    data = request.data

    json_data = json.loads(data)
    #print(json_data)
    #print(request.args)

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

    time_in_force_condition = 'time_in_force' not in json_data
    print(time_in_force_condition)
    if time_in_force_condition:
        time_in_force = 'day'
    else:
        time_in_force = json_data['time_in_force']

    order_type_condition = 'type' not in json_data
    print(order_type_condition)
    if order_type_condition:
        order_type = 'limit'
    else:
        order_type = json_data['order_type']

    APCA_API_KEY_ID = request.args.get('APCA_API_KEY_ID')
    APCA_API_SECRET_KEY = request.args.get('APCA_API_SECRET_KEY')
    ticker = json_data['ticker']
    price = json_data['price']
    side = json_data['side']

    print(f'ticker is {ticker}')
    print(f'price is {price}')
    print(f'side is {side}')
    print(f'time_in_force is {time_in_force}')
    print(f'order_type is {order_type}')

    api = tradeapi.REST(APCA_API_KEY_ID, APCA_API_SECRET_KEY, 'https://paper-api.alpaca.markets')

    account = api.get_account()

    if account.trading_blocked:
        return 'Account is currently restricted from trading.', 400
    open_orders = api.list_orders()
    if not open_orders:
        print('No Open Orders found')
    else:
        print(open_orders)
        print(f'{len(open_orders)} Open Orders found!')


    buying_power = Decimal(account.buying_power)
            
    print(f'Buying Power is {buying_power}')
            
    limit_price = Decimal(price) * Decimal('.0.5')

    if buying_power > 0:
        number_of_shares = round(buying_power // limit_price)
        if number_of_shares > 0:
            order = api.submit_order(
                symbol=ticker,
                qty=number_of_shares - 1,
                side=side,
                type=order_type,
                time_in_force=time_in_force,
                limit_price=limit_price
            )
            print(order)
            if order.status == 'accepted':
                return f'Success: Purchase of {number_of_shares} at ${price} was {order.status}'
            else:
                return f'Error: Purchase of {number_of_shares} at ${price} was {order.status}'
        else:
            return f'Error: Not enough Buying Power: ${buying_power} to buy {number_of_shares} at limit price {limit_price}', 200
    
    return f'Error: You have no Buying Power: ${buying_power}', 200

if __name__ == '__main__':
  app.run(host='0.0.0.0', port=8080)
