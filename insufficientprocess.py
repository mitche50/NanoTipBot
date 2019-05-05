#!/usr/bin/env python3

# DEPENDENCIES =========================================
from datetime import datetime
from decimal import Decimal
from TwitterAPI import TwitterAPI
import telegram
from modules.db import get_db_data, set_db_data
from modules.social import send_dm
from modules.currency import get_pow, receive_pending

import nano, tweepy, configparser, logging, os

# CONFIG CONSTANTS =====================================
# Read config and parse constants
config = configparser.ConfigParser()
config.read('{}/webhookconfig.ini'.format(os.getcwd()))

CURRENCY = config.get('main', 'currency')
CONVERT_MULTIPLIER = {
    'nano': 1000000000000000000000000000000,
    'banano': 100000000000000000000000000000
}

CONSUMER_KEY = config.get(CURRENCY, 'consumer_key')
CONSUMER_SECRET = config.get(CURRENCY, 'consumer_secret')
ACCESS_TOKEN = config.get(CURRENCY, 'access_token')
ACCESS_TOKEN_SECRET = config.get(CURRENCY, 'access_token_secret')
DB_HOST = config.get('main', 'host')
DB_USER = config.get('main', 'user')
DB_PW = config.get('main', 'password')
DB_SCHEMA = config.get(CURRENCY, 'schema')
WALLET = config.get(CURRENCY, 'wallet')
NODE_IP = config.get(CURRENCY, 'node_ip')
BOT_ACCOUNT = config.get(CURRENCY, 'bot_account')
WORK_SERVER = config.get(CURRENCY, 'work_server')
WORK_KEY = config.get(CURRENCY, 'work_key')
TELEGRAM_KEY = config.get(CURRENCY, 'telegram_key')
MIN_TIP = config.get(CURRENCY, 'min_tip')

# Connect to Nano Node
rpc = nano.rpc.Client(NODE_IP)

# Set Log File
logging.basicConfig(handlers=[logging.FileHandler('{}/tipreturn.log'.format(os.getcwd()), 'a', 'utf-8')],
                    level=logging.INFO)

def calculate_donation_amount(amount, sender_id, system):
    donation_raw = get_db_data("SELECT donation_percent FROM donation_info "
                               "WHERE user_id = {} AND system = '{}'".format(sender_id, system))
    donation_percent = Decimal(str(donation_raw[0][0] * .01))

    if amount * donation_percent >= float(MIN_TIP):
        donation = amount * donation_percent
        if CURRENCY == 'banano':
            donation = round(donation)
        else:
            donation = round(donation, 5)

        amount -= donation
        donation_amount = int(donation * CONVERT_MULTIPLIER[CURRENCY])
        send_amount = int(amount * CONVERT_MULTIPLIER[CURRENCY])
    else:
        donation_amount = 0
        send_amount = int(amount * CONVERT_MULTIPLIER[CURRENCY])

    return donation_amount, send_amount


def return_tips():
    tips_to_return_call = ("SELECT tip_list.dm_id, tip_list.amount, users.account, tip_list.sender_id, tip_list.system "
                           "FROM tip_bot.tip_list "
                           "INNER JOIN users ON tip_list.receiver_id = users.user_id AND tip_list.system = users.system "
                           "WHERE processed = 6;")
    tip_list = get_db_data(tips_to_return_call)

    for tip in tip_list:
        transaction_id = tip[0]
        sender_id = tip[3]
        receiver_account = tip[2]
        amount = Decimal(str(tip[1]))
        system = tip[4]

        logging.info("{}: Returning tip {}".format(datetime.now(), transaction_id))

        donation_amount, send_amount = calculate_donation_amount(amount, sender_id, system)
        logging.info("donation amount: {}".format(donation_amount))
        logging.info("send_amount: {} - {}".format(amount, send_amount))

        receive_pending(receiver_account)

        work = get_pow(receiver_account)
        try:
            if work == '':
                if donation_amount > 0:
                    donation_hash = rpc.send(wallet="{}".format(WALLET), source="{}".format(receiver_account),
                                             destination="{}".format(BOT_ACCOUNT), amount=donation_amount)
                    logging.info("{}: Donation sent from account {} under hash: {}".format(datetime.now(), receiver_account,
                                                                                           donation_hash))
            else:
                if donation_amount > 0:
                    donation_hash = rpc.send(wallet="{}".format(WALLET), source="{}".format(receiver_account),
                                             destination="{}".format(BOT_ACCOUNT), amount="{}".format(donation_amount), work=work)
                    logging.info("{}: Donation sent from account {} under hash: {}".format(datetime.now(), receiver_account,
                                                                                           donation_hash))

        except nano.rpc.RPCException as e:
            logging.info("{}: Insufficient balance to return {} raw and {} donation from account {}.  Descriptive error: {}".format(datetime.now(),
                                                                                                                                    send_amount,
                                                                                                                                    donation_amount,
                                                                                                                                    receiver_account,
                                                                                                                                    e))
            insufficient_balance_check = rpc.account_balance(receiver_account)
            logging.info("Current balance: {}".format(insufficient_balance_check))
            if int(insufficient_balance_check['balance']) == 0:
                insufficient_balance_call = ("UPDATE tip_list "
                                             "SET processed = 9 "
                                             "WHERE dm_id = %s;")
            else:
                insufficient_balance_call = ("UPDATE tip_list "
                                             "SET processed = 6 "
                                             "WHERE dm_id = %s;")

            insufficient_balance_values = [transaction_id,]
            set_db_data(insufficient_balance_call, insufficient_balance_values)
            continue
        except Exception as f:
            logging.info("{}: Unexpected error: {}".format(datetime.now(), f))
            continue

        update_tip_call = ("UPDATE tip_list "
                           "SET processed = 9 "
                           "WHERE dm_id = %s;")
        update_tip_values = [transaction_id,]
        try:
            set_db_data(update_tip_call, update_tip_values)
        except Exception as e:
            logging.info("{}: Error updating tip to returned: {}".format(datetime.now(), e))


logging.info("handling insufficient tips")
return_tips()
