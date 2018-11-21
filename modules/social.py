import requests
import json
import logging
import nano
import configparser
import tweepy
import telegram
import pyqrcode
import os

from datetime import datetime
from TwitterAPI import TwitterAPI
from decimal import Decimal
from http import HTTPStatus

from modules.db import get_db_data, set_db_data
from modules.currency import receive_pending

# Set Log File
logging.basicConfig(handlers=[logging.FileHandler('/root/webhooks/webhooks.log', 'a', 'utf-8')],
                    level=logging.INFO)

# Read config and parse constants
config = configparser.ConfigParser()
config.read('/root/webhooks/webhookconfig.ini')

# Twitter API connection settings
CONSUMER_KEY = config.get('webhooks', 'consumer_key')
CONSUMER_SECRET = config.get('webhooks', 'consumer_secret')
ACCESS_TOKEN = config.get('webhooks', 'access_token')
ACCESS_TOKEN_SECRET = config.get('webhooks', 'access_token_secret')

# Secondary API for non-tweepy supported requests
twitterAPI = TwitterAPI(CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)

# Telegram API
TELEGRAM_KEY = config.get('webhooks', 'telegram_key')

# Constants
MIN_TIP = config.get('webhooks', 'min_tip')
NODE_IP = config.get('webhooks', 'node_ip')

# IDs
BOT_ID_TWITTER = config.get('webhooks', 'bot_id_twitter')
BOT_ID_TELEGRAM = config.get('webhooks', 'bot_id_telegram')

# Connect to Twitter
auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
api = tweepy.API(auth)

# Connect to Telegram
telegram_bot = telegram.Bot(token=TELEGRAM_KEY)

# Connect to Nano node
rpc = nano.rpc.Client(NODE_IP)


def send_dm(receiver, message, system):
    """
    Send the provided message to the provided receiver
    """
    if system == 'twitter':
        data = {
            'event': {
                'type': 'message_create', 'message_create': {
                    'target': {
                        'recipient_id': '{}'.format(receiver)
                    }, 'message_data': {
                        'text': '{}'.format(message)
                    }
                }
            }
        }

        r = twitterAPI.request('direct_messages/events/new', json.dumps(data))

        if r.status_code != 200:
            logging.info('Send DM - Twitter ERROR: {} : {}'.format(r.status_code, r.text))

    elif system == 'telegram':
        try:
            telegram_bot.sendMessage(chat_id=receiver, text=message)
        except Exception as e:
            logging.info("{}: Send DM - Telegram ERROR: {}".format(datetime.now(), e))
            pass


def send_img(receiver, path, message):
    file = open(path, 'rb')
    qr_data = file.read()
    r = twitterAPI.request('media/upload', None, {'media': qr_data})

    if r.status_code == 200:
        media_id = r.json()['media_id']
        logging.info('media_id: {}'.format(media_id))
        msg_data = {
            'event': {
                'type': 'message_create',
                'message_create': {
                    'target': {
                        'recipient_id': '{}'.format(receiver)
                    },
                    'message_data': {
                        'text': '{}'.format(message),
                        'attachment': {
                            'type': 'media',
                            'media': {
                                'id': '{}'.format(media_id)
                            }
                        }
                    }
                }
            }
        }

        r = twitterAPI.request('direct_messages/events/new', json.dumps(msg_data))

        if r.status_code != 200:
            logging.info('Send image ERROR: {} : {}'.format(r.status_code, r.text))


def set_message_info(status, message):
    """
    Set the tweet information into the message dictionary
    """
    logging.info("{}: in set_message_info".format(datetime.now()))
    if status.get('retweeted_status'):
        logging.info("{}: Retweets are ignored.".format(datetime.now()))
        message['id'] = None
    else:
        message['id'] = status.get('id')
        message['sender_id_str'] = status.get('user', {}).get('id_str')
        message['sender_id'] = Decimal(message['sender_id_str'])

        if Decimal(message['sender_id']) == Decimal(BOT_ID_TWITTER):
            logging.info('Messages from the bot are ignored.')
            message['id'] = None
            return message

        message['sender_screen_name'] = status.get('user', {}).get('screen_name')

        if status.get('truncated') is False:
            dm_text = status.get('text')
        else:
            dm_text = status.get('extended_tweet', {}).get('full_text')

        dm_text = dm_text.replace('\n', ' ')
        dm_text = dm_text.lower()

        message['text'] = dm_text.split(" ")

    return message


def check_message_action(message):
    """
    Check to see if there are any key action values mentioned in the tweet.
    """
    logging.info("{}: in check_message_action.".format(datetime.now()))
    try:
        message['action_index'] = message['text'].index("!tip")
    except ValueError:
        message['action'] = None
        return message

    message['action'] = message['text'][message['action_index']].lower()
    message['starting_point'] = message['action_index'] + 1

    return message


def validate_tip_amount(message):
    """
    Validate the tweet includes an amount to tip, and if that tip amount is greater than the minimum tip amount.
    """
    logging.info("{}: in validate_tip_amount".format(datetime.now()))
    try:
        message['tip_amount'] = Decimal(message['text'][message['starting_point']])
    except Exception:
        logging.info("{}: Tip amount was not a number: {}".format(datetime.now(),
                                                                  message['text'][message['starting_point']]))
        not_a_number_text = 'Looks like the value you entered to tip was not a number.  You can try to tip ' \
                            'again using the format !tip 1234 @username'
        send_reply(message, not_a_number_text)

        message['tip_amount'] = -1
        return message

    if Decimal(message['tip_amount']) < Decimal(MIN_TIP):
        min_tip_text = ("The minimum tip amount is {} NANO.  Please update your tip amount and try again."
                        .format(MIN_TIP))
        send_reply(message, min_tip_text)

        message['tip_amount'] = -1
        logging.info("{}: User tipped less than {} NANO.".format(datetime.now(), MIN_TIP))
        return message

    try:
        message['tip_amount_raw'] = Decimal(message['tip_amount']) * 1000000000000000000000000000000
    except Exception as e:
        logging.info("{}: Exception converting tip_amount to tip_amount_raw".format(datetime.now()))
        logging.info("{}: {}".format(datetime.now(), e))
        message['tip_amount'] = -1
        return message

    # create a string to remove scientific notation from small decimal tips
    if str(message['tip_amount'])[0] == ".":
        message['tip_amount_text'] = "0{}".format(str(message['tip_amount']))
    else:
        message['tip_amount_text'] = str(message['tip_amount'])

    return message


def set_tip_list(message, users_to_tip):
    """
    Loop through the message starting after the tip amount and identify any users that were tagged for a tip.  Add the
    user object to the users_to_tip dict to process the tips.
    """
    logging.info("{}: in set_tip_list.".format(datetime.now()))

    if message['system'] == 'twitter':
        for t_index in range(message['starting_point'] + 1, len(message['text'])):
            if len(message['text'][t_index]) > 0 and (
                    str(message['text'][t_index][0]) == "@" and str(message['text'][t_index]).lower() != (
                    "@" + str(message['sender_screen_name']).lower())):
                try:
                    user_info = api.get_user(message['text'][t_index])
                except tweepy.TweepError as e:
                    logging.info("{}: The user sent a !tip command with a mistyped user: {}".format(
                        datetime.now(), message['text'][t_index]))
                    logging.info("{}: Tip List Tweep error: {}".format(datetime.now(), e))
                    users_to_tip.clear()
                    return message, users_to_tip

                user_dict = {'receiver_id': user_info.id, 'receiver_screen_name': user_info.screen_name,
                             'receiver_account': None, 'receiver_register': None}
                users_to_tip.append(user_dict)
                logging.info("{}: Users_to_tip: {}".format(datetime.now(), users_to_tip))

    if message['system'] == 'telegram':
        logging.info("trying to set tiplist in telegram: {}".format(message))
        for t_index in range(message['starting_point'] + 1, len(message['text'])):
            if len(message['text'][t_index]) > 0:
                if str(message['text'][t_index][0]) == "@" and str(message['text'][t_index]).lower() != (
                        "@" + str(message['sender_screen_name']).lower()):
                    check_user_call = ("SELECT member_id, member_name FROM telegram_chat_members "
                                       "WHERE chat_id = {} and member_name = '{}'".format(message['chat_id'],
                                                                                          message['text'][t_index][1:]))

                    user_check_data = get_db_data(check_user_call)
                    if user_check_data:
                        receiver_id = user_check_data[0][0]
                        receiver_screen_name = user_check_data[0][1]

                        user_dict = {'receiver_id': receiver_id, 'receiver_screen_name': receiver_screen_name,
                                     'receiver_account': None, 'receiver_register': None}
                        users_to_tip.append(user_dict)
                    else:
                        logging.info("User not found in DB: chat ID:{} - member name:{}".
                                     format(message['chat_id'], message['text'][t_index][1:]))
                        missing_user_message = ("{} not found in our records.  In order to tip them, they need to be a "
                                                "member of the channel.  If they are in the channel, please have them "
                                                "send a message in the chat so I can add them.".
                                                format(message['text'][t_index]))
                        send_reply(message, missing_user_message)
                        users_to_tip.clear()
                        return message, users_to_tip

    logging.info("{}: Users_to_tip: {}".format(datetime.now(), users_to_tip))
    message['total_tip_amount'] = message['tip_amount']
    if len(users_to_tip) > 0 and message['tip_amount'] != -1:
        message['total_tip_amount'] *= len(users_to_tip)

    return message, users_to_tip


def validate_sender(message):
    """
    Validate that the sender has an account with the tip bot, and has enough NANO to cover the tip.
    """
    logging.info("{}: validating sender".format(datetime.now()))
    logging.info("sender id: {}".format(message['sender_id']))
    logging.info("system: {}".format(message['system']))
    db_call = "SELECT account, register FROM users where user_id = {} AND system = '{}'".format(message['sender_id'],
                                                                                                message['system'])
    sender_account_info = get_db_data(db_call)

    if not sender_account_info:
        no_account_text = ("You do not have an account with the bot.  Please send a DM to me with !register to set up "
                           "an account.")
        send_reply(message, no_account_text)

        logging.info("{}: User tried to send a tip without an account.".format(datetime.now()))
        message['sender_account'] = None
        return message

    message['sender_account'] = sender_account_info[0][0]
    message['sender_register'] = sender_account_info[0][1]

    if message['sender_register'] != 1:
        db_call = "UPDATE users SET register = 1 WHERE user_id = {} AND system = '{}'".format(message['sender_id'],
                                                                                              message['system'])
        set_db_data(db_call)

    receive_pending(message['sender_account'])
    message['sender_balance_raw'] = rpc.account_balance(account='{}'.format(message['sender_account']))
    message['sender_balance'] = message['sender_balance_raw']['balance'] / 1000000000000000000000000000000

    return message


def validate_total_tip_amount(message):
    """
    Validate that the sender has enough Nano to cover the tip to all users
    """
    logging.info("{}: validating total tip amount".format(datetime.now()))
    if message['sender_balance_raw']['balance'] < (message['total_tip_amount'] * 1000000000000000000000000000000):
        not_enough_text = ("You do not have enough NANO to cover this {} NANO tip.  Please check your balance by "
                           "sending a DM to me with !balance and retry.".format(message['total_tip_amount']))
        send_reply(message, not_enough_text)

        logging.info("{}: User tried to send more than in their account.".format(datetime.now()))
        message['tip_amount'] = -1
        return message

    return message


def send_reply(message, text):
    if message['system'] == 'twitter':
        text = '@{} '.format(message['sender_screen_name']) + text
        try:
            api.update_status(text, message['id'])
        except tweepy.TweepError as e:
            logging.info("{}: Send Reply Tweepy Error: {}".format(datetime.now(), e))

    elif message['system'] == 'telegram':
        telegram_bot.sendMessage(chat_id=message['chat_id'], text=text)


def check_telegram_member(chat_id, chat_name, member_id, member_name):
    check_user_call = ("SELECT member_id, member_name FROM telegram_chat_members "
                       "WHERE chat_id = {} and member_name = '{}'".format(chat_id,
                                                                          member_name))
    user_check_data = get_db_data(check_user_call)

    logging.info("checking if user exists")
    if not user_check_data:
        logging.info("{}: User {}-{} not found in DB, inserting".format(datetime.now(), chat_id, member_name))
        new_chat_member_call = ("INSERT INTO telegram_chat_members (chat_id, chat_name, member_id, member_name) "
                                "VALUES ({}, '{}', {}, '{}')".format(chat_id, chat_name, member_id, member_name))
        set_db_data(new_chat_member_call)

    return


def get_qr_code(sender_id, sender_account, sm_system):
    """
    Check to see if a QR code has been generated for the sender_id / system combination.  If not, generate one.
    """
    qr_exists = os.path.isfile('/root/webhooks/qr/{}-{}.png'.format(sender_id, sm_system))

    if not qr_exists:
        print("No QR exists, generating a QR for account {}".format(sender_account))
        account_qr = pyqrcode.create('{}'.format(sender_account))
        account_qr.png('/root/webhooks/qr/{}-{}.png'.format(sender_id, sm_system), scale=4)


def send_account_message(account_text, message, account):
    """
    Send a message to the user with their account information.  If twitter, include a QR code for scanning.
    """

    if message['system'] == 'twitter':
        get_qr_code(message['sender_id'], account, message['system'])
        path = ('/root/webhooks/qr/{}-{}.png'.format(message['sender_id'], message['system']))
        send_img(message['sender_id'], path, account_text)
    elif message['system'] != 'twitter':
        send_dm(message['sender_id'], account_text, message['system'])

    send_dm(message['sender_id'], account, message['system'])