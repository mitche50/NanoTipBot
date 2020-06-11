import configparser
import json
import logging
import os
from datetime import datetime
from decimal import Decimal

import nano
import pyqrcode
import telegram
import tweepy
from TwitterAPI import TwitterAPI
from logging.handlers import TimedRotatingFileHandler

import modules.currency
import modules.db
import modules.orchestration
import modules.translations as translations

# Set Log File
logger = logging.getLogger("social_log")
logger.setLevel(logging.INFO)
handler = TimedRotatingFileHandler('{}/logs/{:%Y-%m-%d}-social.log'.format(os.getcwd(), datetime.now()),
                                   when="d",
                                   interval=1,
                                   backupCount=5)
logger.addHandler(handler)

# Read config and parse constants
config = configparser.ConfigParser()
config.read('{}/webhookconfig.ini'.format(os.getcwd()))

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

# Secondary API for non-tweepy supported requests
twitterAPI = TwitterAPI(CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)

# Telegram API
TELEGRAM_KEY = config.get(CURRENCY, 'telegram_key')

# Constants
MIN_TIP = config.get(CURRENCY, 'min_tip')
NODE_IP = config.get(CURRENCY, 'node_ip')
WALLET = config.get(CURRENCY, 'wallet')

# IDs
BOT_ID_TWITTER = config.get(CURRENCY, 'bot_id_twitter')
BOT_ID_TELEGRAM = config.get(CURRENCY, 'bot_id_telegram')
BOT_NAME_TELEGRAM = config.get(CURRENCY, 'bot_name_telegram')
BOT_NAME_TWITTER = config.get(CURRENCY, 'bot_name_twitter')
BASE_URL = config.get('routes', 'base_url')
TELEGRAM_URI = config.get('routes', 'telegram_uri')

# Connect to Twitter
auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
api = tweepy.API(auth)

# Connect to Telegram
if TELEGRAM_KEY != 'none':
    print(TELEGRAM_KEY)
    telegram_bot = telegram.Bot(token=TELEGRAM_KEY)

# Connect to Nano node
rpc = nano.rpc.Client(NODE_IP)


def get_language(message):
    """
    Set the language for messaging the user
    """
    get_language_call = "SELECT language_code FROM languages WHERE user_id = %s AND languages.system = %s"
    language_values = [message['sender_id'], message['system']]
    language_return = modules.db.get_db_data_new(get_language_call, language_values)
    # If there is no record, create a new one with default EN language
    try:
        message['language'] = language_return[0][0]
    except Exception as e:
        logger.info("{}: There was no language entry, setting default".format(datetime.now()))
        # Check if the user has an account - if not, create one
        no_lang_call = ("SELECT account, register FROM users WHERE user_id = {} AND users.system = '{}'"
                         .format(message['sender_id'], message['system']))
        data = modules.db.get_db_data(no_lang_call)

        if not data:
            # Create an account for the user
            sender_account = modules.db.get_spare_account()
            account_create_call = ("INSERT INTO users (user_id, system, user_name, account, register) "
                                   "VALUES(%s, %s, %s, %s, 1)")
            account_create_values = [message['sender_id'], message['system'], message['sender_screen_name'],
                                     sender_account]
            modules.db.set_db_data(account_create_call, account_create_values)
        message['language'] = 'en'


def get_receiver_language(user_id, system):
    """
    Set the language for the receiver of the tip
    """
    get_language_call = ("SELECT language_code FROM languages WHERE user_id = %s "
                         "AND languages.system = %s")
    language_values = [user_id, system]
    language_return = modules.db.get_db_data_new(get_language_call, language_values)
    try:
        return language_return[0][0]
    except Exception as e:
        logger.info("{}: There was no language entry for the receiver, setting default".format(datetime.now()))
        return 'en'


def check_mute(user_id, system):
    """
    Check to see if the bot is muted by the message receiver
    """
    get_mute_call = ("SELECT mute FROM users WHERE user_id = %s "
                     "AND system = %s")
    mute_values = [user_id, system]
    mute_return = modules.db.get_db_data_new(get_mute_call, mute_values)

    try:
        return False if mute_return[0][0] == 0 else True
    except Exception as e:
        logger.info("{}: No mute value found - returning False".format(datetime.now()))
        return False


def send_dm(receiver, message, system):
    """
    Send the provided message to the provided receiver
    """
    if receiver == BOT_ID_TWITTER:
        logger.info("{}: Bot should not be messaging itself.".format(datetime.now()))
        return

    if check_mute(receiver, system):
        logger.info("{}: User has muted bot.".format(datetime.now()))
        return

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
            logger.info('Send DM - Twitter ERROR: {} : {}'.format(r.status_code, r.text))

    elif system == 'telegram':
        try:
            telegram_bot.sendMessage(chat_id=receiver, text=message)
        except Exception as e:
            logger.info("{}: Send DM - Telegram ERROR: {}".format(datetime.now(), e))
            pass


def send_img(receiver, path, message, system):

    if check_mute(receiver, system):
        logger.info("{}: User has muted bot.".format(datetime.now()))
        return

    if system == 'twitter':
        file = open(path, 'rb')
        qr_data = file.read()
        r = twitterAPI.request('media/upload', None, {'media': qr_data})

        if r.status_code == 200:
            media_id = r.json()['media_id']
            logger.info('media_id: {}'.format(media_id))
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
                logger.info('Send image ERROR: {} : {}'.format(r.status_code, r.text))
    elif system == 'telegram':
        try:
            qr_data = '{}{}qr/{}-{}.png'.format(BASE_URL, CURRENCY, system, receiver)
            logger.info("{}qr_data: {}".format(CURRENCY, qr_data))
            telegram_bot.send_photo(chat_id=receiver, photo=qr_data, caption=message)
        except Exception as e:
            logger.info("ERROR SENDING QR PHOTO TELEGRAM: {}".format(e))


def set_message_info(status, message):
    """
    Set the tweet information into the message dictionary
    """
    logger.info("{}: in set_message_info".format(datetime.now()))
    if status.get('retweeted_status'):
        logger.info("{}: Retweets are ignored.".format(datetime.now()))
        message['id'] = None
    else:
        message['id'] = status.get('id')
        message['sender_id_str'] = status.get('user', {}).get('id_str')
        message['sender_id'] = Decimal(message['sender_id_str'])

        if Decimal(message['sender_id']) == Decimal(BOT_ID_TWITTER):
            logger.info('Messages from the bot are ignored.')
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
        modules.social.get_language(message)

    return message


def check_message_action(message):
    """
    Check to see if there are any key action values mentioned in the tweet.
    """
    if message['system'] == 'telegram':
        try:
            check_for_ntb = message['text'].index("{}".format(BOT_NAME_TELEGRAM.lower()))
        except ValueError:
            message['action'] = None
            return message
    try:
        message['action_index'] = None

        if CURRENCY == 'banano':
            tip_commands = modules.translations.banano_tip_commands['en']
        else:
            tip_commands = modules.translations.nano_tip_commands[message['language']]
            if message['language'] != 'en':
                english_commands = modules.translations.nano_tip_commands['en']
                for command in english_commands:
                    tip_commands.append(command)

        logger.info("tip commands: {}".format(tip_commands))

        for command in tip_commands:
            if command in message['text']:
                message['action_index'] = message['text'].index(command)
        if message['action_index'] is None:
            message['action'] = None
            return message

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
    # Set tip commands
    if CURRENCY == 'banano':
        tip_commands = modules.translations.banano_tip_commands['en']
    else:
        tip_commands = modules.translations.nano_tip_commands[message['language']]
        if message['language'] != 'en':
            english_commands = modules.translations.nano_tip_commands['en']
            for command in english_commands:
                logger.info("commad: {}".format(command))
                tip_commands.append(command)

    logger.info("{}: in validate_tip_amount".format(datetime.now()))
    try:
        if not message['text'][message['starting_point']][0].isdigit() and message['text'][message['starting_point']][0] != '.':
            symbol = message['text'][message['starting_point']][0]
            fiat_amount = message['text'][message['starting_point']][1:]
            message['tip_amount'] = Decimal(modules.currency.get_fiat_conversion(symbol, CURRENCY, fiat_amount))

            if message['tip_amount'] == -1:
                send_reply(message, translations.unsupported_fiat[message['language']])
                return message
        else:
            message['tip_amount'] = Decimal(message['text'][message['starting_point']])
    except IndexError as e:
        logger.info("{}: Index out of range". format(datetime.now()))
        message['tip_amount'] = -1
        return message
    except Exception:
        logger.info("{}: Tip amount was not a number".format(datetime.now()))
        if message['system'] == 'twitter':
            bot_name = BOT_NAME_TWITTER
        else:
            bot_name = BOT_NAME_TELEGRAM
        send_reply(message, translations.not_a_number_text[message['language']].format(bot_name, tip_commands[0]))

        message['tip_amount'] = -1
        return message

    if Decimal(message['tip_amount']) < Decimal(MIN_TIP):
        try:
            send_reply(message, translations.min_tip_text[message['language']].format(MIN_TIP, CURRENCY.upper()))
        except Exception as e:
            logger.info("{}: Error sending reply for a tip below the minimum.".format(datetime.now()))

        message['tip_amount'] = -1
        logger.info("{}: User tipped less than {} {}.".format(datetime.now(), MIN_TIP, CURRENCY.upper()))
        return message

    try:
        message['tip_amount_raw'] = Decimal(message['tip_amount']) * CONVERT_MULTIPLIER[CURRENCY]
    except Exception as e:
        logger.info("{}: Exception converting tip_amount to tip_amount_raw".format(datetime.now()))
        logger.info("{}: {}".format(datetime.now(), e))
        message['tip_amount'] = -1
        return message

    # create a string to remove scientific notation from small decimal tips
    if str(message['tip_amount'])[0] == ".":
        message['tip_amount_text'] = "0{}".format(str(message['tip_amount']))
    else:
        message['tip_amount_text'] = str(message['tip_amount'])
    
    # remove any trailing 0's if decimal is 0.  This is to prevent confusion from someone tipping
    # 1.000 and making users think they received 1000 nano/banano
    try:
        if '.' in message['tip_amount_text']:
            if int(message['tip_amount_text'][message['tip_amount_text'].index('.') + 1:]) == 0:
                message['tip_amount_text'] = message['tip_amount_text'][:message['tip_amount_text'].index('.')]
    except Exception as e:
        logger.info("{}: Error in removing trailing zeroes - ignoring {}".format(datetime.now(), e))

    return message


def check_invalid_chars(user):
    """
    Check user for invalid ending characters
    """
    invalid_ending_chars = ['.', '!', '?', ',']

    if user[-1:] in invalid_ending_chars:
        return user[:-1]

    return user


def set_tip_list(message, users_to_tip, request_json):
    """
    Loop through the message starting after the tip amount and identify any users that were tagged for a tip.  Add the
    user object to the users_to_tip dict to process the tips.
    """
    logger.info("{}: in set_tip_list.".format(datetime.now()))

    # Identify the first user to string multi tips.  Once a non-user is mentioned, end the user list

    first_user_flag = False

    if message['system'] == 'twitter':
        for t_index in range(message['starting_point'] + 1, len(message['text'])):
            if first_user_flag and len(message['text'][t_index]) > 0 and str(message['text'][t_index][0]) != "@":
                logger.info("users identified, regular text breaking the loop: {}".format(message['text'][t_index][0]))
                break
            if len(message['text'][t_index]) > 0 and (
                    str(message['text'][t_index][0]) == "@" and str(message['text'][t_index]).lower() != (
                    "@" + str(message['sender_screen_name']).lower())):
                if not first_user_flag:
                    first_user_flag = True
                message['text'][t_index] = check_invalid_chars(message['text'][t_index])
                try:
                    user_info = api.get_user(message['text'][t_index])
                except tweepy.TweepError as e:
                    logger.info("{}: The user sent a !tip command with a mistyped user: {}".format(
                        datetime.now(), message['text'][t_index]))
                    logger.info("{}: Tip List Tweep error: {}".format(datetime.now(), e))
                    users_to_tip.clear()
                    return message, users_to_tip

                receiver_language = get_receiver_language(user_info.id, message['system'])

                user_dict = {'receiver_id': user_info.id, 'receiver_screen_name': user_info.screen_name,
                             'receiver_account': None, 'receiver_register': None,
                             'receiver_language': receiver_language}
                users_to_tip.append(user_dict)
                logger.info("{}: Users_to_tip: {}".format(datetime.now(), users_to_tip))

    if message['system'] == 'telegram':
        logger.info("trying to set tiplist in telegram: {}".format(message))

        if 'reply_to_message' in request_json['message']:
            if len(users_to_tip) == 0:
                check_user_call = ("SELECT member_id, member_name FROM telegram_chat_members "
                                   "WHERE chat_id = {} and member_id = '{}'".format(message['chat_id'],
                                                                                    request_json['message']
                                                                                    ['reply_to_message']['from']['id']))

                user_check_data = modules.db.get_db_data(check_user_call)
                if user_check_data:
                    receiver_id = user_check_data[0][0]
                    receiver_screen_name = user_check_data[0][1]

                    receiver_language = get_receiver_language(receiver_id, message['system'])
                    user_dict = {'receiver_id': receiver_id, 'receiver_screen_name': receiver_screen_name,
                                 'receiver_account': None, 'receiver_register': None,
                                 'receiver_language': receiver_language}
                    users_to_tip.append(user_dict)
                else:
                    logger.info("User not found in DB: chat ID:{} - member name:{}".
                                 format(message['chat_id'], request_json['message']['reply_to_message']['from']
                                                                        ['first_name']))
                    send_reply(message, translations.missing_user_message[message['language']]
                               .format(request_json['message']['reply_to_message']['from']['first_name']))
                    users_to_tip.clear()
                    return message, users_to_tip
        else:
            for t_index in range(message['starting_point'] + 1, len(message['text'])):
                if first_user_flag and len(message['text'][t_index]) > 0 and str(message['text'][t_index][0]) != "@":
                    logger.info("users identified, regular text breaking the loop: {}".format(message['text'][t_index][0]))
                    break
                if len(message['text'][t_index]) > 0:
                    if (str(message['text'][t_index][0]) == "@" and len(message['text'][t_index]) > 1 and message['text'][t_index][1] != ' ' 
                            and str(message['text'][t_index]).lower() != ("@" + str(message['sender_screen_name']).lower())):
                        message['text'][t_index] = check_invalid_chars(message['text'][t_index])
                        check_user_call = ("SELECT member_id, member_name FROM telegram_chat_members "
                                           "WHERE chat_id = {} and member_name = '{}'".format(message['chat_id'],
                                                                                              message['text'][t_index][1:]))

                        user_check_data = modules.db.get_db_data(check_user_call)
                        if user_check_data:
                            receiver_id = user_check_data[0][0]
                            receiver_screen_name = user_check_data[0][1]
                            duplicate_user = False

                            for u_index in range(0, len(users_to_tip)):
                                if users_to_tip[u_index]['receiver_id'] == receiver_id:
                                    duplicate_user = True

                            if not duplicate_user:
                                if not first_user_flag:
                                    first_user_flag = True
                                logger.info("User tipped via searching the string for mentions")
                                receiver_language = get_receiver_language(receiver_id, message['system'])
                                user_dict = {'receiver_id': receiver_id, 'receiver_screen_name': receiver_screen_name,
                                             'receiver_account': None, 'receiver_register': None,
                                             'receiver_language': receiver_language}
                                users_to_tip.append(user_dict)
                        else:
                            logger.info("User not found in DB: chat ID:{} - member name:{}".
                                         format(message['chat_id'], message['text'][t_index][1:]))
                            send_reply(message, translations.missing_user_message[message['language']]
                                       .format(message['text'][t_index]))
                            users_to_tip.clear()
                            return message, users_to_tip
            try:
                text_mentions = request_json['message']['entities']
                for mention in text_mentions:
                    if mention['type'] == 'text_mention':
                        check_user_call = ("SELECT member_id, member_name FROM telegram_chat_members "
                                           "WHERE chat_id = {} and member_id = '{}'".format(message['chat_id'],
                                                                                            mention['user']['id']))

                        user_check_data = modules.db.get_db_data(check_user_call)
                        if user_check_data:
                            receiver_id = user_check_data[0][0]
                            receiver_screen_name = user_check_data[0][1]
                            logger.info("telegram user added via mention list.")
                            logger.info("mention: {}".format(mention))
                            receiver_language = get_receiver_language(receiver_id, message['system'])

                            user_dict = {'receiver_id': receiver_id, 'receiver_screen_name': receiver_screen_name,
                                         'receiver_account': None, 'receiver_register': None,
                                         'receiver_language': receiver_language}
                            users_to_tip.append(user_dict)
                        else:
                            logger.info("User not found in DB: chat ID:{} - member name:{}".
                                         format(message['chat_id'], mention['user']['first_name']))
                            send_reply(message, translations.missing_user_message[message['language']]
                                       .format(mention['user']['first_name']))
                            users_to_tip.clear()
                            return message, users_to_tip
            except:
                pass

    logger.info("{}: Users_to_tip: {}".format(datetime.now(), users_to_tip))
    message['total_tip_amount'] = message['tip_amount']
    if len(users_to_tip) > 0 and message['tip_amount'] != -1:
        message['total_tip_amount'] *= len(users_to_tip)

    return message, users_to_tip


def validate_sender(message):
    """
    Validate that the sender has an account with the tip bot, and has enough NANO to cover the tip.
    """
    logger.info("{}: validating sender".format(datetime.now()))
    logger.info("sender id: {}".format(message['sender_id']))
    logger.info("system: {}".format(message['system']))
    db_call = "SELECT account, register FROM users where user_id = {} AND users.system = '{}'".format(message['sender_id'],
                                                                                                      message['system'])
    sender_account_info = modules.db.get_db_data(db_call)

    if not sender_account_info:
        send_reply(message, translations.no_account_text[message['language']])

        logger.info("{}: User tried to send a tip without an account.".format(datetime.now()))
        message['sender_account'] = None
        return message

    message['sender_account'] = sender_account_info[0][0]
    message['sender_register'] = sender_account_info[0][1]

    if message['sender_register'] != 1:
        db_call = "UPDATE users SET register = 1 WHERE user_id = %s AND users.system = %s"
        db_values = [message['sender_id'], message['system']]
        modules.db.set_db_data(db_call, db_values)

    modules.currency.receive_pending(message['sender_account'])
    message['sender_balance_raw'] = rpc.account_balance(account='{}'.format(message['sender_account']))
    message['sender_balance'] = message['sender_balance_raw']['balance'] / CONVERT_MULTIPLIER[CURRENCY]

    return message


def validate_total_tip_amount(message):
    """
    Validate that the sender has enough Nano to cover the tip to all users
    """
    logger.info("{}: validating total tip amount".format(datetime.now()))
    if message['sender_balance_raw']['balance'] < (message['total_tip_amount'] * CONVERT_MULTIPLIER[CURRENCY]):
        send_reply(message, translations.not_enough_text[message['language']].format(CURRENCY.upper(),
                                                                                     message['total_tip_amount'],
                                                                                     CURRENCY.upper()))

        logger.info("{}: User tried to send more than in their account.".format(datetime.now()))
        message['tip_amount'] = -1
        return message

    return message


def send_reply(message, text):
    if check_mute(message['sender_id'], message['system']):
        logger.info("{}: User has muted bot.".format(datetime.now()))
        return
    
    if message['system'] == 'twitter':
        text = '@{} '.format(message['sender_screen_name']) + text
        try:
            api.update_status(text, message['id'])
        except tweepy.TweepError as e:
            logger.info("{}: Send Reply Tweepy Error: {}".format(datetime.now(), e))

    elif message['system'] == 'telegram':
        try:
            telegram_bot.sendMessage(chat_id=message['chat_id'], reply_to_message_id=message['id'], text=text)
        except Exception as e:
            logger.info("{}: Send reply telegram error3 {}".format(datetime.now(), e))

def check_telegram_member(chat_id, chat_name, member_id, member_name):
    check_user_call = ("SELECT member_id, member_name FROM telegram_chat_members "
                       "WHERE chat_id = {} and member_id = {}".format(chat_id,
                                                                      member_id))
    user_check_data = modules.db.get_db_data(check_user_call)

    if not user_check_data:
        logger.info("{}: User {}-{} not found in DB, inserting".format(datetime.now(), chat_id, member_name))
        new_chat_member_call = ("INSERT INTO telegram_chat_members (chat_id, chat_name, member_id, member_name) "
                                "VALUES (%s, %s, %s, %s)")
        new_chat_member_values = [chat_id, chat_name, member_id, member_name]
        modules.db.set_db_data(new_chat_member_call, new_chat_member_values)

    elif user_check_data[0][1] != member_name:
        logger.info("Member ID {} name incorrect in DB.  Stored value: {}  Updating to {}"
                     .format(member_id, user_check_data[0][1], member_name))

        update_name_call = ("UPDATE telegram_chat_members "
                            "SET member_name = %s "
                            "WHERE member_id = %s")
        update_name_values = [member_name, member_id]
        modules.db.set_db_data(update_name_call, update_name_values)

    return


def get_qr_code(sender_id, sender_account, sm_system):
    """
    Check to see if a QR code has been generated for the sender_id / system combination.  If not, generate one.
    """
    qr_exists = os.path.isfile('{}/{}qr/{}-{}.png'.format(os.getcwd(), CURRENCY, sm_system, sender_id))

    if not qr_exists:
        print("No {} QR exists, generating a QR for account {}".format(CURRENCY, sender_account))
        account_qr = pyqrcode.create('{}'.format(sender_account))
        account_qr.png('{}/{}qr/{}-{}.png'.format(os.getcwd(), CURRENCY, sm_system, sender_id), scale=10)


def send_account_message(account_text, message, account):
    """
    Send a message to the user with their account information.  If twitter, include a QR code for scanning.
    """

    if check_mute(message['sender_id'], message['system']):
        logger.info("{}: User has muted bot.".format(datetime.now()))
        return

    if message['system'] == 'twitter' or message['system'] == 'telegram':
        get_qr_code(message['sender_id'], account, message['system'])
        path = ('{}/{}qr/{}-{}.png'.format(os.getcwd(), CURRENCY, message['system'], message['sender_id']))
        send_img(message['sender_id'], path, account_text, message['system'])
    else:
        send_dm(message['sender_id'], account_text, message['system'])

    send_dm(message['sender_id'], account, message['system'])


def telegram_set_webhook():
    try:
        response = telegram_bot.setWebhook('{}/{}'.format(BASE_URL, TELEGRAM_URI))
        if response:
            return "Webhook setup successfully"
        else:
            return "Error {}".format(response)
    except Exception as e:
        print("banano has no telegram bot")
