import base64
import configparser
from decimal import Decimal
import hashlib
import hmac
import json
import logging
import os
from datetime import timedelta, datetime
from http import HTTPStatus
from logging.handlers import TimedRotatingFileHandler

import nano
import requests
import telegram
import tweepy
from flask import Flask, render_template, request, Response, redirect, jsonify
from flask_weasyprint import HTML, render_pdf

import modules.currency
import modules.db
import modules.orchestration
import modules.social
import modules.translations as translations

# Set Log File
logger = logging.getLogger("main_log")
tweet_log = logging.getLogger("tweet_log")
tweet_log.setLevel(logging.INFO)
logger.setLevel(logging.INFO)
handler = TimedRotatingFileHandler('{}/logs/{:%Y-%m-%d}-main.log'.format(os.getcwd(), datetime.now()),
                                   when="d",
                                   interval=1,
                                   backupCount=5)
tweet_handler = TimedRotatingFileHandler('{}/logs/{:%Y-%m-%d}-tweet.log'.format(os.getcwd(), datetime.now()),
                                         when="d",
                                         interval=1,
                                         backupCount=5)
logger.addHandler(handler)
tweet_log.addHandler(tweet_handler)

# Read config and parse constants
config = configparser.ConfigParser()
config.read('webhookconfig.ini')

# Check the currency of the bot
CURRENCY = config.get('main', 'currency')
CONVERT_MULTIPLIER = {
    'nano': 1000000000000000000000000000000,
    'banano': 100000000000000000000000000000
}

# Twitter API connection settings
CONSUMER_KEY = config.get(CURRENCY, 'consumer_key')
CONSUMER_SECRET = config.get(CURRENCY, 'consumer_secret')
ACCESS_TOKEN = config.get(CURRENCY, 'access_token')
ACCESS_TOKEN_SECRET = config.get(CURRENCY, 'access_token_secret')

# Telegram API
TELEGRAM_KEY = config.get(CURRENCY, 'telegram_key')

# IDs
BOT_ID_TWITTER = config.get(CURRENCY, 'bot_id_twitter')
BOT_ID_TELEGRAM = config.get(CURRENCY, 'bot_id_telegram')
BOT_ACCOUNT = config.get(CURRENCY, 'bot_account')
BOT_NAME_TWITTER = config.get(CURRENCY, 'bot_name_twitter')
BOT_NAME_TELEGRAM = config.get(CURRENCY, 'bot_name_telegram')


# Set route variables
TWITTER_URI = config.get('routes', 'twitter_uri')
TWITTER_BANANO_URI = config.get('routes', 'twitter_banano_uri')
TELEGRAM_URI = config.get('routes', 'telegram_uri')
TELEGRAM_BANANO_URI = config.get('routes', 'telegram_banano_uri')
TELEGRAM_SET_URI = config.get('routes', 'telegram_set_uri')
BASE_URL = config.get('routes', 'base_url')
EXPLORER = config.get('routes', '{}_explorer'.format(CURRENCY))


# DB Data
DB_SCHEMA = config.get(CURRENCY, 'schema')


# Set up Flask routing
app = Flask(__name__)

# Connect to Twitter
auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
api = tweepy.API(auth)

# Connect to Telegram
if TELEGRAM_KEY != 'none':
    telegram_bot = telegram.Bot(token=TELEGRAM_KEY)

# Connect to Nano Node
NODE_IP = config.get(CURRENCY, 'node_ip')
rpc = nano.rpc.Client(NODE_IP)


# Flask routing
@app.route('/test/papertip')
def papertiptest():

    exp_length = 30

    currency_amount = 5.00
    currency_type = 'EUR'
    crypto_currency = 'NANO'
    nano_amount = modules.currency.get_fiat_conversion(currency_type, crypto_currency, currency_amount)

    if currency_type == 'USD':
        currency_mark = '$'
    elif currency_type == 'EUR':
        currency_mark = u"\u20AC"
    else:
        currency_mark = u"\u00A3"

    gen_date = datetime.now().strftime("%b %d, %y")
    exp_date = (datetime.now() + timedelta(days=exp_length)).strftime("%b %d, %y")
    nano_price = modules.currency.get_fiat_price(currency_type, crypto_currency)
    qr_img = "papertipqr.png"
    qr_link = "https://nanotipbot.com/tips/iaoi4fat-haa-32aaa"
    num_tip = 6

    return render_template('/templates/papertip.html', nano_amount=nano_amount, currency_mark=currency_mark,
                           currency_amount=currency_amount, gen_date=gen_date, exp_date=exp_date, nano_price=nano_price,
                           qr_img=qr_img, qr_link=qr_link, num_tip=num_tip, currency=CURRENCY)


@app.route('/test/papertippdf')
def paperpdf():

    exp_length = 30

    currency_amount = 5.00
    currency_type = 'USD'
    crypto_currency = 'NANO'
    nano_amount = modules.currency.get_fiat_conversion(currency_type, crypto_currency, currency_amount)

    if currency_type == 'USD':
        currency_mark = '$'
    elif currency_type == 'EUR':
        currency_mark = u"\u20AC"
    else:
        currency_mark = u"\u00A3"

    gen_date = datetime.now().strftime("%b %d, %y")
    exp_date = (datetime.now() + timedelta(days=exp_length)).strftime("%b %d, %y")
    nano_price = modules.currency.get_fiat_price(currency_type, crypto_currency)
    qr_img = "papertipqr.png"
    qr_link = "https://nanotipbot.com/tips/iaoi4fat-haa-32aaa"
    num_tip = 12

    html = render_template('papertip.html', nano_amount=nano_amount, currency_mark=currency_mark,
                           currency_amount=currency_amount, gen_date=gen_date, exp_date=exp_date, nano_price=nano_price,
                           qr_img=qr_img, qr_link=qr_link, num_tip=num_tip, currency=CURRENCY)

    return render_pdf(HTML(string=html))


@app.route('/pay', methods=['GET'])
def deep_link_test():
    address = request.args.get('address')
    amount = request.args.get('amount')

    if amount is None:
        uri = "nano://{}".format(address)
        return render_template('uriformatter.html', uri=uri, address=address, currency=CURRENCY)

    else:
        logger.info(amount)
        amount_raw = int(Decimal(amount) * CONVERT_MULTIPLIER[CURRENCY])
        logger.info("amount_raw = {}".format(int(amount_raw)))
        uri = "nano://{}?amount={}".format(address, amount_raw)
        return render_template('uriformatter.html', uri=uri, address=address, amount=Decimal(amount),
                               amount_raw=amount_raw, currency=CURRENCY)


@app.route('/noappredirect')
def noappredirect():
    address = request.args.get('address')
    amount_raw = request.args.get('amount')

    logger.info("amount: {}".format(amount_raw))
    logger.info("amount = none: {}".format((amount_raw is None)))

    if amount_raw is None or amount_raw == 'None' or amount_raw == '':
        return render_template('noappredirect.html', address=address, amount=0, amount_raw=0)

    return render_template('noappredirect.html', address=address,
                           amount=int(amount_raw) / CONVERT_MULTIPLIER[CURRENCY], amount_raw=amount_raw,
                           currency=CURRENCY)


@app.route('/paygenerator')
def linkgenerator():
    return render_template('linkgenerator.html', currency=CURRENCY)


@app.route('/tutorial')
@app.route('/tutorial.html')
def tutorial():
    if CURRENCY == 'banano':
        tip_command = '!ban'
    else:
        tip_command = '!tip'

    return render_template('tutorial.html', currency=CURRENCY, bot_id=BOT_ID_TWITTER, bot_name_twitter=BOT_NAME_TWITTER, tip_command=tip_command)


@app.route('/about')
@app.route('/about.html')
def about():
    btc_energy = 887000
    nano_energy = 0.032
    total_energy, checked_blocks = modules.currency.get_energy(nano_energy)

    total_energy = round(total_energy, 3)

    btc_vs_nano = round((total_energy / btc_energy), 3)

    total_energy_formatted = '{:,}'.format(total_energy)
    btc_energy_formatted = '{:,}'.format(btc_energy)
    checked_blocks_formatted = '{:,}'.format(checked_blocks)

    return render_template('about.html', btc_energy=btc_energy_formatted, nano_energy=nano_energy,
                           btc_vs_nano=btc_vs_nano, total_energy=total_energy_formatted,
                           checked_blocks=checked_blocks_formatted, currency=CURRENCY)


@app.route('/contact')
@app.route('/contact.html')
def contact():
    return render_template('contact.html', currency=CURRENCY)


@app.route('/contact-form-thank-you')
@app.route('/contact-form-thank-you.html')
def thanks():
    return render_template('contact-form-thank-you.html', currency=CURRENCY)


@app.route('/tippers')
@app.route('/tippers.html')
def tippers():
    largest_tip = ("SELECT user_name, amount, account, a.system, timestamp "
                   "FROM {0}.tip_list AS a, {0}.users AS b "
                   "WHERE user_id = sender_id "
                   "AND user_name IS NOT NULL "
                   "AND processed = 2 "
                   # "AND user_name != 'mitche50' "
                   "AND amount = (select max(amount) "
                   "FROM {0}.tip_list) "
                   "ORDER BY timestamp DESC "
                   "LIMIT 1;".format(DB_SCHEMA))

    tippers_call = ("SELECT user_name AS 'screen_name', sum(amount) AS 'total_tips', account, b.system "
                    "FROM {0}.tip_list AS a, {0}.users AS b "
                    "WHERE user_id = sender_id "
                    "AND user_name IS NOT NULL "
                    "AND receiver_id IN (SELECT user_id FROM {0}.users) "
                    "GROUP BY sender_id "
                    "ORDER BY sum(amount) DESC "
                    "LIMIT 50".format(DB_SCHEMA))

    tipper_table = modules.db.get_db_data(tippers_call)
    top_tipper = modules.db.get_db_data(largest_tip)
    logger.info("tipper_call: {}".format(tippers_call))
    logger.info("largest_tip: {}".format(largest_tip))
    top_tipper_date = top_tipper[0][4].date()
    return render_template('tippers.html', tipper_table=tipper_table, top_tipper=top_tipper,
                           top_tipper_date=top_tipper_date, currency=CURRENCY, explorer=EXPLORER)


@app.route('/tiplist')
def tip_list():
    tip_list_call = ("SELECT DISTINCT t1.user_name AS 'Sender ID', t2.user_name AS 'Receiver ID', t1.amount, "
                     "t1.account AS 'Sender Account', t2.account AS 'Receiver Account', t1.system, t1.timestamp "
                     "FROM "
                     "(SELECT user_name, amount, account, a.system, timestamp "
                     "FROM {0}.tip_list AS a, {0}.users AS b "
                     "WHERE user_id = sender_id "
                     "AND user_name IS NOT NULL "
                     "AND processed = 2 "
                     # "AND user_name != 'mitche50' "
                     "ORDER BY timestamp desc "
                     "LIMIT 50) AS t1 "
                     "JOIN "
                     "(SELECT user_name, account, timestamp "
                     "FROM {0}.tip_list, {0}.users "
                     "WHERE user_id = receiver_id "
                     "AND user_name IS NOT NULL "
                     "AND processed = 2 "
                     "ORDER BY timestamp DESC "
                     "LIMIT 20) AS t2 "
                     "ON t1.timestamp = t2.timestamp".format(DB_SCHEMA))
    tip_list_table = modules.db.get_db_data(tip_list_call)
    return render_template('tiplist.html', tip_list_table=tip_list_table, currency=CURRENCY, explorer=EXPLORER)


@app.route('/')
@app.route('/index')
@app.route('/index.html')
def index():
    r = requests.get('https://api.coingecko.com/api/v3/simple/price?ids={}&vs_currencies=usd'.format(CURRENCY))
    rx = r.json()
    price = float(rx[CURRENCY]['usd'])
    if CURRENCY == 'banano':
        tip_command = '!ban'
    else:
        tip_command = '!tip'
    if price > .01:
        price = round(price, 2)

    total_tipped_nano = ("SELECT tip_list.system, sum(amount) AS total "
                         "FROM {0}.tip_list "
                         "WHERE receiver_id IN (SELECT user_id FROM {0}.users) "
                         "GROUP BY system "
                         "ORDER BY total DESC".format(DB_SCHEMA))

    total_tipped_number = ("SELECT tip_list.system, count(system) AS notips "
                           "FROM {0}.tip_list "
                           "WHERE receiver_id IN (SELECT user_id FROM {0}.users)"
                           "GROUP BY tip_list.system "
                           "ORDER BY notips DESC".format(DB_SCHEMA))

    total_tipped_nano_table = modules.db.get_db_data(total_tipped_nano)
    total_tipped_number_table = modules.db.get_db_data(total_tipped_number)
    try:
        total_value_usd = round(Decimal(total_tipped_nano_table[0][1] + total_tipped_nano_table[1][1]) * Decimal(price), 2)
    except Exception as e:
        total_value_usd = 0

    return render_template('index.html', total_tipped_nano_table=total_tipped_nano_table,
                           total_tipped_number_table=total_tipped_number_table, total_value_usd=total_value_usd,
                           price=price, currency=CURRENCY, bot_id=BOT_ID_TWITTER, bot_account=BOT_ACCOUNT,
                           bot_name_twitter=BOT_NAME_TWITTER, bot_name_telegram=BOT_NAME_TELEGRAM,
                           tip_command=tip_command)


@app.route('/users/twitter/<username>', methods=["GET"])
def get_user_address_twitter(username):
    # Returns the address of the provided username
    address_call = ("SELECT account FROM users "
                   "WHERE user_name = %s AND system = 'twitter'")
    address_values = [username,]
    address_return = modules.db.get_db_data_new(address_call, address_values)
    try:
        if address_return[0][0] is not None:
            json_response = {
                "account": address_return[0][0]
            }
            response = jsonify(json_response)
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response, 200
        else:
            return "Account not found for user {} on twitter".format(username)
    except Exception as e:
        return e

@app.route('/users/<address>', methods=["GET"])
def get_user_from_address(address):
    # Returns the user info of the provided address
    address_call = ("SELECT user_id, system, user_name FROM users "
                   "WHERE account = %s")
    address_values = [address,]
    address_return = modules.db.get_db_data_new(address_call, address_values)
    try:
        if address_return[0] is not None:
            json_response = {
                'user_id': address_return[0][0],
                'system': address_return[0][1],
                'user_name': address_return[0][2]
            }
            response = jsonify(json_response)
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response, 200
        else:
            return "There is no user tied to address {}".format(address)
    except Exception as e:
        return e


@app.route('/users/telegram/<username>', methods=["GET"])
def get_user_address_telegram(username):
    # Returns the address of the provided username
    address_call = ("SELECT account FROM users "
                   "WHERE user_id = %s AND system = 'telegram'")
    address_values = [username,]
    address_return = modules.db.get_db_data_new(address_call, address_values)
    try:
        if address_return[0][0] is not None:
            json_response = {
                "account": address_return[0][0]
            }
            response = jsonify(json_response)
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response, 200
        else:
            return "Account not found for user {} on telegram".format(username)
    except Exception as e:
        return e


@app.route('/users/telegram', methods=["GET"])
def get_all_users_telegram():
    # Returns the address of the provided username
    address_call = ("SELECT user_id, user_name, account FROM users "
                   "WHERE system = 'telegram'")
    address_values = []
    address_return = modules.db.get_db_data_new(address_call, address_values)
    json_response = []
    try:
        if address_return is not None:
            for user in address_return:
                json_response.append({
                    "user_id": user[0],
                    "user_name": user[1],
                    "account": user[2]
                })
            response = jsonify(json_response)
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response, 200
        else:
            return "Error retrieving addresses on telegram"
    except Exception as e:
        return e


@app.route('/users/twitter', methods=["GET"])
def get_all_users_twitter():
    # Returns the address of the provided username
    address_call = ("SELECT user_id, user_name, account FROM users "
                   "WHERE system = 'twitter'")
    address_values = []
    address_return = modules.db.get_db_data_new(address_call, address_values)
    json_response = []
    try:
        if address_return is not None:
            for user in address_return:
                json_response.append({
                    "user_id": user[0],
                    "user_name": user[1],
                    "account": user[2]
                })
            response = jsonify(json_response)
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response, 200
        else:
            return "Error retrieving addresses on twitter"
    except Exception as e:
        return e


@app.route(TWITTER_BANANO_URI, methods=["GET"])
@app.route(TWITTER_URI, methods=["GET"])
def webhook_challenge():
    # creates HMAC SHA-256 hash from incoming token and your consumer secret
    logger.info("starting webhook challenge from twitter")
    try:
        crc = request.args.get('crc_token')

        validation = hmac.new(
            key=bytes(CONSUMER_SECRET, 'utf-8'),
            msg=bytes(crc, 'utf-8'),
            digestmod=hashlib.sha256
        )

        digested = base64.b64encode(validation.digest())

        # construct response data with base64 encoded hash
        response = {
            'response_token': 'sha256=' + format(str(digested)[2:-1])
        }

        return json.dumps(response), 200
    except Exception as e:
        logger.info("Error: {}".format(e))


@app.route('/webhooks/twitter/getaccount/<screen_name>', methods=["GET"])
def get_twitter_account(screen_name):
    try:
        user = api.get_user(screen_name)

        if user is not None:
            account_call = ("SELECT account FROM users "
                            "WHERE user_id = '{}' AND users.system = 'twitter';".format(user.id_str))
            account_return = modules.db.get_db_data(account_call)
            modules.currency.receive_pending(account_return[0][0])
            balance_return = rpc.account_balance(account="{}".format(account_return[0][0]))
            account_dict = {
                'user_id': user.id_str,
                'account': account_return[0],
                'balance': str(balance_return['balance'] / CONVERT_MULTIPLIER[CURRENCY]),
                'pending': str(balance_return['pending'] / CONVERT_MULTIPLIER[CURRENCY])
            }
            response = Response(json.dumps(account_dict))
            response.headers['Access-Control-Allow-Credentials'] = True
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Content-Type'] = 'application/json'
            return response, HTTPStatus.OK
        else:
            logger.info('{}: No user found.'.format(datetime.now()))
            account_dict = {
                'user_id': None,
                'account': None,
                'balance': None,
                'pending': None
            }
            response = Response(json.dumps(account_dict))
            response.headers['Access-Control-Allow-Credentials'] = True
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Content-Type'] = 'application/json'
            return response, HTTPStatus.OK
    except Exception as e:
        logger.info('{}: ERROR in get_twitter_account(webhooks.py): {}'.format(datetime.now(), e))
        account_dict = {
            'user_id': None,
            'account': None,
            'balance': None,
            'pending': None
        }
        response = Response(json.dumps(account_dict))
        response.headers['Access-Control-Allow-Credentials'] = True
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Content-Type'] = 'application/json'
        return response, HTTPStatus.OK


@app.route('/webhooks/twitter/refreshbalance/<account>', methods=["GET"])
def refresh_balance(account):
    try:
        balance_return = rpc.account_balance(account="{}".format(account))
        balance_dict = {
            'balance': balance_return[0],
            'pending': balance_return[1]
        }
        response = Response(json.dumps(balance_dict))
        response.headers['Access-Control-Allow-Credentials'] = True
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Content-Type'] = 'application/json'

        return response, HTTPStatus.OK
    except Exception as e:
        logger.info("{}: ERROR in refresh_balance (webhooks.py): {}".format(datetime.now, e))
        return e, HTTPStatus.BAD_REQUEST


@app.route(TELEGRAM_BANANO_URI, methods=["POST"])
@app.route(TELEGRAM_URI, methods=["POST"])
def telegram_event():
    message = {
        # id:                     ID of the received tweet - Error logged through None value
        # text:                   A list containing the text of the received tweet, split by ' '
        # sender_id:              Twitter ID of the user sending the tip
        # sender_screen_name:     Twitter Handle of the user sending the tip
        # sender_account:         Nano account of sender - Error logged through None value
        # sender_register:        Registration status with Tip Bot of sender account
        # sender_balance_raw:     Amount of Nano in sender's account, stored in raw
        # sender_balance:         Amount of Nano in sender's account, stored in Nano

        # action_index:           Location of key action value *(currently !tip only)
        # action:                 Action found in the received tweet - Error logged through None value

        # starting_point:         Location of action sent via tweet (currently !tip only)

        # tip_amount:             Value of tip to be sent to receiver(s) - Error logged through -1
        # tip_amount_text:        Value of the tip stored in a string to prevent formatting issues
        # total_tip_amount:       Equal to the tip amount * number of users to tip
        # tip_id:                 ID of the tip, used to prevent double sending of tips.  Comprised of
        #                         message['id'] + index of user in users_to_tip
        # send_hash:              Hash of the send RPC transaction
        # system:                 System that the command was sent from
    }

    users_to_tip = [
        # List including dictionaries for each user to send a tip.  Each index will include
        # the below parameters
        #    receiver_id:            Twitter ID of the user receiving a tip
        #    receiver_screen_name:   Twitter Handle of the user receiving a tip
        #    receiver_account:       Nano account of receiver
        #    receiver_register:      Registration status with Tip Bot of reciever account
    ]
    message['system'] = 'telegram'
    request_json = request.get_json()
    if 'message' in request_json.keys():
        if request_json['message']['chat']['type'] == 'private':
            logger.info("Direct message received in Telegram.  Processing.")
            message['sender_id'] = request_json['message']['from']['id']
            bot_ids = ['1115793994024464384', '894722023', '966739513195335680', '624103005']
            if message['sender_id'] in bot_ids:
                return 'ok'
            try:
                message['sender_screen_name'] = request_json['message']['from']['username']
            except KeyError:
                if 'first_name' in request_json['message']['from'].keys():
                    message['sender_screen_name'] = request_json['message']['from']['first_name']
                if 'last_name' in request_json['message']['from'].keys():
                    message['sender_screen_name'] = \
                        message['sender_screen_name'] + ' ' + request_json['message']['from']['last_name']
            message['dm_id'] = request_json['update_id']
            try:
                message['text'] = request_json['message']['text']
            except KeyError:
                logger.info("error in DM processing: {}".format(request_json))
                return ''
            message['dm_array'] = message['text'].split(" ")
            message['dm_action'] = message['dm_array'][0].lower()
            modules.social.get_language(message)

            logger.info("{}: action identified: {}".format(datetime.now(), message['dm_action']))

            # Update DB with new DM
            # dm_insert_call = ("INSERT INTO dm_list (dm_id, processed, sender_id, dm_text, system) "
            #                   "VALUES (%s, 0, %s, %s, 'telegram')")
            # dm_insert_values = [message['dm_id'], message['sender_id'], message['text']]
            # err = modules.db.set_db_data(dm_insert_call, dm_insert_values)
            # if err is not None:
            #     return 'ok'

            modules.orchestration.parse_action(message)

        elif (request_json['message']['chat']['type'] == 'supergroup' or
              request_json['message']['chat']['type'] == 'group'):

            if 'forward_from' in request_json['message']:
                return '', HTTPStatus.OK

            if 'text' in request_json['message']:
                message['sender_id'] = request_json['message']['from']['id']
                if 'username' in request_json['message']['from']:
                    message['sender_screen_name'] = request_json['message']['from']['username']
                else:
                    if 'first_name' in request_json['message']['from'].keys():
                        message['sender_screen_name'] = request_json['message']['from']['first_name']
                    if 'last_name' in request_json['message']['from'].keys():
                        message['sender_screen_name'] = \
                            message['sender_screen_name'] + ' ' + request_json['message']['from']['last_name']
                message['id'] = request_json['message']['message_id']
                message['chat_id'] = request_json['message']['chat']['id']
                message['chat_name'] = request_json['message']['chat']['title']

                modules.social.check_telegram_member(message['chat_id'], message['chat_name'], message['sender_id'],
                                                     message['sender_screen_name'])

                message['text'] = request_json['message']['text']
                message['text'] = message['text'].replace('\n', ' ')
                message['text'] = message['text'].lower()
                message['text'] = message['text'].split(' ')
                modules.social.get_language(message)

                message = modules.social.check_message_action(message)
                if message['action'] is None:
                    return '', HTTPStatus.OK

                message = modules.social.validate_tip_amount(message)
                if message['tip_amount'] <= 0:
                    return '', HTTPStatus.OK

                logger.info("Got past initial checks.")
                logger.info("message: {}".format(message))
                logger.info("bot_id_telegram: {}".format(BOT_ID_TELEGRAM))
                logger.info("sender id: {}".format(message['sender_id']))

                if message['action'] != -1 and str(message['sender_id']) != str(BOT_ID_TELEGRAM):
                    new_pid = os.fork()
                    if new_pid == 0:
                        try:
                            bot_status = config.get('main', 'bot_status')
                            if bot_status == 'maintenance':
                                modules.social.send_dm(message['sender_id'],
                                                    translations.maintenance_text[message['language']].format(BOT_NAME_TWITTER),
                                                    message['system'])
                                return ''
                            elif message['system'] == 'twitter' and bot_status == 'twitter-maintenance':
                                modules.social.send_dm(message['sender_id'],
                                                    translations.maintenance_text[message['language']].format(BOT_NAME_TWITTER),
                                                    message['system'])
                                return ''
                            elif message['system'] == 'telegram' and bot_status == 'telegram-maintenance':
                                modules.social.send_dm(message['sender_id'],
                                                    translations.maintenance_text[message['language']].format(BOT_NAME_TWITTER),
                                                    message['system'])
                                return ''
                            else:
                                modules.orchestration.tip_process(message, users_to_tip, request_json)
                        except Exception as e:
                            logger.info("Exception: {}".format(e))
                            raise e

                        os._exit(0)
                    else:
                        return '', HTTPStatus.OK
            elif 'new_chat_member' in request_json['message']:
                logger.info("new member joined chat, adding to DB")
                chat_id = request_json['message']['chat']['id']
                chat_name = request_json['message']['chat']['title']
                member_id = request_json['message']['new_chat_member']['id']
                if 'username' in request_json['message']['new_chat_member']:
                    member_name = request_json['message']['new_chat_member']['username']
                else:
                    member_name = None

                new_chat_member_call = (
                    "INSERT IGNORE INTO telegram_chat_members (chat_id, chat_name, member_id, member_name) "
                    "VALUES (%s, %s, %s, %s)")
                new_member_values = [chat_id, chat_name, member_id, member_name]
                err = modules.db.set_db_data(new_chat_member_call, new_member_values)
                if err is not None:
                    return 'ok'

            elif 'left_chat_member' in request_json['message']:
                chat_id = request_json['message']['chat']['id']
                chat_name = request_json['message']['chat']['title']
                member_id = request_json['message']['left_chat_member']['id']
                if 'username' in request_json['message']['left_chat_member']:
                    member_name = request_json['message']['left_chat_member']['username']
                else:
                    member_name = None
                logger.info("member {}-{} left chat {}-{}, removing from DB.".format(member_id, member_name, chat_id,
                                                                                      chat_name))

                remove_member_call = ("DELETE FROM telegram_chat_members "
                                      "WHERE chat_id = %s AND member_id = %s")
                remove_member_values = [chat_id, member_id]
                err = modules.db.set_db_data(remove_member_call, remove_member_values)
                if err is not None:
                    return 'ok'

            elif 'group_chat_created' in request_json['message']:
                chat_id = request_json['message']['chat']['id']
                chat_name = request_json['message']['chat']['title']
                member_id = request_json['message']['from']['id']
                member_name = request_json['message']['from']['username']
                logger.info("member {} created chat {}, inserting creator into DB.".format(member_name, chat_name))
                new_chat_call = ("INSERT IGNORE INTO telegram_chat_members (chat_id, chat_name, member_id, member_name) "
                                 "VALUES (%s, %s, %s, %s)")
                new_chat_values = [chat_id, chat_name, member_id, member_name]
                err = modules.db.set_db_data(new_chat_call, new_chat_values)
                if err is not None:
                    return 'ok'

        else:
            logger.info("request: {}".format(request_json))
    return 'ok'


@app.route(TWITTER_BANANO_URI, methods=["POST"])
@app.route(TWITTER_URI, methods=["POST"])
def twitter_event_received():
    message = {}
    users_to_tip = []

    message['system'] = 'twitter'
    request_json = request.get_json()
    auth_header = request.headers.get('X-Twitter-Webhooks-Signature')
    request_data = request.get_data()
    validation = hmac.new(
        key=bytes(CONSUMER_SECRET, 'utf-8'),
        msg=request_data,
        digestmod=hashlib.sha256
    )

    tweet_log.info("{}: Message received from twitter: {}".format(datetime.now(), request_json))

    digested = base64.b64encode(validation.digest())
    compare_auth = 'sha256=' + format(str(digested)[2:-1])
    try:
        hash_comparison = hmac.compare_digest(auth_header, compare_auth)
    except Exception as e:
        if request.headers.getlist("X-Forwarded-For"):
            ip = request.headers.getlist("X-Forwarded-For")[0]
        else:
            ip = request.remote_addr
        logger.info("auth header not provided, probable malicious access attempt from IP: {}".format(ip))
        return 'You are not allowed to access this webhook.', HTTPStatus.BAD_REQUEST

    if not hash_comparison:
        if request.headers.getlist("X-Forwarded-For"):
            ip = request.headers.getlist("X-Forwarded-For")[0]
        else:
            ip = request.remote_addr
        logger.info("auth header not provided, probable malicious access attempt from IP: {}".format(ip))
        return 'You are not allowed to access this webhook.', HTTPStatus.BAD_REQUEST

    if 'direct_message_events' in request_json.keys():
        """
        User sent a DM to the bot.  Parse the DM, see if there is an action provided and perform it.
        If no action is provided, reply with an error.
        Each action spawns a child process that will handle the requested action and terminate after completion.
        """
        # DM received, process that
        dm_object = request_json['direct_message_events'][0]
        message_object = request_json['direct_message_events'][0].get('message_create', {})

        message['sender_id'] = message_object.get('sender_id')
        bot_ids = ['1115793994024464384', '894722023', '966739513195335680', '624103005']
        if message['sender_id'] in bot_ids:
            return

        user_info = api.get_user(message['sender_id'])
        message['sender_screen_name'] = user_info.screen_name
        message['dm_id'] = dm_object.get('id')
        message['text'] = message_object.get('message_data', {}).get('text')
        message['dm_array'] = message['text'].split(" ")
        message['dm_action'] = message['dm_array'][0].lower()
        modules.social.get_language(message)

        logger.info("Processing direct message.")

        # Update DB with new DM
        dm_insert_call = ("INSERT INTO dm_list (dm_id, processed, sender_id, dm_text, system) "
                          "VALUES (%s, 0, %s, %s, 'twitter')")
        dm_insert_values = [message['dm_id'], message['sender_id'], message['text']]
        err = modules.db.set_db_data(dm_insert_call, dm_insert_values)
        if err is not None:
            return 'ok'

        logger.info("{}: action identified: {}".format(datetime.now(), message['dm_action']))
        # Check for action on DM
        modules.orchestration.parse_action(message)

        return '', HTTPStatus.OK

    elif 'tweet_create_events' in request_json.keys():
        """
        A tweet was received.  The bot will parse the tweet, see if there are any tips and process them.
        Error handling will cover if the sender doesn't have an account, doesn't have enough to cover the tips,
        sent to an invalid username, didn't send an amount to tip or didn't send a !tip command.
        """

        tweet_object = request_json['tweet_create_events'][0]
        # tweet_log.info("{}: Tweet received: From - {} - Text - {}".format(datetime.now(), 
        #                                                                tweet_object.get('user', {}).get('screen_name'),
        #                                                                tweet_object.get('text')))

        message = modules.social.set_message_info(tweet_object, message)
        if message['id'] is None:
            return '', HTTPStatus.OK

        message = modules.social.check_message_action(message)
        if message['action'] is None:
            logger.info("{}: Mention of nano tip bot without a !tip command.".format(datetime.now()))
            return '', HTTPStatus.OK

        message = modules.social.validate_tip_amount(message)
        if message['tip_amount'] <= 0:
            return '', HTTPStatus.OK

        if message['action'] != -1 and str(message['sender_id']) != str(BOT_ID_TWITTER):
            new_pid = os.fork()
            if new_pid == 0:
                try:
                    bot_status = config.get('main', 'bot_status')
                    if bot_status == 'maintenance':
                        modules.social.send_dm(message['sender_id'],
                                            translations.maintenance_text[message['language']].format(BOT_NAME_TWITTER),
                                            message['system'])
                        return ''
                    elif message['system'] == 'twitter' and bot_status == 'twitter-maintenance':
                        modules.social.send_dm(message['sender_id'],
                                            translations.maintenance_text[message['language']].format(BOT_NAME_TWITTER),
                                            message['system'])
                        return ''
                    elif message['system'] == 'telegram' and bot_status == 'telegram-maintenance':
                        modules.social.send_dm(message['sender_id'],
                                            translations.maintenance_text[message['language']].format(BOT_NAME_TWITTER),
                                            message['system'])
                        return ''
                    else:
                        # Favoriting has been removed due to possible issues with Twitter automation rules.
                        # api.create_favorite(message['id'])
                        modules.orchestration.tip_process(message, users_to_tip, request_json)
                except Exception as e:
                    logger.info("Exception: {}".format(e))
                    raise e

                os._exit(0)
            else:
                return '', HTTPStatus.OK

        elif str(message['sender_id']) == str(BOT_ID_TWITTER):
            logger.info("{}: TipBot sent a message.".format(datetime.now()))

        return '', HTTPStatus.OK

    elif 'follow_events' in request_json.keys():
        """
        New user followed the bot.  Send a welcome message.
        """
        logger.info("{}: New user followed, sending help message.".format(datetime.now()))
        request_json = request.get_json()
        follow_object = request_json['follow_events'][0]
        follow_source = follow_object.get('source', {})
        message['sender_id'] = follow_source.get('id')
        modules.social.get_language(message)

        modules.orchestration.help_process(message)

        return '', HTTPStatus.OK

    else:
        # Event type not supported
        return '', HTTPStatus.OK


@app.cli.command('initdb')
def initdb_command():
    modules.db.db_init()


if __name__ == "__main__":
    modules.db.db_init()
    logger.info("db initialized from wsgi")
    modules.social.telegram_set_webhook()
    app.run(host='0.0.0.0')
