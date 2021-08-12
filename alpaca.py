import logging
import alpaca_trade_api as tradeapi
from discord import Webhook, RequestsWebhookAdapter
from sys import stdout
import math
import time

log = logging.getLogger()
log.setLevel(logging.DEBUG)
log.propagate = False
formatter = logging.Formatter('[%(asctime)s] %(pathname)s:%(lineno)d %(levelname)s - %(message)s','%m-%d %H:%M:%S')
consoleHandler = logging.StreamHandler(stdout)
consoleHandler.setFormatter(formatter)
log.addHandler(consoleHandler)

def sendDiscordMessage(message):
	url = "https://discord.com/api/webhooks/831890918796820510/OWR1HucrnJzHdTE-vASdf5EIbPC1axPikD4D5lh0VBn413nARUW4mla3xPjZHWCK9-9P"
	debug_url = "https://discord.com/api/webhooks/832603152330784819/yA1ZK7ymT3XBU0fJtg0cKZ9RNMPS0C9h0IDABmZZd_KIquToIODOSVOJ6k2aJQSrwC8I"
	webhook = Webhook.from_url(url, adapter=RequestsWebhookAdapter())

	if message is None:
		log.warning('Error: Discord Message is empty!')
	elif 'Error' in message:
		webhook = Webhook.from_url(debug_url, adapter=RequestsWebhookAdapter())
		msg = f'```diff\n-{message}\n```'
		webhook.send(msg)
	elif 'Failed' in message:
		msg = f'```diff\n-{message}\n```'
		webhook.send(msg)
	elif 'Success' in message:
		msg = f'```diff\n+{message}\n```'
		webhook.send(msg)
	else:
		webhook = Webhook.from_url(debug_url, adapter=RequestsWebhookAdapter())
		webhook.send(message)

def watchOrderFilledStatus(api, user, user_key, ticker, quantity, side, limit_price, order_id):
	new_buy_limit_price_mulitplier = 1.005

	new_sell_stop_limit_price_multiplier = .9925

	sleep = 30
	log.info(f'Waiting {sleep}s before checking status for Original Order ID: {order_id}')
	time.sleep(sleep)

	try:
		order = api.get_order(order_id)
	except Exception as e:
		log.error(e)
	else:
		if order is None:
			message = 'Order was empty!'
			log.error(message)
			return message
		else:
			retry = 0
			order_id = order.id
			order_status = order.status
			log.info(f'Original Order status is {order_status}')

			while order_status == 'accepted' or order_status == 'new' and order_status != 'partially_filled' and order_status != 'filled' and order_status != 'canceled' and order_status != 'done_for_day' and order_status != 'replaced' and order_status != 'pending_replace' and retry < 5:

				log.info(f'Order Retry is {retry}/5')

				if side == 'buy':
					time.sleep(10)
					order = api.get_order(order_id)
					order_id = order.id
					order_status = order.status
					log.info(order)
					log.info(f'Buy Order status is {order_status}')

					if order_status == 'filled':
						message = f'Success: Order Status is {order_status}. Breaking!'
						log.info(message)
						break
					if order_status == 'canceled' or order_status == 'done_for_day' or order_status == 'replaced' or order_status == 'pending_replace':
						message = f'Error: Order Status is {order_status}. Breaking!'
						log.info(message)
						break
					if retry >= 4:
						message = f'Order Failed: Retry limit reached to {side} {quantity} of {ticker}. Aborting.'
						log.error(message)
						sendDiscordMessage(message)
						break 

					new_limit_price = round(float(order.limit_price) * new_buy_limit_price_mulitplier, 2)

					try:
						order = api.replace_order(
							order_id=order.id,
							qty=quantity,
							time_in_force='day',
							limit_price=new_limit_price
						)
						order_id = order.id
						order_status = order.status

						log.info(f'Updated Buy Order ID: {order_id}')
					except tradeapi.rest.APIError as err:
						if 'sent to exchange yet' in err.response.content:
							log.info(err.response.content)
						else:
							log.error(f'Error submitting updated buy order: {err.response.content}')
					else:
						log.info(f'Buy Limit Price was changed from {limit_price} to {new_limit_price}')
						limit_price = new_limit_price
						log.info(f'Buy Order status is: {order_status}')

				elif side == 'sell':
					time.sleep(10)
					order = api.get_order(order_id)
					order_id = order.id
					order_status = order.status
					log.info(f'Sell Order status is {order_status}')

					if order_status == 'filled' or order_status == 'partially_filled' or order_status == 'canceled' or order_status == 'done_for_day' or order_status == 'replaced' or order_status == 'pending_replace':
						message = f'Order Status is {order_status}. Breaking!'
						log.info(message)
						sendDiscordMessage(message)
						break

					if retry >= 4:
						message = f'Order Failed: Retry limit reached to {side} {quantity} of {ticker}. Aborting.'
						log.error(message)
						sendDiscordMessage(message)
						break 

					new_limit_price = round(float(order.limit_price) * new_sell_stop_limit_price_multiplier, 2)

					try:
						order = api.replace_order(
							order_id=order.id,
							qty=quantity,
							time_in_force='day',
							limit_price=new_limit_price
						)
						order_id = order.id
						order_status = order.status
						log.info(f'Updated Sell Order ID: {order_id}')
					except tradeapi.rest.APIError as err:
						log.error(f'Error submitting updated sell order: {err.response.content}')
					else:
						log.info(f'Sell Limit Price was changed from {limit_price} to {new_limit_price}')
						limit_price = new_limit_price
						log.info(f'Sell Order status is: {order_status}')
				else:
					log.error(f'Order is neither buy nor sell!')
				sleep = 10
				log.info(f'Waiting {sleep}s before retrying...')

				time.sleep(sleep)

				retry += 1

			if order_status == 'filled':
				message = f'Success: Order to {side} of {quantity} shares of {ticker} at ${limit_price} was {order_status}.'
				log.info(message)
				sendDiscordMessage(message)
			if order_status == 'canceled' or order_status == 'done_for_day' or order_status == 'replaced' or order_status == 'pending_replace':
				message = f'Failed - User: {user} - Order to {side} of {quantity} shares of {ticker} at ${limit_price} was {order_status}.'
				log.info(message)
				sendDiscordMessage(message)

def submitAlpacaOrder(ticker, quantity, limit_price, side, APCA_API_KEY_ID, APCA_API_SECRET_KEY):
	# Set User and Key
	user = APCA_API_KEY_ID
	user_key = APCA_API_SECRET_KEY

	# Check if Live or Paper Trading
	if user[0:2] == 'PK':
		api = tradeapi.REST(user, user_key, 'https://paper-api.alpaca.markets')
		log.info('Using Paper Trading API')
	elif user[0:2] == 'AK':
		api = tradeapi.REST(user, user_key, 'https://api.alpaca.markets')
		log.info('Using Live Trading API')
	else:
		log.error(f'Error: API Key {user} is malformed.')
		sendDiscordMessage(f'Error: API Key {user} is malformed.')

	# Get Account information
	account = api.get_account()

	# Check available Buying Power
	buying_power = float(account.buying_power)   

	log.info(f'Buying Power is ${buying_power}')


	# Show Order Parameters
	log.info(f'Ticker is {ticker}')
	log.info(f'Price is ${limit_price}')
	log.info(f'Quantity is {quantity}')
	log.info(f'Side is {side}')

	# Check if Account is Blocked
	if account.trading_blocked:
		sendDiscordMessage(f'Order Failed - User: {user} - Account is currently restricted from trading.')
		log.info('Account is currently restricted from trading.')

	if side == 'sell':
		try:
			order = api.submit_order(
				symbol=ticker,
				qty=quantity,
				side=side,
				type='limit',
				limit_price=limit_price,
				time_in_force='day',
			)
		except tradeapi.rest.APIError as e:
			if 'account is not authorized to trade' in e:
				log.error(f'Failed: {e} - User: {user} - Check your API Keys are correct')
				sendDiscordMessage(str(e))
				return str(e)
			else:
				log.error(f'Error submitting Order: {e}')
				sendDiscordMessage(str(e))
				return str(e)
		else:
			log.info(order)
			if 'accepted' in order.status:
				log.info(f'Pending Order - User: {user} - Order to {side} of {quantity} shares of {ticker} at ${limit_price} was {order.status}.')
				sleep(10)
				try:
					status = watchOrderFilledStatus(api, user, user_key, ticker, quantity, side, limit_price, order.id)
				except Exception as e:
					log.error(str(e))
					sendDiscordMessage(str(e))
					return str(e)
			else:
				message = f'Failed - User: {user} - Order to {side} of {quantity} shares of {ticker} at ${limit_price} was {order.status}.'
				log.info(message)
				sendDiscordMessage(message)
				return message

	elif side == 'buy':
		try:
			order = api.submit_order(
				symbol=ticker,
				qty=quantity,
				side=side,
				type='limit',
				limit_price=limit_price,
				time_in_force='day',
			)
		except tradeapi.rest.APIError as e:
			if 'account is not authorized to trade' in e:
				log.error(f'Failed: {e} - User: {user} - Check your API Keys are correct')
				sendDiscordMessage(str(e))
				return str(e)
			else:
				log.error(f'Error submitting Order: {e}')
				sendDiscordMessage(str(e))
				return str(e)
		else:
			log.info(order)
			if 'accepted' in order.status:
				log.info(f'Pending Order - User: {user} - Order to {side} of {quantity} shares of {ticker} at ${limit_price} was {order.status}.')
				sleep(10)
				try:
					status = watchOrderFilledStatus(api, user, user_key, ticker, quantity, side, limit_price, order.id)
				except Exception as e:
					log.error(str(e))
					sendDiscordMessage(str(e))
					return str(e)
			else:
				message = f'Failed - User: {user} - Order to {side} of {quantity} shares of {ticker} at ${limit_price} was {order.status}.'
				log.info(message)
				sendDiscordMessage(message)
				return message
#if __name__ == '__main__':
#	ticker = 'QQQ'
#	quantity = 1
#	price = 366.5
#	side = 'buy'
#	APCA_API_KEY_ID = ''
#	APCA_API_SECRET_KEY = ''

#	submitAlpacaOrder(ticker, quantity, price, side, APCA_API_KEY_ID, APCA_API_SECRET_KEY)

