#!/usr/bin/env python3

# DEPENDENCIES =========================================
from datetime import datetime
from decimal import Decimal
from TwitterAPI import TwitterAPI
import telegram
from nano import convert
from modules.db import get_db_data, set_db_data
from modules.social import send_dm
from modules.currency import get_pow

import MySQLdb, re, requests, nano, tweepy, configparser, logging, json

# CONFIG CONSTANTS =====================================
config = configparser.ConfigParser()
config.read('webhookconfig.ini')

CONSUMER_KEY = config.get('webhooks', 'consumer_key')
CONSUMER_SECRET = config.get('webhooks', 'consumer_secret')
ACCESS_TOKEN = config.get('webhooks', 'access_token')
ACCESS_TOKEN_SECRET = config.get('webhooks', 'access_token_secret')
DB_HOST = config.get('webhooks', 'host')
DB_USER = config.get('webhooks', 'user')
DB_PW = config.get('webhooks', 'password')
DB_SCHEMA = config.get('webhooks', 'schema')
WALLET = config.get('webhooks', 'wallet')
NODE_IP = config.get('webhooks', 'node_ip')
BOT_ACCOUNT = config.get('webhooks', 'bot_account')
WORK_SERVER = config.get('webhooks', 'work_server')
WORK_KEY = config.get('webhooks', 'work_key')
TELEGRAM_KEY = config.get('webhooks', 'telegram_key')


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
logging.basicConfig(handlers=[logging.FileHandler('/root/webhooks/unregistered.log', 'a', 'utf-8')],
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
    unregistered_users_call = ("SELECT DISTINCT tip_bot.tip_list.receiver_id, tip_bot.tip_list.system FROM tip_bot.tip_list "
                               "INNER JOIN tip_bot.users "
                               "ON tip_bot.tip_list.receiver_id = tip_bot.users.user_id "
                               "WHERE DATE(tip_bot.tip_list.timestamp) < DATE_SUB(now(), interval 1 month) "
                               "AND tip_bot.users.register = 0 "
                               "AND tip_bot.tip_list.processed = 9;")
    unregistered_users_data = get_db_data(unregistered_users_call)

    for user in unregistered_users_data:
        send_dm(user[0], "You had tips that were sent 30 or more days ago, and you haven't registered your account. "
                         "These tips were returned to the sender so they can continue to spread Nano to others. "
                         "If you would like to keep any future tips, please register to prevent any more returns!",
                user[1])

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
                           "FROM tip_bot.tip_list "
                           "WHERE processed = {}".format(processed_num))
    notified_users = get_db_data(notified_users_call)

    for id in notified_users:
        notified_send_call = ("UPDATE tip_bot.tip_list "
                              "SET processed = %s "
                              "WHERE dm_id = %s")
        notified_send_values = [(processed_num - 1), id[0]]
        set_db_data(notified_send_call, notified_send_values)



def send_returned_notice_to_senders():
    """
    Notify all users who sent tips which were returned that their balance has been updated.
    """
    sender_return_notice_call = ("SELECT tip_bot.tip_list.sender_id, tip_bot.tip_list.system, sum(tip_bot.tip_list.amount) "
                                 "FROM tip_bot.tip_list "
                                 "INNER JOIN tip_bot.users "
                                 "ON tip_bot.tip_list.receiver_id = tip_bot.users.user_id "
                                 "WHERE DATE(tip_bot.tip_list.timestamp) < DATE_SUB(now(), interval 1 month) "
                                 "AND tip_bot.users.register = 0 "
                                 "AND tip_bot.tip_list.processed = 8 "
                                 "GROUP BY tip_bot.tip_list.sender_id, tip_bot.tip_list.system;")
    sender_return_list = get_db_data(sender_return_notice_call)

    for sender in sender_return_list:
        send_dm(sender[0], "You've had tips returned to your account due to unregistered users.  Your account has been "
                           "credited {} NANO.  Continue spreading the love or withdraw to your wallet!".format(sender[2]),
                sender[1])

    mark_notified("senders")


def return_tips():
    tips_to_return_call = ("SELECT tip_bot.tip_list.dm_id, tip_bot.tip_list.sender_id, "
                           "tip_bot.users.account, tip_bot.tip_list.amount "
                           "FROM tip_bot.tip_list "
                           "INNER JOIN tip_bot.users "
                           "ON tip_bot.tip_list.receiver_id = tip_bot.users.user_id "
                           "WHERE DATE(tip_bot.tip_list.timestamp) < DATE_SUB(now(), interval 1 month) "
                           "AND tip_bot.users.register = 0 "
                           "AND tip_bot.tip_list.processed = 2;")
    tip_list = get_db_data(tips_to_return_call)

    for tip in tip_list:
        transaction_id = tip[0]
        sender_id = tip[1]
        receiver_account = tip[2]
        amount = Decimal(tip[3])

        logging.info("{}: Returning tip {}".format(datetime.now(), transaction_id))

        sender_account_call = "SELECT account FROM users WHERE user_id = {}".format(sender_id)
        sender_account_info = get_db_data(sender_account_call)
        sender_account = sender_account_info[0][0]
        send_amount = int(amount * 1000000000000000000000000000000)

        work = get_pow(receiver_account)
        try:
            if work == '':
                send_hash = rpc.send(wallet="{}".format(WALLET), source="{}".format(receiver_account),
                                     destination="{}".format(sender_account), amount=send_amount)
            else:
                send_hash = rpc.send(wallet="{}".format(WALLET), source="{}".format(receiver_account),
                                     destination="{}".format(sender_account), amount=send_amount, work=work)
            logging.info("{}: Tip returned under hash: {}".format(str(datetime.now()), send_hash))
        except nano.rpc.RPCException as e:
            logging.info("{}: Insufficient balance to return.  Descriptive error: {}".format(datetime.now(), e))
            insufficient_balance_call = ("UPDATE tip_bot.tip_list "
                                       "SET processed = 6 "
                                       "WHERE dm_id = %s;")
            insufficient_balance_values = [transaction_id,]
            set_db_data(insufficient_balance_call, insufficient_balance_values)
        except Exception as f:
            logging.info("{}: Unexpected error: {}".format(datetime.now(), f))

        update_tip_call = ("UPDATE tip_bot.tip_list "
                           "SET processed = 9 "
                           "WHERE dm_id = %s;")
        update_tip_values = [transaction_id,]
        try:
            set_db_data(update_tip_call, update_tip_values)
        except Exception as e:
            logging.info("{}: Error updating tip to returned: {}".format(datetime.now(), e))

    send_returned_notice_to_receivers()
    send_returned_notice_to_senders()


def main():
    # Check for users who need reminders
    unregistered_user_reminder(int(10), "Just a reminder that someone sent you a tip and you haven't registered your account yet!  Reply to this message with !register to do so, then !help to see all my commands!")
    unregistered_user_reminder(int(20), "You still have not registered your account.  If you do not register within 30 days, your tip will be returned.  Please respond with !register to complete your registration, or !help to see my commands!")
    unregistered_user_reminder(int(29), "This is your final notice!  If you do not register your account before tomorrow, your tips will be sent back to the users that tipped you!")

    # Send back the tip to users not registered in 30 days
    return_tips()

    logging.info("{}: completed check for unregistered users.".format(datetime.now()))


main()
