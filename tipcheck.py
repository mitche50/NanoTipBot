#!/usr/bin/env python3

# DEPENDENCIES =========================================
from datetime import datetime
from decimal import Decimal

import configparser
import json
import logging
import nano
import os
import requests
import telegram
import tweepy
from TwitterAPI import TwitterAPI

from modules.currency import get_pow, receive_pending
from modules.db import get_db_data, set_db_data
from modules.social import send_dm

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


# Connect to Twitter
auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
api = tweepy.API(auth)
# Secondary API for non-tweepy supported requests
twitterAPI = TwitterAPI(CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)

# Connect to Nano Node
rpc = nano.rpc.Client(NODE_IP)

# Connect to Telegram
telegram_bot = telegram.Bot(token=TELEGRAM_KEY)

# Set Log File
logging.basicConfig(handlers=[logging.FileHandler('{}/tipreturn.log'.format(os.getcwd()), 'a', 'utf-8')],
                    level=logging.INFO)


def unregistered_user_reminder(day_difference, dm_text):
    """
    Check for unregistered users day_difference away from the current day and send a DM with the provided dm_text
    """
    db_call = ("SELECT user_id, system "
               "FROM users "
               "WHERE register = 0 "
               "AND DATE(created_ts) BETWEEN DATE_SUB(NOW(), INTERVAL {} DAY) "
               "AND DATE_SUB(NOW(), INTERVAL {} DAY)").format(day_difference, (day_difference - 1))
    try:
        unregistered_users = get_db_data(db_call)
    except Exception as e:
        logging.info(e)
        raise e
    logging.info("unregistered_users: {}".format(unregistered_users))

    for user in unregistered_users:
        try:
            send_dm(user[0], dm_text, user[1])
            logging.info("{}: User {} reminded after {} days.".format(str(datetime.now()), user[0], day_difference))
        except tweepy.TweepError as e:
            logging.info("{}: Tweepy Error: {}".format(datetime.now(), e))
        except Exception as e:
            logging.info("{}: Exception: {}".format(datetime.now(), e))
            raise e


def send_returned_notice_to_receivers():
    """
    Notify all unregistered users that their tips are being returned.
    """
    unregistered_users_call = ("SELECT DISTINCT tip_list.receiver_id, tip_list.system FROM tip_list "
                               "INNER JOIN users "
                               "ON tip_list.receiver_id = users.user_id AND tip_list.system = users.system "
                               "WHERE DATE(tip_list.timestamp) < DATE_SUB(now(), interval 30 day) "
                               "AND users.register = 0 "
                               "AND tip_list.processed = 9;")
    unregistered_users_data = get_db_data(unregistered_users_call)

    # for user in unregistered_users_data:
    #     send_dm(user[0], "You had tips that were sent 30 or more days ago, and you haven't registered your account. "
    #                      "These tips were returned to the sender so they can continue to spread {} to others. "
    #                      "If you would like to keep any future tips, please register to prevent any more returns!"
    #             .format(CURRENCY.title()),
    #             user[1])

    mark_notified("receivers")


def mark_notified(user_type):
    """
    Set the DB to show that the receivers were identified.
    """

    if user_type == 'receivers':
        processed_num = 9
    else:
        processed_num = 8

    notified_users_call = ("SELECT dm_id "
                           "FROM tip_list "
                           "WHERE processed = {}".format(processed_num))
    notified_users = get_db_data(notified_users_call)

    for id in notified_users:
        notified_send_call = ("UPDATE tip_list "
                              "SET processed = %s "
                              "WHERE dm_id = %s")
        notified_send_values = [(processed_num - 1), id[0]]
        set_db_data(notified_send_call, notified_send_values)


def send_returned_notice_to_senders():
    """
    Notify all users who sent tips which were returned that their balance has been updated.
    """
    sender_return_notice_call = ("SELECT tip_list.sender_id, tip_list.system, sum(tip_list.amount) "
                                 "FROM tip_list "
                                 "INNER JOIN users "
                                 "ON tip_list.receiver_id = users.user_id AND tip_list.system = users.system "
                                 "WHERE DATE(tip_list.timestamp) < DATE_SUB(now(), interval 30 day) "
                                 "AND users.register = 0 "
                                 "AND tip_list.processed = 8 "
                                 "GROUP BY tip_list.sender_id, tip_list.system;")
    sender_return_list = get_db_data(sender_return_notice_call)

    sender_return_names = ("SELECT tip_list.sender_id, tip_list.system, users.user_name "
                           "FROM tip_list "
                           "INNER JOIN users "
                           "ON tip_list.receiver_id = users.user_id AND tip_list.system = users.system "
                           "WHERE DATE(tip_list.timestamp) < DATE_SUB(now(), interval 30 day) "
                           "AND users.register = 0 "
                           "AND tip_list.processed = 8;")
    sender_return_name_list = get_db_data(sender_return_names)
    return_dict = {}

    for sender in sender_return_name_list:
        sender_comp = str(sender[0]) + "-" + str(sender[1])
        if sender_comp not in return_dict.keys():
            return_dict[sender_comp] = [sender[2]]
        else:
            return_dict[sender_comp].append(sender[2])

    # for sender in sender_return_list:
    #     donation_amount, send_amount = calculate_donation_amount(sender[2], sender[0], sender[1])
    #     sender_comp = str(sender[0]) + "-" + str(sender[1])
    #     logging.info("send amount in Nano = {}".format(Decimal(str(send_amount / CONVERT_MULTIPLIER[CURRENCY]))))
    #     send_dm(sender[0], "You've had tips returned to your account due to the following list of users "
    #                        "not registering: {}.  Your account has been credited {} {}.  Continue spreading the "
    #                        "love or withdraw to your wallet!".format(return_dict[sender_comp],
    #                                                                  Decimal(str(send_amount / CONVERT_MULTIPLIER[CURRENCY])),
    #                                                                  CURRENCY.upper()),
    #             sender[1])

    mark_notified("senders")


def calculate_donation_amount(amount, sender_id, system):
    donation_call = ("SELECT donation_percent FROM donation_info "
                     "WHERE user_id = {} AND system = '{}'").format(sender_id, system)
    logging.info("{}: donation amount check call: {}".format(datetime.now(), donation_call))
    donation_raw = get_db_data(donation_call)
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
        donation = 0
        donation_amount = 0
        send_amount = int(amount * CONVERT_MULTIPLIER[CURRENCY])

    return donation_amount, send_amount


def return_tips():
    tips_to_return_call = ("SELECT tip_list.dm_id, tip_list.sender_id, "
                           "users.account, tip_list.amount, tip_list.system "
                           "FROM tip_list "
                           "INNER JOIN users "
                           "ON tip_list.receiver_id = users.user_id AND tip_list.system = users.system "
                           "WHERE DATE(tip_list.timestamp) < DATE_SUB(now(), interval 30 day) "
                           "AND users.register = 0 "
                           "AND tip_list.processed = 2;")
    tip_list = get_db_data(tips_to_return_call)

    for tip in tip_list:
        transaction_id = tip[0]
        sender_id = tip[1]
        receiver_account = tip[2]
        amount = Decimal(str(tip[3]))
        system = tip[4]

        logging.info("{}: Returning tip {}".format(datetime.now(), transaction_id))

        sender_account_call = "SELECT account FROM users WHERE user_id = {} AND system = '{}'".format(sender_id, system)
        sender_account_info = get_db_data(sender_account_call)
        sender_account = sender_account_info[0][0]

        donation_amount, send_amount = calculate_donation_amount(amount, sender_id, system)
        logging.info("donation amount: {}".format(donation_amount))
        logging.info("send_amount: {} - {}".format(amount, send_amount))

        receive_pending(receiver_account)

        work = get_pow(receiver_account)
        try:
            if work == '':
                send_hash = rpc.send(wallet="{}".format(WALLET), source="{}".format(receiver_account),
                                     destination="{}".format(sender_account), amount=send_amount)
                if donation_amount > 0:
                    donation_hash = rpc.send(wallet="{}".format(WALLET), source="{}".format(receiver_account),
                                             destination="{}".format(BOT_ACCOUNT), amount=donation_amount)
                    logging.info("{}: Donation sent from account {} under hash: {}".format(datetime.now(), receiver_account,
                                                                                           donation_hash))
            else:
                send_hash = rpc.send(wallet="{}".format(WALLET), source="{}".format(receiver_account),
                                     destination="{}".format(sender_account), amount=send_amount, work=work)
                if donation_amount > 0:
                    donation_work = get_pow(receiver_account)
                    donation_hash = rpc.send(wallet="{}".format(WALLET), source="{}".format(receiver_account),
                                             destination="{}".format(BOT_ACCOUNT), amount=donation_amount, work=donation_work)
                    logging.info("{}: Donation sent from account {} under hash: {}".format(datetime.now(), receiver_account,
                                                                                           donation_hash))

            logging.info("{}: Tip returned under hash: {}".format(str(datetime.now()), send_hash))
        except nano.rpc.RPCException as e:
            logging.info("{}: Insufficient balance to return {} raw and {} donation from account {}.  Descriptive error: {}".format(datetime.now(),
                                                                                                                                    send_amount,
                                                                                                                                    donation_amount,
                                                                                                                                    receiver_account,
                                                                                                                                    e))
            insufficient_balance_check = rpc.account_balance(receiver_account)
            logging.info("Current balance: {}".format(insufficient_balance_check))
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

    send_returned_notice_to_receivers()
    send_returned_notice_to_senders()


def return_unused_balance():
    get_inactive_users = ("SELECT user_id, system, account "
                          " FROM tip_bot.return_address "
                          " WHERE last_action < DATE_SUB(now(), interval 60 day) "
                          "     AND account IS NOT NULL;")
    inactive_users = get_db_data(get_inactive_users)
    logging.info("{}: Returning inactive balances for user list: {}".format(datetime.now(), inactive_users))

    for user in inactive_users:
        get_tip_account = ("SELECT account FROM users "
                           "WHERE user_id = {} AND system = '{}'".format(user[0], user[1]))
        tip_account_data = get_db_data(get_tip_account)
        tip_account = tip_account_data[0][0]
        print("Returning unused balance for user {} system {} account {} to ")
        # check for any unreceived tips
        receive_pending(tip_account)
        # get balance of tip account
        balance_data = {'action': 'account_balance', 'account': tip_account}
        json_request = json.dumps(balance_data)
        r = requests.post('{}'.format(NODE_IP), data=json_request)
        rx = r.json()
        balance_raw = rx['balance']
        balance = Decimal(balance_raw) / CONVERT_MULTIPLIER[CURRENCY]
        # send from tip account to return account
        if Decimal(balance) > 0:
            donation_amount, send_amount = calculate_donation_amount(Decimal(balance), user[0], user[1])
            work = get_pow(tip_account)
            donation_hash = rpc.send(wallet=WALLET, source=tip_account, destination=BOT_ACCOUNT, work=work, amount=donation_amount)
            work = get_pow(tip_account)
            inactive_hash = rpc.send(wallet=WALLET, source=tip_account, destination=user[2], work=work, amount=send_amount)
            logging.info(
                "{}: Inactive user {} on {} had their funds returned to their recovery address {} under hash {}".format(
                    datetime.now(),
                    user[0],
                    user[1],
                    user[2],
                    inactive_hash))
            logging.info(
                "{}: Inactive user {} on {} donated under hash {}".format(
                    datetime.now(),
                    user[0],
                    user[1],
                    user[2],
                    donation_hash))
        else:
            logging.info("{}: Balance for user {} on {} was 0".format(datetime.now(), user[0], user[1]))


def main():
    # Check for users who need reminders - removed to prevent suspension in the future.
    # unregistered_user_reminder(int(10), "Just a reminder that someone sent you a tip and you haven't registered your account yet!  Reply to this message with !register to do so, then !help to see all my commands!")
    # unregistered_user_reminder(int(20), "You still have not registered your account.  If you do not register within 30 days, your tip will be returned.  Please respond with !register to complete your registration, or !help to see my commands!")
    # unregistered_user_reminder(int(29), "This is your final notice!  If you do not register your account before tomorrow, your tips will be sent back to the users that tipped you!")

    # Send back the tip to users not registered in 30 days
    return_tips()

    logging.info("{}: completed check for unregistered users.".format(datetime.now()))

    return_unused_balance()


main()
