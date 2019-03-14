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

import nano
import requests
import telegram
import tweepy
from flask import Flask, render_template, request, Response
from flask_weasyprint import HTML, render_pdf

import modules.currency
import modules.db
import modules.orchestration
import modules.social
import modules.translations as translations

# Set Log File
logging.basicConfig(handlers=[logging.FileHandler('webhooks.log', 'a', 'utf-8')],
                    level=logging.INFO)

# Read config and parse constants
config = configparser.ConfigParser()
config.read('webhookconfig.ini')

# Twitter API connection settings
CONSUMER_KEY = config.get('webhooks', 'consumer_key')
CONSUMER_SECRET = config.get('webhooks', 'consumer_secret')
ACCESS_TOKEN = config.get('webhooks', 'access_token')
ACCESS_TOKEN_SECRET = config.get('webhooks', 'access_token_secret')

# Telegram API
TELEGRAM_KEY = config.get('webhooks', 'telegram_key')

# IDs
BOT_ID_TWITTER = config.get('webhooks', 'bot_id_twitter')
BOT_ID_TELEGRAM = config.get('webhooks', 'bot_id_telegram')

# Set key for webhook challenge from Twitter
key = config.get('webhooks', 'consumer_secret')

# Set route variables
TWITTER_URI = config.get('routes', 'twitter_uri')
TELEGRAM_URI = config.get('routes', 'telegram_uri')
TELEGRAM_SET_URI = config.get('routes', 'telegram_set_uri')
BASE_URL = config.get('routes', 'base_url')

# Set up Flask routing
app = Flask(__name__)

# Connect to Twitter
auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
api = tweepy.API(auth)

# Connect to Telegram
telegram_bot = telegram.Bot(token=TELEGRAM_KEY)

# Connect to Nano Node
NODE_IP = config.get('webhooks', 'node_ip')
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
                           qr_img=qr_img, qr_link=qr_link, num_tip=num_tip)


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
                           qr_img=qr_img, qr_link=qr_link, num_tip=num_tip)

    return render_pdf(HTML(string=html))


@app.route('/tutorial')
@app.route('/tutorial.html')
def tutorial():
    return render_template('tutorial.html')


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
                           checked_blocks=checked_blocks_formatted)


@app.route('/contact')
@app.route('/contact.html')
def contact():
    return render_template('contact.html')


@app.route('/contact-form-thank-you')
@app.route('/contact-form-thank-you.html')
def thanks():
    return render_template('contact-form-thank-you.html')


@app.route('/tippers')
@app.route('/tippers.html')
def tippers():
    largest_tip = ("SELECT user_name, amount, account, a.system, timestamp "
                   "FROM tip_bot.tip_list AS a, tip_bot.users AS b "
                   "WHERE user_id = sender_id "
                   "AND user_name IS NOT NULL "
                   "AND processed = 2 "
                   "AND user_name != 'mitche50' "
                   "AND amount = (select max(amount) "
                   "FROM tip_bot.tip_list) "
                   "ORDER BY timestamp DESC "
                   "LIMIT 1;")

    tippers_call = ("SELECT user_name AS 'screen_name', sum(amount) AS 'total_tips', account, b.system "
                    "FROM tip_bot.tip_list AS a, tip_bot.users AS b "
                    "WHERE user_id = sender_id "
                    "AND user_name IS NOT NULL "
                    "AND receiver_id IN (SELECT user_id FROM tip_bot.users)"
                    "GROUP BY sender_id "
                    "ORDER BY sum(amount) DESC "
                    "LIMIT 15")

    tipper_table = modules.db.get_db_data(tippers_call)
    top_tipper = modules.db.get_db_data(largest_tip)
    top_tipper_date = top_tipper[0][4].date()
    return render_template('tippers.html', tipper_table=tipper_table, top_tipper=top_tipper,
                           top_tipper_date=top_tipper_date)


@app.route('/tiplist')
def tip_list():
    tip_list_call = ("SELECT t1.user_name AS 'Sender ID', t2.user_name AS 'Receiver ID', t1.amount, "
                     "t1.account AS 'Sender Account', t2.account AS 'Receiver Account', t1.system, t1.timestamp "
                     "FROM "
                     "(SELECT user_name, amount, account, a.system, timestamp "
                     "FROM tip_bot.tip_list AS a, tip_bot.users AS b "
                     "WHERE user_id = sender_id "
                     "AND user_name IS NOT NULL "
                     "AND processed = 2 "
                     "AND user_name != 'mitche50' "
                     "ORDER BY timestamp desc "
                     "LIMIT 50) AS t1 "
                     "JOIN "
                     "(SELECT user_name, account, timestamp "
                     "FROM tip_bot.tip_list, tip_bot.users "
                     "WHERE user_id = receiver_id "
                     "AND user_name IS NOT NULL "
                     "AND processed = 2 "
                     "ORDER BY timestamp DESC "
                     "LIMIT 20) AS t2 "
                     "ON t1.timestamp = t2.timestamp")
    tip_list_table = modules.db.get_db_data(tip_list_call)
    print(tip_list_table)
    return render_template('tiplist.html', tip_list_table=tip_list_table)


@app.route('/')
@app.route('/index')
@app.route('/index.html')
def index():
    r = requests.get('https://api.coinmarketcap.com/v2/ticker/1567/')
    rx = r.json()
    price = round(rx['data']['quotes']['USD']['price'], 2)

    total_tipped_nano = ("SELECT tip_list.system, sum(amount) AS total "
                         "FROM tip_bot.tip_list "
                         "WHERE receiver_id IN (SELECT user_id FROM tip_bot.users) "
                         "GROUP BY system "
                         "ORDER BY total DESC")

    total_tipped_number = ("SELECT tip_list.system, count(system) AS notips "
                           "FROM tip_bot.tip_list "
                           "WHERE receiver_id IN (SELECT user_id FROM tip_bot.users)"
                           "GROUP BY tip_list.system "
                           "ORDER BY notips DESC")

    total_tipped_nano_table = modules.db.get_db_data(total_tipped_nano)
    total_tipped_number_table = modules.db.get_db_data(total_tipped_number)
    total_value_usd = round(Decimal(total_tipped_nano_table[0][1] + total_tipped_nano_table[1][1]) * Decimal(price), 2)

    return render_template('index.html', total_tipped_nano_table=total_tipped_nano_table,
                           total_tipped_number_table=total_tipped_number_table, total_value_usd=total_value_usd,
                           price=price)


@app.route(TWITTER_URI, methods=["GET"])
def webhook_challenge():
    # creates HMAC SHA-256 hash from incoming token and your consumer secret

    crc = request.args.get('crc_token')

    validation = hmac.new(
        key=bytes(key, 'utf-8'),
        msg=bytes(crc, 'utf-8'),
        digestmod=hashlib.sha256
    )

    digested = base64.b64encode(validation.digest())

    # construct response data with base64 encoded hash
    response = {
        'response_token': 'sha256=' + format(str(digested)[2:-1])
    }

    return json.dumps(response), 200


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
                'balance': str(balance_return['balance'] / 1000000000000000000000000000000),
                'pending': str(balance_return['pending'] / 1000000000000000000000000000000)
            }
            response = Response(json.dumps(account_dict))
            response.headers['Access-Control-Allow-Credentials'] = True
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Content-Type'] = 'application/json'
            return response, HTTPStatus.OK
        else:
            logging.info('{}: No user found.'.format(datetime.now()))
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
        logging.info('{}: ERROR in get_twitter_account(webhooks.py): {}'.format(datetime.now(), e))
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
        logging.info("{}: ERROR in refresh_balance (webhooks.py): {}".format(datetime.now, e))
        return e, HTTPStatus.BAD_REQUEST


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
            logging.info("Direct message received in Telegram.  Processing.")
            message['sender_id'] = request_json['message']['from']['id']
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
                logging.info("error in DM processing: {}".format(request_json))
                return ''
            message['dm_array'] = message['text'].split(" ")
            message['dm_action'] = message['dm_array'][0].lower()
            modules.social.get_language(message)

            logging.info("{}: action identified: {}".format(datetime.now(), message['dm_action']))

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

                if message['action'] != -1 and str(message['sender_id']) != str(BOT_ID_TELEGRAM):
                    new_pid = os.fork()
                    if new_pid == 0:
                        try:
                            bot_status = config.get('webhooks', 'bot_status')
                            if bot_status == 'maintenance':
                                modules.social.send_dm(message['sender_id'],
                                                       translations.maintenance_text[message['language']],
                                                       message['system'])
                            else:
                                modules.orchestration.tip_process(message, users_to_tip, request_json)
                        except Exception as e:
                            logging.info("Exception: {}".format(e))
                            raise e

                        os._exit(0)
                    else:
                        return '', HTTPStatus.OK
            elif 'new_chat_member' in request_json['message']:
                logging.info("new member joined chat, adding to DB")
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
                logging.info("member {}-{} left chat {}-{}, removing from DB.".format(member_id, member_name, chat_id,
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
                logging.info("member {} created chat {}, inserting creator into DB.".format(member_name, chat_name))
                new_chat_call = ("INSERT IGNORE INTO telegram_chat_members (chat_id, chat_name, member_id, member_name) "
                                 "VALUES (%s, %s, %s, %s)")
                new_chat_values = [chat_id, chat_name, member_id, member_name]
                err = modules.db.set_db_data(new_chat_call, new_chat_values)
                if err is not None:
                    return 'ok'

        else:
            logging.info("request: {}".format(request_json))
    return 'ok'


@app.route(TWITTER_URI, methods=["POST"])
def twitter_event_received():
    message = {}
    users_to_tip = []

    message['system'] = 'twitter'
    request_json = request.get_json()
    auth_header = request.headers.get('X-Twitter-Webhooks-Signature')
    request_data = request.get_data()
    validation = hmac.new(
        key=bytes(key, 'utf-8'),
        msg=request_data,
        digestmod=hashlib.sha256
    )

    digested = base64.b64encode(validation.digest())
    compare_auth = 'sha256=' + format(str(digested)[2:-1])
    try:
        logging.info("hash comparison: {}".format(hmac.compare_digest(auth_header, compare_auth)))
    except Exception as e:
        if request.headers.getlist("X-Forwarded-For"):
            ip = request.headers.getlist("X-Forwarded-For")[0]
        else:
            ip = request.remote_addr
        logging.info("auth header not provided, probable malicious access attempt from IP: {}".format(ip))
        return 'You are not allowed to access this webhook.', HTTPStatus.BAD_REQUEST

    if not hmac.compare_digest(auth_header, compare_auth):
        if request.headers.getlist("X-Forwarded-For"):
            ip = request.headers.getlist("X-Forwarded-For")[0]
        else:
            ip = request.remote_addr
        logging.info("auth header not provided, probable malicious access attempt from IP: {}".format(ip))
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

        if message['sender_id'] == BOT_ID_TWITTER:
            logging.info("Message from bot ignored.")
            return '', HTTPStatus.OK

        user_info = api.get_user(message['sender_id'])
        message['sender_screen_name'] = user_info.screen_name
        message['dm_id'] = dm_object.get('id')
        message['text'] = message_object.get('message_data', {}).get('text')
        message['dm_array'] = message['text'].split(" ")
        message['dm_action'] = message['dm_array'][0].lower()
        modules.social.get_language(message)

        logging.info("Processing direct message.")

        # Update DB with new DM
        dm_insert_call = ("INSERT INTO dm_list (dm_id, processed, sender_id, dm_text) "
                          "VALUES (%s, 0, %s, %s)")
        dm_insert_values = [message['dm_id'], message['sender_id'], message['text']]
        err = modules.db.set_db_data(dm_insert_call, dm_insert_values)
        if err is not None:
            return 'ok'

        logging.info("{}: action identified: {}".format(datetime.now(), message['dm_action']))
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

        message = modules.social.set_message_info(tweet_object, message)
        if message['id'] is None:
            return '', HTTPStatus.OK

        message = modules.social.check_message_action(message)
        if message['action'] is None:
            logging.info("{}: Mention of nano tip bot without a !tip command.".format(datetime.now()))
            return '', HTTPStatus.OK

        message = modules.social.validate_tip_amount(message)
        if message['tip_amount'] <= 0:
            return '', HTTPStatus.OK

        if message['action'] != -1 and str(message['sender_id']) != str(BOT_ID_TWITTER):
            new_pid = os.fork()
            if new_pid == 0:
                try:
                    bot_status = config.get('webhooks', 'bot_status')
                    if bot_status == 'maintenance':
                        modules.social.send_dm(message['sender_id'],
                                               translations.maintenance_text[message['language']],
                                               message['system'])
                    else:
                        api.create_favorite(message['id'])
                        modules.orchestration.tip_process(message, users_to_tip, request_json)
                except Exception as e:
                    logging.info("Exception: {}".format(e))
                    raise e

                os._exit(0)
            else:
                return '', HTTPStatus.OK

        elif str(message['sender_id']) == str(BOT_ID_TWITTER):
            logging.info("{}: TipBot sent a message.".format(datetime.now()))

        return '', HTTPStatus.OK

    elif 'follow_events' in request_json.keys():
        """
        New user followed the bot.  Send a welcome message.
        """
        logging.info("{}: New user followed, sending help message.".format(datetime.now()))
        request_json = request.get_json()
        follow_object = request_json['follow_events'][0]
        follow_source = follow_object.get('source', {})
        message['sender_id'] = follow_source.get('id')

        modules.orchestration.help_process(message)

        return '', HTTPStatus.OK

    else:
        # Event type not supported
        return '', HTTPStatus.OK


if __name__ == "__main__":
    modules.db.db_init()
    modules.social.telegram_set_webhook()
    app.run(host='0.0.0.0')
