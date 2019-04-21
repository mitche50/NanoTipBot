import configparser
import json
import logging
import os
import re
from datetime import datetime
from decimal import Decimal

import nano
import requests
import telegram
import tweepy
from TwitterAPI import TwitterAPI

import modules.db
import modules.social
import modules.translations as translations

# Set Log File
logging.basicConfig(handlers=[logging.FileHandler('{}/webhooks.log'.format(os.getcwd()), 'a', 'utf-8')],
                    level=logging.INFO)

# Read config and parse constants
config = configparser.ConfigParser()
config.read('{}/webhookconfig.ini'.format(os.getcwd()))

# Check the currency of the bot
CURRENCY = config.get('main', 'currency')

# Constants
WALLET = config.get(CURRENCY, 'wallet')
NODE_IP = config.get(CURRENCY, 'node_ip')
WORK_SERVER = config.get(CURRENCY, 'work_server')
WORK_KEY = config.get(CURRENCY, 'work_key')
RE_EMOJI = re.compile('[\U00010000-\U0010ffff\U000026A1]', flags=re.UNICODE)
TELEGRAM_KEY = config.get(CURRENCY, 'telegram_key')
URL = config.get('routes', '{}_url'.format(CURRENCY))
CONVERT_MULTIPLIER = {
    'nano': 1000000000000000000000000000000,
    'banano': 100000000000000000000000000000
}

# Twitter API connection settings
CONSUMER_KEY = config.get(CURRENCY, 'consumer_key')
CONSUMER_SECRET = config.get(CURRENCY, 'consumer_secret')
ACCESS_TOKEN = config.get(CURRENCY, 'access_token')
ACCESS_TOKEN_SECRET = config.get(CURRENCY, 'access_token_secret')

# Connect to Nano node
rpc = nano.rpc.Client(NODE_IP)

# Connect to Telegram
if TELEGRAM_KEY != 'none':
    telegram_bot = telegram.Bot(token=TELEGRAM_KEY)

# Connect to Twitter
auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
api = tweepy.API(auth)

# Secondary API for non-tweepy supported requests
twitterAPI = TwitterAPI(CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)


def receive_pending(sender_account):
    """
    Check to see if the account has any pending blocks and process them
    """
    try:
        logging.info("{}: in receive pending".format(datetime.now()))
        pending_blocks = rpc.pending(account='{}'.format(sender_account))
        logging.info("pending blocks: {}".format(pending_blocks))
        if len(pending_blocks) > 0:
            try:
                for block in pending_blocks:
                    work = get_pow(sender_account)
                    if work == '':
                        logging.info("{}: processing without pow".format(datetime.now()))
                        receive_data = {'action': "receive", 'wallet': WALLET, 'account': sender_account,
                                        'block': block}
                    else:
                        logging.info("{}: processing with pow".format(datetime.now()))
                        receive_data = {'action': "receive", 'wallet': WALLET, 'account': sender_account,
                                        'block': block, 'work': work}
                    receive_json = json.dumps(receive_data)
                    requests.post('{}'.format(NODE_IP), data=receive_json)
                    logging.info("{}: block {} received".format(datetime.now(), block))
            except Exception as e:
                logging.info("Exception: {}".format(e))
                raise e
    except Exception as e:
        logging.info("Receive Pending Error: {}".format(e))
        raise e

    return


def get_pow(sender_account):
    """
    Retrieves the frontier (hash of previous transaction) of the provided account and generates work for the next block.
    """
    logging.info("{}: in get_pow".format(datetime.now()))
    try:
        account_info = rpc.account_info(account="{}".format(sender_account))
        hash = account_info['frontier']
        logging.info("{}: account: {} - frontier: {}".format(datetime.now(), sender_account, hash))
    except Exception as e:
        logging.info("{}: Error checking frontier: {}".format(datetime.now(), e))
        return ''

    work = ''
    try:
        if CURRENCY == 'nano':
            work_data = {'hash': hash, 'key': WORK_KEY, 'account': sender_account}
        else:
            work_data = {'action': 'work_generate', 'hash': hash}
        json_request = json.dumps(work_data)
        r = requests.post('{}'.format(WORK_SERVER), data=json_request)
        rx = r.json()
        if 'work' in rx.keys():
            work = rx['work']
            logging.info("{}: Work generated: {}".format(datetime.now(), work))
    except Exception as e:
        logging.info("{}: ERROR GENERATING WORK: {}".format(datetime.now(), e))
        pass

    return work


def send_tip(message, users_to_tip, tip_index):
    """
    Process tip for specified user
    """
    bot_status = config.get('main', 'bot_status')
    if bot_status == 'maintenance':
        modules.social.send_dm(message['sender_id'], translations.maintenance_text[message['language']],
                               message['system'])
        return
    else:
        logging.info("{}: sending tip to {}".format(datetime.now(), users_to_tip[tip_index]['receiver_screen_name']))
        if str(users_to_tip[tip_index]['receiver_id']) == str(message['sender_id']):
            modules.social.send_reply(message,
                                      translations.self_tip_text[message['language']].format(CURRENCY.upper()))

            logging.info("{}: User tried to tip themself").format(datetime.now())
            return

        # Check if the receiver has an account
        receiver_account_get = ("SELECT account FROM users where user_id = {} and users.system = '{}'"
                                .format(int(users_to_tip[tip_index]['receiver_id']), message['system']))
        receiver_account_data = modules.db.get_db_data(receiver_account_get)

        # If they don't, check reserve accounts and assign one.
        if not receiver_account_data:
            users_to_tip[tip_index]['receiver_account'] = modules.db.get_spare_account()
            create_receiver_account = ("INSERT INTO users (user_id, system, user_name, account, register) "
                                       "VALUES(%s, %s, %s, %s, 0)")
            create_receiver_account_values = [users_to_tip[tip_index]['receiver_id'], message['system'],
                                              users_to_tip[tip_index]['receiver_screen_name'],
                                              users_to_tip[tip_index]['receiver_account']]
            modules.db.set_db_data(create_receiver_account, create_receiver_account_values)
            logging.info("{}: Sender sent to a new receiving account.  Created  account {}"
                         .format(datetime.now(), users_to_tip[tip_index]['receiver_account']))

        else:
            users_to_tip[tip_index]['receiver_account'] = receiver_account_data[0][0]

        # Send the tip
        message['tip_id'] = "{}{}".format(message['id'], tip_index)

        work = get_pow(message['sender_account'])
        logging.info("Sending Tip:")
        logging.info("From: {}".format(message['sender_account']))
        logging.info("To: {}".format(users_to_tip[tip_index]['receiver_account']))
        logging.info("amount: {:f}".format(message['tip_amount_raw']))
        logging.info("id: {}".format(message['tip_id']))
        logging.info("work: {}".format(work))
        if work == '':
            logging.info("{}: processed without work".format(datetime.now()))
            message['send_hash'] = rpc.send(wallet="{}".format(WALLET), source="{}".format(message['sender_account']),
                                            destination="{}".format(users_to_tip[tip_index]['receiver_account']),
                                            amount="{}".format(int(message['tip_amount_raw'])),
                                            id="tip-{}".format(message['tip_id']))
        else:
            logging.info("{}: processed with work: {}".format(datetime.now(), work))
            message['send_hash'] = rpc.send(wallet="{}".format(WALLET), source="{}".format(message['sender_account']),
                                            destination="{}".format(users_to_tip[tip_index]['receiver_account']),
                                            amount="{}".format(int(message['tip_amount_raw'])),
                                            work=work,
                                            id="tip-{}".format(message['tip_id']))
        # Update the DB
        message['text'] = strip_emoji(message['text'])
        modules.db.set_db_data_tip(message, users_to_tip, tip_index)

        # Get receiver's new balance
        try:
            logging.info("{}: Checking to receive new tip")

            receive_pending(users_to_tip[tip_index]['receiver_account'])
            balance_return = rpc.account_balance(account="{}".format(users_to_tip[tip_index]['receiver_account']))
            users_to_tip[tip_index]['balance'] = balance_return['balance'] / CONVERT_MULTIPLIER[CURRENCY]
            # create a string to remove scientific notation from small decimal tips
            if str(users_to_tip[tip_index]['balance'])[0] == ".":
                users_to_tip[tip_index]['balance'] = "0{}".format(str(users_to_tip[tip_index]['balance']))
            else:
                users_to_tip[tip_index]['balance'] = str(users_to_tip[tip_index]['balance'])

            # Send a DM to the receiver
            modules.social.send_dm(users_to_tip[tip_index]['receiver_id'],
                                   translations.receiver_tip_text[users_to_tip[tip_index]['receiver_language']]
                                   .format(message['sender_screen_name'], message['tip_amount_text'],
                                           CURRENCY.upper(), CURRENCY.upper(), URL), message['system'])

        except Exception as e:
            logging.info("{}: ERROR IN RECEIVING NEW TIP - POSSIBLE NEW ACCOUNT NOT REGISTERED WITH DPOW: {}"
                         .format(datetime.now(), e))

        logging.info(
            "{}: tip sent to {} via hash {}".format(datetime.now(), users_to_tip[tip_index]['receiver_screen_name'],
                                                    message['send_hash']))


def get_energy(nano_energy):
    """
    Calculate the total energy used by Nano at time of loading the webpage.
    """
    block_count_get = rpc.block_count()
    checked_blocks = block_count_get['count']

    total_energy = checked_blocks * nano_energy

    return total_energy, checked_blocks


def strip_emoji(text):
    """
    Remove Emojis from tweet text to prevent issues with logging
    """
    logging.info('{}: removing emojis'.format(datetime.now()))
    text = str(text)
    return RE_EMOJI.sub(r'', text)


def get_fiat_conversion(fiat, crypto_currency, fiat_amount):
    """
    Get the current fiat price conversion for the provided fiat:crypto pair
    """
    fiat = fiat.upper()
    crypto_currency = crypto_currency.upper()
    post_url = 'https://min-api.cryptocompare.com/data/price?fsym={}&tsyms={}'.format(crypto_currency, fiat)
    try:
        # Retrieve price conversion from API
        response = requests.get(post_url)
        response_json = json.loads(response.text)
        price = Decimal(response_json['{}'.format(fiat)])
        # Find value of 0.01 in the retrieved crypto
        penny_value = Decimal(0.01) / price
        # Find precise amount of the fiat amount in crypto
        precision = 1
        crypto_value = Decimal(fiat_amount) / price
        # Find the precision of 0.01 in crypto
        crypto_convert = precision * penny_value
        while Decimal(crypto_convert) < 1:
            precision *= 10
            crypto_convert = precision * penny_value
        # Round the expected amount to the nearest 0.01
        temp_convert = crypto_value * precision
        temp_convert = str(round(temp_convert))
        final_convert = Decimal(temp_convert) / Decimal(str(precision))

        return final_convert
    except Exception as e:
        logging.info("{}: Exception converting fiat price to crypto price".format(datetime.now()))
        logging.info("{}: {}".format(datetime.now(), e))
        raise e


def get_fiat_price(fiat, crypto_currency):
    fiat = fiat.upper()
    crypto_currency = crypto_currency.upper()
    post_url = 'https://min-api.cryptocompare.com/data/price?fsym={}&tsyms={}'.format(crypto_currency, fiat)
    try:
        # Retrieve price conversion from API
        response = requests.get(post_url)
        response_json = json.loads(response.text)
        price = response_json['{}'.format(fiat)]

        return price
    except Exception as e:
        logging.info("{}: Exception converting fiat price to crypto price".format(datetime.now()))
        logging.info("{}: {}".format(datetime.now(), e))
        raise e


def generate_accounts():
    accounts = rpc.accounts_create(wallet=WALLET, count=50, work=False)
    if CURRENCY == 'nano':
        logging.info("{}: providing accounts to dpow for precaching.".format(datetime.now()))
        work_data = {'accounts': accounts, 'key': WORK_KEY}
        json_request = json.dumps(work_data)
        r = requests.post('{}'.format(WORK_SERVER), data=json_request)
        rx = r.json()
        logging.info("{}: return from dpow: {}".format(datetime.now(), rx))

    return accounts
