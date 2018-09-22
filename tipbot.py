from flask import Flask, render_template, request, send_from_directory, make_response
from TwitterAPI import TwitterAPI
from datetime import datetime
from decimal import *
from http import HTTPStatus
from pytz import timezone
from nano import convert
from contextlib import closing
from sys import getsizeof
import telegram
import MySQLdb, re, requests, base64, hashlib, hmac, json, logging, configparser, nano, tweepy, os, time, socket, pyqrcode

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

# Facebook API
VERIFY_TOKEN = config.get('webhooks', 'verify_token')
PAGE_ACCESS_TOKEN = config.get('webhooks', 'page_access_token')

# Telegram API
TELEGRAM_KEY = config.get('webhooks', 'telegram_key')

# DB connection settings
DB_HOST = config.get('webhooks', 'host')
DB_USER = config.get('webhooks', 'user')
DB_PW = config.get('webhooks', 'password')
DB_SCHEMA = config.get('webhooks', 'schema')

# Nano Node connection settings
WALLET = config.get('webhooks', 'wallet')
NODE_IP = config.get('webhooks', 'node_ip')
BOT_ID_TWITTER = config.get('webhooks', 'bot_id_twitter')
BOT_ID_FACEBOOK = config.get('webhooks', 'bot_id_facebook')
BOT_NAME = config.get('webhooks', 'bot_name')
BOT_ACCOUNT = config.get('webhooks', 'bot_account')
MIN_TIP = config.get('webhooks', 'min_tip')
WORK_SERVER = config.get('webhooks', 'work_server')
WORK_KEY = config.get('webhooks', 'work_key')
WORK_PEER_ADDRESS = config.get('webhooks', 'work_peer_address')
WORK_PEER_PORT = int(config.get('webhooks', 'work_peer_port'))
RE_EMOJI = re.compile('[\U00010000-\U0010ffff\U000026A1]', flags=re.UNICODE)
TIMEZONE = timezone('US/Eastern')
BULLET = u"\u2022"

# Set key for webhook challenge from Twitter
key = config.get('webhooks', 'consumer_secret')

# Set up Flask routing
app = Flask(__name__, template_folder='/var/www/html')

# Connect to Twitter
auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
api = tweepy.API(auth)

# Secondary API for non-tweepy supported requests
twitterAPI = TwitterAPI(CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)

# Connect to Nano node
rpc = nano.rpc.Client(NODE_IP)

# Connect to Telegram
telegram_bot = telegram.Bot(token=TELEGRAM_KEY)


def getDBData(db_call):
    """
    Retrieve data from DB
    """
    db = MySQLdb.connect(host=DB_HOST, port=3306, user=DB_USER, passwd=DB_PW, db=DB_SCHEMA, use_unicode=True,
                         charset="utf8")
    db_cursor = db.cursor()
    db_cursor.execute(db_call)
    db_data = db_cursor.fetchall()
    db_cursor.close()
    db.close()
    return db_data


def setDBData(db_call):
    """
    Enter data into DB
    """
    db = MySQLdb.connect(host=DB_HOST, port=3306, user=DB_USER, passwd=DB_PW, db=DB_SCHEMA, use_unicode=True,
                         charset="utf8")
    try:
        db_cursor = db.cursor()
        db_cursor.execute(db_call)
        db.commit()
        db_cursor.close()
        db.close()
        logging.info("{}: record inserted into DB".format(datetime.now()))
    except MySQLdb.ProgrammingError as e:
        logging.info("{}: Exception entering data into database".format(datetime.now(TIMEZONE)))
        logging.info("{}: {}".format(datetime.now(TIMEZONE), e))
        raise e


def receivePending(sender_account):
    """
    Check to see if the account has any pending blocks and process them
    """
    try:
        logging.info("{}: in receive pending".format(datetime.now()))
        pending_blocks = rpc.pending(account='{}'.format(sender_account))
        if len(pending_blocks) > 0:
            for block in pending_blocks:
                work = getPOW(sender_account)
                if work == '':
                    logging.info("{}: processing without pow".format(datetime.now()))
                    receive_data = {'action': "receive", 'wallet': WALLET, 'account': sender_account, 'block': block}
                else:
                    logging.info("{}: processing with pow".format(datetime.now()))
                    receive_data = {'action': "receive", 'wallet': WALLET, 'account': sender_account, 'block': block, 'work': work}
                receive_json = json.dumps(receive_data)
                r = requests.post('{}'.format(NODE_IP), data=receive_json)
                logging.info("{}: block {} received".format(datetime.now(), block))

        else:
            logging.info('{}: No blocks to receive.'.format(datetime.now()))

    except Exception as e:
        logging.info("Error: {}".format(e))
        raise e

    return


def sendDM(receiver, message, system):
    """
    Send the provided message to the provided receiver
    """
    if system == 'twitter':
        data = {'event':
                    {'type':'message_create', 'message_create':
                        {'target':
                             {'recipient_id':'{}'.format(receiver)},
                         'message_data':
                             {'text':'{}'.format(message)}
                         }
                     }
                }

        r = twitterAPI.request('direct_messages/events/new', json.dumps(data))

        if r.status_code != 200:
            logging.info('ERROR: {} : {}'.format(r.status_code, r.text))

    elif system == 'facebook':
        request_body = {
            "messaging_type": "RESPONSE",
            "recipient": {
                "id": receiver
            },
            "message": {
                "text": message
            }
        }

        message_json = json.dumps(request_body)
        logging.info("working message_json: {}".format(message_json))
        post_url = 'https://graph.facebook.com/v2.6/me/messages?access_token={}'.format(PAGE_ACCESS_TOKEN)
        try:
            r = requests.post(post_url, headers={"Content-Type": "application/json"}, data=message_json)
        except Exception as e:
            logging.info("{}: ERROR: {}".format(datetime.now(), e))
            pass

    elif system == 'facebook2':
        request_body = {
            "messaging_type": "UPDATE",
            "recipient": {
                "id": receiver
            },
            "message": {
                "text": message
            }
        }

        message_json = json.dumps(request_body)
        logging.info("dm message_json: {}".format(message_json))
        post_url = 'https://graph.facebook.com/v2.6/me/messages?access_token={}'.format(PAGE_ACCESS_TOKEN)
        try:
            r = requests.post(post_url, headers={"Content-Type": "application/json"}, data=message_json)
            logging.info("dm response: {} - {}".format(r, r.text))
        except Exception as e:
            logging.info("{}: ERROR: {}".format(datetime.now(), e))
            pass

    elif system == 'telegram':
        try:
            telegram_bot.sendMessage(chat_id=receiver, text=message)
        except Exception as e:
            logging.info("{}: ERROR SENDING TELEGRAM MESSAGE: {}".format(datetime.now(), e))
            pass


def helpProcess(message):
    """
    Reply to the sender with help commands
    """
    help_message = ("Thank you for using the Nano Tip Bot!  Below is a list of commands, and a description of what they do:\n\n" + BULLET +
                    " !help: The tip bot will respond to your DM with a list of commands and their functions. If you forget something, use this to get a hint of how to do it!\n\n" + BULLET +
                    " !register: Registers your twitter ID for an account that is tied to it.  This is used to store your tips. Make sure to withdraw to a private wallet, as the tip bot is not meant to be a long term storage device for Nano.\n\n" + BULLET +
                    " !balance: This returns the balance of the account linked with your Twitter ID.\n\n" + BULLET +
                    " !tip: Tips are sent through public tweets.  Tag @NanoTipBot in a tweet and mention !tip <amount> <@username>.  Example: @NanoTipBot !tip 1 @mitche50 would send a 1 Nano tip to user @mitche50.\n\n" + BULLET +
                    " !privatetip: Currently disabled.  Will be enabled when live DM monitoring is possible through twitter.  This will send a tip to another user without posting a tweet.  If you would like your tip amount to be private, use this function!  Proper usage is !privatetip @username 1234\n\n" + BULLET +
                    " !account: Returns the account number that is tied to your Twitter handle.  You can use this to deposit more Nano to tip from your personal wallet.\n\n" + BULLET +
                    " !withdraw: Proper usage is !withdraw xrb_12345.  This will send the full balance of your tip account to the provided Nano account.  Optional: You can include an amount to withdraw by sending !withdraw <amount> <address>.  Example: !withdraw 1 xrb_iaoia83if221lodoepq would withdraw 1 NANO to account xrb_iaoia83if221lodoepq.\n\n" + BULLET +
                    " !donate: Proper usage is !donate 1234.  This will send the requested donation to the Nano Tip Bot donation account to help fund development efforts.")
    sendDM(message['sender_id'], help_message, message['system'])
    logging.info("{}: Help message sent!".format(str(datetime.now())))


def balanceProcess(message):
    """
    When the user sends a DM containing !balance, reply with the balance of the account linked with their Twitter ID
    """
    logging.info("{}: In balance process".format(datetime.now()))
    balance_call = ("SELECT account, register FROM users WHERE user_id = {} "
                    "AND system = '{}'".format(message['sender_id'], message['system']))
    data = getDBData(balance_call)
    if not data:
        logging.info("{}: User tried to check balance without an account".format(str(datetime.now())))
        balance_message = ("There is no account linked to your username.  Please respond with !register to "
                           "create an account.")
        sendDM(message['sender_id'], balance_message, message['system'])
    else:
        message['sender_account'] = data[0][0]
        sender_register = data[0][1]

        if sender_register == 0:
            set_register_call = ("UPDATE users SET register = 1 WHERE user_id = {} AND system = '{}' AND "
                                 "register = 0".format(message['sender_id'], message['system']))
            setDBData(set_register_call)

        receivePending(message['sender_account'])
        balance_return = rpc.account_balance(account="{}".format(message['sender_account']))
        message['sender_balance_raw'] = balance_return['balance']
        message['sender_balance'] = balance_return['balance'] / 1000000000000000000000000000000
        if message['sender_balance'] == 0:
            balance_text = "Your balance is 0 NANO."
        else:
            balance_text = "Your balance is {} NANO.".format(message['sender_balance'])
        sendDM(message['sender_id'], balance_text, message['system'])
        logging.info("{}: Balance Message Sent!".format(str(datetime.now())))


def registerProcess(message):
    """
    When the user sends !register, create an account for them and mark it registered.  If they already have an account
    reply with their account number.
    """
    logging.info("{}: In register process.".format(datetime.now()))
    register_call = ("SELECT account, register FROM users WHERE user_id = {} AND system = '{}'".format(message['sender_id'], message['system']))
    data = getDBData(register_call)

    if not data:
        # Create an account for the user
        sender_account = rpc.account_create(wallet="{}".format(WALLET), work=False)
        account_create_call = ("INSERT INTO users (user_id, system, user_name, account, register) "
                               "VALUES({}, '{}', '{}', '{}',1)".format(message['sender_id'], message['system'],
                                                                       message['sender_screen_name'], sender_account))
        setDBData(account_create_call)
        account_create_text = "You have successfully registered for an account.  Your account number is:"

        if message['system'] == 'twitter':
            getQRCode(message['sender_id'], sender_account, message['system'])
            path = ('/root/webhooks/qr/{}-{}.png'.format(message['sender_id'], message['system']))
            sendImg(message['sender_id'], path, account_create_text)

        elif message['system'] != 'twitter':
            sendDM(message['sender_id'], account_create_text, message['system'])

        sendDM(message['sender_id'], sender_account, message['system'])

        logging.info("{}: Register successful!".format(str(datetime.now())))

    elif data[0][1] == 0:
        # The user has an account, but needed to register, so send a message to the user with their account
        sender_account = data[0][0]
        account_registration_update = ("UPDATE users SET register = 1 WHERE user_id = {} AND "
                                       "register = 0".format(message['sender_id']))
        setDBData(account_registration_update)
        account_registration_text = "You have successfully registered for an account.  Your account number is:"

        if message['system'] == 'twitter':
            getQRCode(message['sender_id'], sender_account, message['system'])
            path = ('/root/webhooks/qr/{}-{}.png'.format(message['sender_id'], message['system']))
            sendImg(message['sender_id'], path, account_registration_text)
        elif message['system'] != 'twitter':
            sendDM(message['sender_id'], account_registration_text, message['system'])

        sendDM(message['sender_id'], sender_account, message['system'])

        logging.info("{}: User has an account, but needed to register.  Message sent".format(str(datetime.now())))

    else:
        # The user had an account and already registered, so let them know their account.
        sender_account = data[0][0]
        account_already_registered = "You already have registered your account.  Your account number is:"
        if message['system'] == 'twitter':
            getQRCode(message['sender_id'], sender_account, message['system'])
            path = ('/root/webhooks/qr/{}-{}.png'.format(message['sender_id'], message['system']))
            sendImg(message['sender_id'], path, account_already_registered)
        elif message['system'] != 'twitter':
            sendDM(message['sender_id'], account_already_registered, message['system'])

        sendDM(message['sender_id'], sender_account, message['system'])

        logging.info("{}: User has a registered account.  Message sent.".format(str(datetime.now())))


def accountProcess(message):
    """
    If the user sends !account command, reply with their account.  If there is no account, create one, register it
    and reply to the user.
    """
    logging.info("{}: In account process.".format(datetime.now()))
    sender_account_call = ("SELECT account, register FROM users WHERE user_id = {} AND system = '{}'".format(message['sender_id'], message['system']))
    account_data = getDBData(sender_account_call)
    if not account_data:
        sender_account = rpc.account_create(wallet="{}".format(WALLET), work=True)
        account_create_call = ("INSERT INTO users (user_id, system, user_name, account, register) "
                               "VALUES({}, '{}', '{}', '{}',1)".format(message['sender_id'], message['system'],
                                                                       message['sender_screen_name'], sender_account))
        setDBData(account_create_call)

        account_create_text = "You didn't have an account set up, so I set one up for you.  Your account number is:"

        if message['system'] == 'twitter':
            getQRCode(message['sender_id'], sender_account, message['system'])
            path = ('/root/webhooks/qr/{}-{}.png'.format(message['sender_id'], message['system']))
            sendImg(message['sender_id'], path, account_create_text)
        elif message['system'] != 'twitter':
            sendDM(message['sender_id'], account_create_text, message['system'])
        sendDM(message['sender_id'], sender_account, message['system'])
        logging.info("{}: Created an account for the user!".format(str(datetime.now())))

    else:
        sender_account = account_data[0][0]
        sender_register = account_data[0][1]

        if sender_register == 0:
            set_register_call = ("UPDATE users SET register = 1 WHERE user_id = {} AND system = '{}' AND register = 0".format(message['sender_id'], message['system']))
            setDBData(set_register_call)

        account_text = "Your account number is:"

        if message['system'] == 'twitter':
            getQRCode(message['sender_id'], sender_account, message['system'])
            path = ('/root/webhooks/qr/{}-{}.png'.format(message['sender_id'], message['system']))
            sendImg(message['sender_id'], path, account_text)
        elif message['system'] != 'twitter':
            sendDM(message['sender_id'], account_text, message['system'])
        sendDM(message['sender_id'], sender_account, message['system'])
        logging.info("{}: Sent the user their account number.".format(str(datetime.now())))


def getQRCode(sender_id, sender_account, sm_system):
    """
    Check to see if a QR code has been generated for the sender_id / system combination.  If not, generate one.
    """
    qr_exists = os.path.isfile('/root/webhooks/qr/{}-{}.png'.format(sender_id, sm_system))

    if not qr_exists:
        print("No QR exists, generating a QR for account {}".format(sender_account))
        account_qr = pyqrcode.create('{}'.format(sender_account))
        account_qr.png('/root/webhooks/qr/{}-{}.png'.format(sender_id, sm_system), scale=4)


def sendImg(receiver, path, message):
    file = open(path, 'rb')
    qr_data = file.read()
    r = twitterAPI.request('media/upload', None, {'media': qr_data})

    if r.status_code == 200:
        media_id = r.json()['media_id']
        logging.info('media_id: {}'.format(media_id))
        msg_data = {'event':
                    {'type': 'message_create', 'message_create':
                        {'target':
                             {'recipient_id': '{}'.format(receiver)},
                         'message_data':
                             {'text': '{}'.format(message),
                              'attachment': {
                                  'type': 'media',
                                  'media': {
                                      'id':'{}'.format(media_id)
                                  }
                              }}
                         }
                     }
                }

        r = twitterAPI.request('direct_messages/events/new', json.dumps(msg_data))

        if r.status_code != 200:
            logging.info('ERROR: {} : {}'.format(r.status_code, r.text))


def withdrawProcess(message):
    """
    When the user sends !withdraw, send their entire balance to the provided account.  If there is no provided account
    reply with an error.
    """
    logging.info('{}: in withdrawProcess.'.format(datetime.now()))
    # check if there is a 2nd argument
    if 3 >= len(message['dm_array']) >= 2:
        # if there is, retrieve the sender's account and wallet
        withdraw_account_call = ("SELECT account FROM users where user_id = {} and system = '{}'".format(message['sender_id'], message['system']))
        withdraw_data = getDBData(withdraw_account_call)
        if not withdraw_data:
            withdraw_no_account_text = "You do not have an account.  Respond with !register to set one up."
            sendDM(message['sender_id'], withdraw_no_account_text, message['system'])
            logging.info("{}: User tried to withdraw with no account".format(str(datetime.now())))
        else:
            sender_account = withdraw_data[0][0]
            # check if there are pending blocks for the user's account
            receivePending(sender_account)
            # find the total balance of the account
            balance_return = rpc.account_balance(account='{}'.format(sender_account))
            if len(message['dm_array']) == 2:
                receiver_account = message['dm_array'][1].lower()
            else:
                receiver_account = message['dm_array'][2].lower()
            # if the balance is 0, send a message that they have nothing to withdraw
            if rpc.validate_account_number(receiver_account) == 0:
                invalid_account_text = ("The account number you provided is invalid.  Please double check and "
                                        "resend your request.")
                sendDM(message['sender_id'], invalid_account_text, message['system'])
                logging.info("{}: The xrb account number is invalid: {}".format(str(datetime.now()), receiver_account))
            elif balance_return['balance'] == 0:
                no_balance_text = ("You have 0 balance in your account.  Please deposit to your address {} to "
                                   "send more tips!".format(sender_account))
                sendDM(message['sender_id'], no_balance_text, message['system'])
                logging.info("{}: The user tried to withdraw with 0 balance".format(str(datetime.now())))
            else:
                # check to see if an amount to send was provided
                if len(message['dm_array']) == 3:
                    try:
                        withdraw_amount = Decimal(message['dm_array'][1])
                    except Exception as e:
                        logging.info("{}: ERROR: {}".format(datetime.now(), e))
                        invalid_amount_text = ("You did not send a number to withdraw.  Please resend with the format"
                                               "!withdraw <account> or !withdraw <amount> <account>")
                        sendDM(message['sender_id'], invalid_amount_text, message['system'])
                        return
                    withdraw_amount_raw = int(withdraw_amount * 1000000000000000000000000000000)
                    if Decimal(withdraw_amount_raw) > Decimal(balance_return['balance']):
                        not_enough_balance_text = ("You do not have that much NANO in your account.  To withdraw your "
                                                   "full amount, send !withdraw <account>")
                        sendDM(message['sender_id'], not_enough_balance_text, message['system'])
                        return
                else:
                    withdraw_amount_raw = balance_return['balance']
                    withdraw_amount = balance_return['balance'] / 1000000000000000000000000000000
                # send the total balance to the provided account
                work = getPOW(sender_account)
                if work == '':
                    logging.info("{}: processed without work".format(datetime.now()))
                    send_hash = rpc.send(wallet="{}".format(WALLET), source="{}".format(sender_account),
                                     destination="{}".format(receiver_account), amount=withdraw_amount_raw)
                else:
                    logging.info("{}: processed with work: {}".format(datetime.now(), work))
                    send_hash = rpc.send(wallet="{}".format(WALLET), source="{}".format(sender_account),
                                     destination="{}".format(receiver_account), amount=withdraw_amount_raw, work=work)
                logging.info("{}: send_hash = {}".format(datetime.now(), send_hash))
                # respond that the withdraw has been processed
                withdraw_text = ("You have successfully withdrawn {} NANO!  You can check the "
                                 "transaction at https://www.nanode.co/block/{}".format(withdraw_amount, send_hash))
                sendDM(message['sender_id'], withdraw_text, message['system'])
                logging.info("{}: Withdraw processed.  Hash: {}".format(str(datetime.now()), send_hash))
    else:
        incorrect_withdraw_text = "I didn't understand your withdraw request.  Please resend with !withdraw <optional:amount> <account>.  Example, !withdraw 1 xrb_aigakjkfa343tm3h1kj would withdraw 1 NANO to account xrb_aigakjkfa343tm3h1kj.  Also, !withdraw xrb_aigakjkfa343tm3h1kj would withdraw your entire balance to account xrb_aigakjkfa343tm3h1kj."
        sendDM(message['sender_id'], incorrect_withdraw_text, message['system'])
        logging.info("{}: User sent a withdraw with invalid syntax.".format(str(datetime.now())))



def donateProcess(message):
    """
    When the user sends !donate, send the provided amount from the user's account to the tip bot's donation wallet.
    If the user has no balance or account, reply with an error.
    """
    logging.info("{}: in donateProcess.".format(datetime.now()))

    if len(message['dm_array']) >= 2:
        sender_account_call = ("SELECT account FROM users where user_id = {} and system = '{}'".format(message['sender_id'], message['system']))
        donate_data = getDBData(sender_account_call)
        sender_account = donate_data[0][0]
        send_amount = message['dm_array'][1]

        receivePending(sender_account)

        balance_return = rpc.account_balance(account='{}'.format(sender_account))
        balance = balance_return['balance'] / 1000000000000000000000000000000
        receiver_account = BOT_ACCOUNT

        try:
            logging.info("{}: The user is donating {} NANO".format(str(datetime.now()), Decimal(send_amount)))
        except Exception as e:
            logging.info("{}: ERROR IN CONVERTING DONATION AMOUNT: {}".format(datetime.now(), e))
            wrong_donate_text = "Only number amounts are accepted.  Please resend as !donate 1234"
            sendDM(message['sender_id'], wrong_donate_text, message['system'])
            return ''

        if Decimal(balance) < Decimal(send_amount):
            large_donate_text = ("Your balance is only {} NANO and you tried to send {}.  Please add more NANO"
                                 " to your account, or lower your donation amount.".format(balance, Decimal(send_amount)))
            sendDM(message['sender_id'], large_donate_text, message['system'])
            logging.info("{}: User tried to donate more than their balance.".format(datetime.now()))

        elif Decimal(send_amount) < Decimal(MIN_TIP):
            small_donate_text = ("The minimum donation amount is {}.  Please update your donation amount "
                                 "and resend.".format(MIN_TIP))
            sendDM(message['sender_id'], small_donate_text, message['system'])
            logging.info("{}: User tried to donate less than 0.000001".format(datetime.now()))

        else:
            send_amount_raw = convert(send_amount, from_unit='XRB', to_unit='raw')
            work = getPOW(sender_account)
            if work == '':
                send_hash = rpc.send(wallet="{}".format(WALLET), source="{}".format(sender_account),
                                     destination="{}".format(receiver_account), amount="{:f}".format(send_amount_raw))
            else:
                send_hash = rpc.send(wallet="{}".format(WALLET), source="{}".format(sender_account),
                                     destination="{}".format(receiver_account), amount="{:f}".format(send_amount_raw),
                                     work=work)

            logging.info("{}: send_hash = {}".format(datetime.now(), send_hash))

            donate_text = ("Thank you for your generosity!  You have successfully donated {} NANO!  You can check the "
                           "transaction at https://www.nanode.co/block/{}".format(send_amount, send_hash))
            sendDM(message['sender_id'], donate_text, message['system'])
            logging.info("{}: {} NANO donation processed.  Hash: {}".format(str(datetime.now()), Decimal(send_amount), send_hash))

    else:
        incorrect_donate_text = "Incorrect syntax.  Please use the format !donate 1234"
        sendDM(message['sender_id'], incorrect_donate_text, message['system'])
        logging.info("{}: User sent a donation with invalid syntax".format(str(datetime.now())))




def setMessageInfo(status, message):
    """
    Set the tweet information into the message dictionary
    """
    logging.info("{}: in setMessageInfo".format(datetime.now()))
    if status.get('retweeted_status'):
        logging.info("{}: Retweets are ignored.".format(datetime.now(TIMEZONE)))
        message['id'] = None
    else:
        message['id'] = status.get('id')
        message['sender_id_str'] = status.get('user',{}).get('id_str')
        message['sender_id'] = Decimal(message['sender_id_str'])

        if Decimal(message['sender_id']) == Decimal(BOT_ID_TWITTER):
            logging.info('Messages from the bot are ignored.')
            message['id'] = None
            return

        message['sender_screen_name'] = status.get('user',{}).get('screen_name')

        if status.get('truncated') is False:
            dm_text = status.get('text')
        else:
            dm_text = status.get('extended_tweet',{}).get('full_text')

        dm_text = dm_text.replace('\n', ' ')
        dm_text = dm_text.lower()

        message['text'] = dm_text.split(" ")


def checkMessageAction(message):
    """
    Check to see if there are any key action values mentioned in the tweet.
    """
    logging.info("{}: in checkMessageAction.".format(datetime.now()))
    try:
        message['action_index'] = message['text'].index("!tip")
    except ValueError:
        message['action'] = None
        return

    message['action'] = message['text'][message['action_index']].lower()
    message['starting_point'] = message['action_index'] + 1


def validateTipAmount(message):
    """
    Validate the tweet includes an amount to tip, and if that tip amount is greater than the minimum tip amount.
    """
    logging.info("{}: in validateTipAmount".format(datetime.now()))
    try:
        message['tip_amount'] = Decimal(message['text'][message['starting_point']])
    except Exception:
        logging.info("{}: Tip amount was not a number: {}".format(datetime.now(),
                                                                  message['text'][message['starting_point']]))
        not_a_number_text = 'Looks like the value you entered to tip was not a number.  You can try to tip ' \
                            'again using the format !tip 1234 @username'
        sendReply(message, not_a_number_text)

        message['tip_amount'] = -1
        return

    if Decimal(message['tip_amount']) < Decimal(MIN_TIP):
        min_tip_text = ("The minimum tip amount is {} NANO.  Please update your tip amount and try again."
                        .format(MIN_TIP))
        sendReply(message, min_tip_text)

        message['tip_amount'] = -1
        logging.info("{}: User tipped less than {} NANO.".format(datetime.now(TIMEZONE), MIN_TIP))
        return

    try:
        message['tip_amount_raw'] = convert(message['tip_amount'], from_unit='XRB', to_unit='raw')
    except Exception as e:
        logging.info("{}: Exception converting tip_amount to tip_amount_raw".format(datetime.now(TIMEZONE)))
        logging.info("{}: {}".format(datetime.now(TIMEZONE), e))

    # create a string to remove scientific notation from small decimal tips
    if str(message['tip_amount'])[0] == ".":
        message['tip_amount_text'] = "0{}".format(str(message['tip_amount']))
    else:
        message['tip_amount_text'] = str(message['tip_amount'])


def setTipList(message, users_to_tip):
    """
    Loop through the message starting after the tip amount and identify any users that were tagged for a tip.  Add the
    user object to the users_to_tip dict to process the tips.
    """
    logging.info("{}: in setTipList.".format(datetime.now()))

    if message['system'] == 'twitter':
        for index in range(message['starting_point'] + 1, len(message['text'])):
            if len(message['text'][index]) > 0:
                if str(message['text'][index][0]) == "@" and str(message['text'][index]).lower() != (
                        "@" + str(message['sender_screen_name']).lower()):
                    try:
                        user_info = api.get_user(message['text'][index])
                    except tweepy.TweepError as e:
                        logging.info("{}: The user sent a !tip command with a mistyped user: {}".format(
                                datetime.now(TIMEZONE), message['text'][index]))
                        logging.info("{}: Tweep error: {}".format(datetime.now(TIMEZONE), e))
                        return

                    user_dict = {'receiver_id': user_info.id, 'receiver_screen_name': user_info.screen_name,
                                 'receiver_account': None, 'receiver_register': None}
                    users_to_tip.append(user_dict)
                    logging.info("{}: Users_to_tip: {}".format(datetime.now(TIMEZONE), users_to_tip))



    if message['system'] == 'facebook':
        post_url = 'https://graph.facebook.com/{}?access_token={}&fields=message_tags'.format(message['id'],
                                                                                              PAGE_ACCESS_TOKEN)
        try:
            r = requests.get(post_url, headers={"Content-Type": "application/json"})
            rx = r.json()
            if 'message_tags' in rx:
                for user in rx['message_tags']:
                    if user['type'] == 'user':
                        user_dict = {'receiver_id': user['id'], 'receiver_screen_name': user['name'],
                                     'receiver_account': None, 'receiver_register': None}
                        users_to_tip.append(user_dict)
                logging.info("{}: populated users_to_tip: {}".format(datetime.now(), users_to_tip))

        except Exception as e:
            logging.info("{}: ERROR: {}".format(datetime.now(), e))
            pass

    if message['system'] == 'telegram':
        logging.info("trying to set tiplist in telegram: {}".format(message))
        for index in range(message['starting_point'] + 1, len(message['text'])):
            if len(message['text'][index]) > 0:
                if str(message['text'][index][0]) == "@" and str(message['text'][index]).lower() != ("@" + str(message['sender_screen_name']).lower()):
                    check_user_call = ("SELECT member_id, member_name FROM telegram_chat_members "
                                       "WHERE chat_id = {} and member_name = '{}'".format(message['chat_id'], message['text'][index][1:]))

                    user_check_data = getDBData(check_user_call)
                    if user_check_data:
                        receiver_id = user_check_data[0][0]
                        receiver_screen_name = user_check_data[0][1]

                        user_dict = {'receiver_id': receiver_id, 'receiver_screen_name': receiver_screen_name,
                                 'receiver_account': None, 'receiver_register': None}
                        users_to_tip.append(user_dict)
                    else:
                        logging.info("User not found in DB: chat ID:{} - member name:{}".format(message['chat_id'], message['text'][index][1:]))
                        missing_user_message = ("{} not found in our records.  In order to tip them, they need to be a " 
                                               "member of the channel.  If they are in the channel, please have them send a message in the chat so I can add them.".format(message['text'][index]))
                        sendReply(message, missing_user_message)

    logging.info("{}: Users_to_tip: {}".format(datetime.now(TIMEZONE), users_to_tip))
    message['total_tip_amount'] = message['tip_amount']
    if len(users_to_tip) > 0 and message['tip_amount'] != -1:
        message['total_tip_amount'] *= len(users_to_tip)

    else:
        return


def validateSender(message):
    """
    Validate that the sender has an account with the tip bot, and has enough NANO to cover the tip.
    """
    logging.info("{}: validating sender".format(datetime.now()))
    logging.info("sender id: {}".format(message['sender_id']))
    logging.info("system: {}".format(message['system']))
    db_call = "SELECT account, register FROM users where user_id = {} AND system = '{}'".format(message['sender_id'], message['system'])
    sender_account_info = getDBData(db_call)

    if not sender_account_info:
        no_account_text = "You do not have an account with the bot.  Please send a DM to me with !register to set up an account."
        sendReply(message, no_account_text)

        logging.info("{}: User tried to send a tip without an account.".format(datetime.now(TIMEZONE)))
        message['sender_account'] = None
        return

    message['sender_account'] = sender_account_info[0][0]
    message['sender_register'] = sender_account_info[0][1]

    if message['sender_register'] != 1:
        db_call = "UPDATE users SET register = 1 WHERE user_id = {} AND system = '{}'".format(message['sender_id'], message['system'])
        setDBData(db_call)

    receivePending(message['sender_account'])
    message['sender_balance_raw'] = rpc.account_balance(account='{}'.format(message['sender_account']))
    message['sender_balance'] = message['sender_balance_raw']['balance'] / 1000000000000000000000000000000


def validateTotalTipAmount(message):
    """
    Validate that the sender has enough Nano to cover the tip to all users
    """
    logging.info("{}: validating total tip amount".format(datetime.now()))
    if message['sender_balance_raw']['balance'] < (message['total_tip_amount'] * 1000000000000000000000000000000):
        not_enough_text = ("You do not have enough NANO to cover this {} NANO tip.  Please check your balance by "
                           "sending a DM to me with !balance and retry.".format(message['total_tip_amount']))
        sendReply(message, not_enough_text)


        logging.info("{}: User tried to send more than in their account.".format(datetime.now(TIMEZONE)))
        message['tip_amount'] = -1
        return


def stripEmoji(text):
    """
    Remove Emojis from tweet text to prevent issues with logging
    """
    logging.info('{}: removing emojis'.format(datetime.now()))
    text = str(text)
    return RE_EMOJI.sub(r'', text)


def setDBDataTip(message, users_to_tip, index):
    """
    Special case to update DB information to include tip data
    """
    logging.info("{}: inserting tip into DB.".format(datetime.now()))
    db = MySQLdb.connect(host=DB_HOST, port=3306, user=DB_USER, passwd=DB_PW, db=DB_SCHEMA, use_unicode=True,
                         charset="utf8")
    try:
        db_cursor = db.cursor()
        db_cursor.execute("INSERT INTO tip_list (dm_id, tx_id, processed, sender_id, receiver_id, system, dm_text, amount)"
                          " VALUES (%s, %s, 2, %s, %s, %s, %s, %s)",
                          (message['id'], message['tip_id'], message['sender_id'],
                           users_to_tip[index]['receiver_id'], message['system'], message['text'],
                           Decimal(message['tip_amount'])))
        db.commit()
        db_cursor.close()
        db.close()
    except Exception as e:
        logging.info("{}: Exception in setDBDataTip".format(datetime.now()))
        logging.info("{}: {}".format(datetime.now(), e))
        raise e


def sendTip(message, users_to_tip, tip_index):
    """
    Process tip for specified user
    """
    logging.info("{}: sending tip to {}".format(datetime.now(), users_to_tip[tip_index]['receiver_screen_name']))
    if str(users_to_tip[tip_index]['receiver_id']) == str(message['sender_id']):
        self_tip_text = "Self tipping is not allowed.  Please use this bot to spread the $NANO to other Twitter users!"
        sendReply(message, self_tip_text)

        logging.info("{}: User tried to tip themself").format(datetime.now())
        return

    # Check if the receiver has an account
    receiver_account_get = ("SELECT account FROM users where user_id = {} and system = '{}'".format(int(users_to_tip[tip_index]['receiver_id']), message['system']))
    receiver_account_data = getDBData(receiver_account_get)
    # If they don't, create an account for them
    if not receiver_account_data:
        users_to_tip[tip_index]['receiver_account'] = rpc.account_create(wallet="{}".format(WALLET), work=True)
        create_receiver_account = ("INSERT INTO users (user_id, system, user_name, account, register) VALUES({}, '{}', '{}', "
                                   "'{}',0)".format(users_to_tip[tip_index]['receiver_id'], message['system'],
                                                    users_to_tip[tip_index]['receiver_screen_name'],
                                                    users_to_tip[tip_index]['receiver_account']))
        setDBData(create_receiver_account)
        logging.info("{}: Sender sent to a new receiving account.  Created  account {}".format(
            datetime.now(TIMEZONE), users_to_tip[tip_index]['receiver_account']))
    else:
        users_to_tip[tip_index]['receiver_account'] = receiver_account_data[0][0]

    # Send the tip
    message['tip_id'] = "{}{}".format(message['id'], tip_index)

    work = getPOW(message['sender_account'])
    if work == '':
        message['send_hash'] = rpc.send(wallet="{}".format(WALLET), source="{}".format(message['sender_account']),
                                    destination="{}".format(users_to_tip[tip_index]['receiver_account']),
                                    amount="{:f}".format(message['tip_amount_raw']),
                                    id="tip-{}".format(message['tip_id']))
    else:
        message['send_hash'] = rpc.send(wallet="{}".format(WALLET), source="{}".format(message['sender_account']),
                                    destination="{}".format(users_to_tip[tip_index]['receiver_account']),
                                    amount="{:f}".format(message['tip_amount_raw']),
                                    work=work,
                                    id="tip-{}".format(message['tip_id']))
    # Update the DB
    message['text'] = stripEmoji(message['text'])
    setDBDataTip(message, users_to_tip, tip_index)

    # Get receiver's new balance
    try:
        receivePending(users_to_tip[tip_index]['receiver_account'])
        balance_return = rpc.account_balance(account="{}".format(users_to_tip[tip_index]['receiver_account']))
        users_to_tip[tip_index]['balance'] = balance_return['balance'] / 1000000000000000000000000000000

        # create a string to remove scientific notation from small decimal tips
        if str(users_to_tip[tip_index]['balance'])[0] == ".":
            users_to_tip[tip_index]['balance'] = "0{}".format(str(users_to_tip[tip_index]['balance']))
        else:
            users_to_tip[tip_index]['balance'] = str(users_to_tip[tip_index]['balance'])

        # Send a DM to the receiver
        receiver_tip_text = ("@{} just sent you a {} NANO tip! Your new balance is {} NANO.  If you have not registered an account,"
                             " send a reply with !register to get started, or !help to see a list of "
                             "commands!  Learn more about NANO at https://nano.org/".format(
                              message['sender_screen_name'], message['tip_amount_text'], users_to_tip[tip_index]['balance']))
        sendDM(users_to_tip[tip_index]['receiver_id'], receiver_tip_text, message['system'])
    except Exception as e:
        logging.info("{}: ERROR IN RECEIVING NEW TIP - POSSIBLE NEW ACCOUNT NOT REGISTERED WITH DPOW: {}".format(datetime.now(), e))

    logging.info(
        "{}: tip sent to {} via hash {}".format(datetime.now(TIMEZONE), users_to_tip[tip_index]['receiver_screen_name'],
                                                message['send_hash']))


def tipProcess(message, users_to_tip):
    """
    Main orchestration process to handle tips
    """
    logging.info("{}: in tipProcess".format(datetime.now()))
    setTipList(message, users_to_tip)
    if len(users_to_tip) < 1 and message['system'] != 'telegram':
        no_users_text = "Looks like you didn't enter in anyone to tip, or you mistyped someone's handle.  You can try " \
                        "to tip again using the format !tip 1234 @username"
        sendReply(message, no_users_text)
        return

    validateSender(message)
    if message['sender_account'] is None or message['tip_amount'] <= 0:
        return

    validateTotalTipAmount(message)
    if message['tip_amount'] <= 0:
        return

    for index in range(0, len(users_to_tip)):
        sendTip(message, users_to_tip, index)

    # Inform the user that all tips were sent.
    if len(users_to_tip) >= 2:
        multi_tip_success = ("You have successfully sent your {} $NANO tips.  Check your account at nanode.co/account/{}"
                             .format(message['tip_amount_text'], message['sender_account']))
        sendReply(message, multi_tip_success)


    elif len(users_to_tip) == 1:
        tip_success = ("You have successfully sent your {} $NANO tip.  Check your account at nanode.co/account/{}"
                       .format(message['tip_amount_text'], message['sender_account']))
        sendReply(message, tip_success)


def getPOW(sender_account):
    """
    Retrieves the frontier (hash of previous transaction) of the provided account and generates work for the next block.
    """
    logging.info("{}: in getPOW".format(datetime.now()))
    try:
        account_frontiers = rpc.accounts_frontiers(accounts=["{}".format(sender_account)])
        hash = account_frontiers[sender_account]
    except Exception as e:
        logging.info("{}: Error checking frontier: {}".format(datetime.now(), e))
        return ''
    logging.info("account_frontiers: {}".format(account_frontiers))

    work = ''
    logging.info("{}: hash: {}".format(datetime.now(), hash))
    while work == '':
        try:
            work_data = {'hash': hash, 'key': WORK_KEY}
            json_request = json.dumps(work_data)
            r = requests.post('{}'.format(WORK_SERVER), data=json_request)
            rx = r.json()
            work = rx['work']
            logging.info("{}: Work generated: {}".format(datetime.now(), work))
        except Exception as e:
            logging.info("{}: ERROR GENERATING WORK: {}".format(datetime.now(), e))
            pass

    return work


def parseAction(message):
    if message['dm_action'] == '!help' or message['dm_action'] == '/help' or message['dm_action'] == '/start':
        new_pid = os.fork()
        if new_pid == 0:
            try:
                helpProcess(message)
            except Exception as e:
                logging.info("Exception: {}".format(e))
                raise e
            os._exit(0)
        else:
            return '', HTTPStatus.OK


    elif message['dm_action'] == '!balance' or message['dm_action'] == '/balance':
        new_pid = os.fork()
        if new_pid == 0:
            try:
                balanceProcess(message)
            except Exception as e:
                logging.info("Exception: {}".format(e))
                raise e
            os._exit(0)
        else:
            return '', HTTPStatus.OK

    elif message['dm_action'] == '!register' or message['dm_action'] == '/register':
        new_pid = os.fork()
        if new_pid == 0:
            try:
                registerProcess(message)
            except Exception as e:
                logging.info("Exception: {}".format(e))
                raise e
            os._exit(0)
        else:
            return '', HTTPStatus.OK

    elif message['dm_action'] == '!tip' or message['dm_action'] == '/tip':
        new_pid = os.fork()
        if new_pid == 0:
            try:
                redirect_tip_text = "Tips are processed through public messages now.  Please send in the format @NanoTipBot !tip .0001 @user1."
                sendDM(message['sender_id'], redirect_tip_text, message['system'])
            except Exception as e:
                logging.info("Exception: {}".format(e))
                raise e
            os._exit(0)
        else:
            return '', HTTPStatus.OK

    elif message['dm_action'] == '!withdraw' or message['dm_action'] == '/withdraw':
        new_pid = os.fork()
        if new_pid == 0:
            try:
                withdrawProcess(message)
            except Exception as e:
                logging.info("Exception: {}".format(e))
                raise e
            os._exit(0)
        else:
            return '', HTTPStatus.OK

    elif message['dm_action'] == '!donate' or message['dm_action'] == '/donate':
        new_pid = os.fork()
        if new_pid == 0:
            try:
                donateProcess(message)
            except Exception as e:
                logging.info("Exception: {}".format(e))
                raise e
            os._exit(0)
        else:
            return '', HTTPStatus.OK

    elif message['dm_action'] == '!account' or message['dm_action'] == '/account':
        new_pid = os.fork()
        if new_pid == 0:
            try:
                accountProcess(message)
            except Exception as e:
                logging.info("Exception: {}".format(e))
                raise e
            os._exit(0)
        else:
            return '', HTTPStatus.OK

    elif message['dm_action'] == '!privatetip' or message['dm_action'] == '/privatetip':
        new_pid = os.fork()
        if new_pid == 0:
            try:
                redirect_tip_text = "Private Tip is under maintenance.  To send your tip, use the !tip function in a tweet or reply!"
                sendDM(message['sender_id'], redirect_tip_text, message['system'])
            except Exception as e:
                logging.info("Exception: {}".format(e))
                raise e
            os._exit(0)
        else:
            return '', HTTPStatus.OK

    else:
        new_pid = os.fork()
        if new_pid == 0:
            try:
                wrong_format_text = (
                    "The command or syntax you sent is not recognized.  Please send !help for a list of "
                    "commands and what they do.")
                sendDM(message['sender_id'], wrong_format_text, message['system'])
                logging.info('unrecognized syntax')
            except Exception as e:
                logging.info("Exception: {}".format(e))
                raise e
            os._exit(0)
        else:
            return '', HTTPStatus.OK

    return '', HTTPStatus.OK


def getFBName(message):

    post_url = 'https://graph.facebook.com/v2.11/{}?access_token={}&fields=name'.format(message['sender_id'],PAGE_ACCESS_TOKEN)
    try:
        r = requests.get(post_url, headers={"Content-Type": "application/json"})
        rx = r.json()
        message['sender_screen_name'] = rx['name']

    except Exception as e:
        logging.info("{}: ERROR: {}".format(datetime.now(), e))
        pass


def sendReply(message, text):
    if message['system'] == 'twitter':
        text = '@{} '.format(message['sender_screen_name']) + text
        try:
            api.update_status(text, message['id'])
        except tweepy.TweepError as e:
            logging.info("{}: Tweepy Error: {}".format(datetime.now(TIMEZONE), e))

    elif message['system'] == 'facebook':
        message['system'] = 'facebook2'
        logging.info("{}: sending message: {}".format(datetime.now(), text))
        post_url = 'https://graph.facebook.com/v3.1/{}/likes?access_token={}'.format(message['id'],PAGE_ACCESS_TOKEN)
        sendDM(message['sender_id'], text, message['system'])
        try:
            r = requests.post(post_url, headers={"Content-Type": "application/json"})
            logging.info("{}: response: {} - {}".format(datetime.now(), r, r.text))
        except Exception as e:
            logging.info("{}: ERROR: {}".format(datetime.now(), e))
            pass

    elif message['system'] == 'telegram':
        telegram_bot.sendMessage(chat_id=message['chat_id'], text=text)



def checkTelegramMember(chat_id, chat_name, member_id, member_name):
    check_user_call = ("SELECT member_id, member_name FROM telegram_chat_members "
                       "WHERE chat_id = {} and member_name = '{}'".format(chat_id,
                                                                          member_name))
    user_check_data = getDBData(check_user_call)

    logging.info("checking if user exists")
    if not user_check_data:
        logging.info("{}: User {}-{} not found in DB, inserting".format(datetime.now(), chat_id, member_name))
        new_chat_member_call = ("INSERT INTO telegram_chat_members (chat_id, chat_name, member_id, member_name) "
                                "VALUES ({}, '{}', {}, '{}')".format(chat_id, chat_name, member_id, member_name))
        setDBData(new_chat_member_call)

    return


# Flask routing
@app.route('/tutorial')
@app.route('/tutorial.html')
def tutorial():
    return render_template('tutorial.html')


@app.route('/about')
@app.route('/about.html')
def about():
    return render_template('about.html')


@app.route('/contact')
@app.route('/contact.html')
def contact():
    return render_template('contact.html')


@app.route('/contact-form-handler')
@app.route('/contact-form-handler.php')
def contacthandler():
    return render_template('contact-form-handler.php')


@app.route('/contact-form-thank-you')
@app.route('/contact-form-thank-you.html')
def thanks():
    return render_template('contact-form-thank-you.html')


@app.route('/tippers')
@app.route('/tippers.html')
def tippers():
    largest_tip = ("select user_name, amount, account, a.system, timestamp FROM tip_bot.tip_list as a, tip_bot.users as b "
                   "WHERE user_id = sender_id and user_name is NOT NULL and processed = 2 and user_name != 'mitche50' and amount = (select max(amount) from tip_bot.tip_list) "
                   "ORDER BY timestamp desc "
                   "limit 1;")

    tippers_call = ("SELECT user_name as 'screen_name', sum(amount) as 'total_tips', account, b.system "
                    "FROM tip_bot.tip_list as a, tip_bot.users as b "
                    "where user_id = sender_id and user_name is NOT NULL and receiver_id IN (SELECT user_id FROM tip_bot.users)"
                    "group by sender_id "
                    "order by sum(amount) desc "
                    "limit 15")

    tipper_table = getDBData(tippers_call)
    top_tipper = getDBData(largest_tip)
    top_tipper_date = top_tipper[0][4].date()
    return render_template('tippers.html', tipper_table=tipper_table, top_tipper=top_tipper, top_tipper_date=top_tipper_date)


@app.route('/tiplist')
def tip_list():
    tip_list_call = ("SELECT t1.user_name as 'Sender ID', t2.user_name as 'Receiver ID', t1.amount, "
                     "t1.account as 'Sender Account', t2.account as 'Receiver Account', t1.system, t1.timestamp "
                     "FROM "
                     "(SELECT user_name, amount, account, a.system, timestamp "
                     "FROM tip_bot.tip_list as a, tip_bot.users as b "
                     "WHERE user_id = sender_id and user_name is NOT NULL and processed = 2 and user_name != 'mitche50' "
                     "ORDER BY timestamp desc "
                     "limit 50) as t1 "
                     "JOIN "
                     "(SELECT user_name, account, timestamp "
                     "FROM tip_bot.tip_list, tip_bot.users "
                     "WHERE user_id = receiver_id and user_name is NOT NULL and processed = 2 "
                     "ORDER BY timestamp desc "
                     "limit 50) as t2 "
                     "ON "
                     "t1.timestamp = t2.timestamp")
    tip_list_table = getDBData(tip_list_call)
    print(tip_list_table)
    return render_template('tiplist.html', tip_list_table=tip_list_table)

@app.route('/')
@app.route('/index.html')
def index():
    r = requests.get('https://api.coinmarketcap.com/v2/ticker/1567/')
    rx = r.json()
    price = round(rx['data']['quotes']['USD']['price'], 2)

    total_tipped_nano = ("SELECT system, sum(amount) as total "
                         "FROM tip_bot.tip_list "
                         "WHERE receiver_id IN (SELECT user_id FROM tip_bot.users) "
                         "GROUP BY system "
                         "ORDER BY total desc")

    total_tipped_number = ("SELECT system, count(system) as notips "
                           "FROM tip_bot.tip_list "
                           "WHERE receiver_id IN (SELECT user_id FROM tip_bot.users)"
                           "GROUP BY system "
                           "ORDER BY notips desc")

    total_tipped_nano_table = getDBData(total_tipped_nano)
    total_tipped_number_table = getDBData(total_tipped_number)
    total_value_usd = round(total_tipped_number_table[0][1] * price,2)

    logging.info("total_value_usd: {}".format(total_value_usd))
    logging.info("total_tipped_nano_table = {}".format(total_tipped_nano_table))
    logging.info("total_tipped_number_table = {}".format(total_tipped_number_table))
    return render_template('index.html', total_tipped_nano_table=total_tipped_nano_table, total_tipped_number_table=total_tipped_number_table, total_value_usd=total_value_usd, price=price)


@app.route('/webhooks/twitter', methods=["GET"])
def webhook_challenge():
    # creates HMAC SHA-256 hash from incoming token and your consumer secret

    crc = request.args.get('crc_token')

    validation = hmac.new(
      key=bytes(key, 'utf-8'),
      msg=bytes(crc, 'utf-8'),
      digestmod = hashlib.sha256
    )

    digested = base64.b64encode(validation.digest())

    # construct response data with base64 encoded hash
    response = {
      'response_token': 'sha256=' + format(str(digested)[2:-1])
    }

    return json.dumps(response), 200


@app.route('/webhooks/facebook', methods=["GET"])
def facebook_webhook():
    # respond to Facebook webhook challenge
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')

    if mode and token:
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            logging.info("Facebook webhook verified")
            return challenge, 200

    logging.info("Facebook webhook tried but not validated.")
    return '', HTTPStatus.OK


@app.route('/webhooks/telegram/set_webhook')
def telegram_webhook():
    response = telegram_bot.setWebhook('https://nanotipbot.com/webhooks/telegram')
    if response:
        return "Webhook setup successfully"
    else:
        return "Error {}".format(response)


@app.route('/webhooks/telegram', methods=["POST"])
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
    logging.info("request_json: {}".format(request_json))
    if 'message' in request_json.keys():
        if request_json['message']['chat']['type'] == 'private':
            logging.info("Direct message received in Telegram.  Processing.")
            message['sender_id'] = request_json['message']['from']['id']

            message['sender_screen_name'] = request_json['message']['from']['username']
            message['dm_id'] = request_json['update_id']
            message['text'] = request_json['message']['text']
            message['dm_array'] = message['text'].split(" ")
            message['dm_action'] = message['dm_array'][0].lower()

            logging.info("{}: action identified: {}".format(datetime.now(), message['dm_action']))

            parseAction(message)

        elif request_json['message']['chat']['type'] == 'supergroup' or request_json['message']['chat']['type'] == 'group':
            if 'text' in request_json['message']:
                message['sender_id'] = request_json['message']['from']['id']
                message['sender_screen_name'] = request_json['message']['from']['username']
                message['id'] = request_json['message']['message_id']
                message['chat_id'] = request_json['message']['chat']['id']
                message['chat_name'] = request_json['message']['chat']['title']

                checkTelegramMember(message['chat_id'], message['chat_name'], message['sender_id'], message['sender_screen_name'])

                message['text'] = request_json['message']['text']
                message['text'] = message['text'].replace('\n', ' ')
                message['text'] = message['text'].lower()
                message['text'] = message['text'].split(' ')



                checkMessageAction(message)
                if message['action'] is None:
                    logging.info("{}: Mention of nano tip bot without a !tip command.".format(datetime.now(TIMEZONE)))
                    return '', HTTPStatus.OK

                validateTipAmount(message)
                if message['tip_amount'] <= 0:
                    return '', HTTPStatus.OK

                if message['action'] != -1 and str(message['sender_id']) != str(BOT_ID_FACEBOOK):
                    new_pid = os.fork()
                    if new_pid == 0:
                        try:
                            tipProcess(message, users_to_tip)
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
                member_name = request_json['message']['new_chat_member']['username']

                new_chat_member_call = ("INSERT INTO telegram_chat_members (chat_id, chat_name, member_id, member_name) "
                                        "VALUES ({}, '{}', {}, '{}')".format(chat_id, chat_name, member_id, member_name))
                setDBData(new_chat_member_call)

            elif 'left_chat_member' in request_json['message']:
                chat_id = request_json['message']['chat']['id']
                chat_name = request_json['message']['chat']['title']
                member_id = request_json['message']['left_chat_member']['id']
                member_name = request_json['message']['left_chat_member']['username']
                logging.info("member {}-{} left chat {}-{}, removing from DB.".format(member_id, member_name, chat_id, chat_name))

                remove_member_call = ("DELETE FROM telegram_chat_members "
                                      "WHERE chat_id = {} AND member_id = {}".format(chat_id, member_id))
                setDBData(remove_member_call)

            elif 'group_chat_created' in request_json['message']:
                chat_id = request_json['message']['chat']['id']
                chat_name = request_json['message']['chat']['title']
                member_id = request_json['message']['from']['id']
                member_name = request_json['message']['from']['username']
                logging.info("member {} created chat {}, inserting creator into DB.".format(member_name, chat_name))

                new_chat_call = ("INSERT INTO telegram_chat_members (chat_id, chat_name, member_id, member_name) "
                    "VALUES ({}, '{}', {}, '{}')".format(chat_id, chat_name, member_id, member_name))
                setDBData(new_chat_call)

        else:
            logging.info("request: {}".format(request_json))


    return 'ok'


@app.route('/webhooks/facebook', methods=["POST"])
def facebook_event():
    message = {}
    users_to_tip = []

    message['system'] = 'facebook'
    request_json = request.get_json()
    logging.info(request_json)

    object = request_json['object']
    entry = request_json['entry']

    if 'messaging' in entry[0]:
        webhook_event = entry[0]['messaging']
        message['sender_id'] = entry[0]['messaging'][0]['sender']['id']
        getFBName(message)

        if object == 'page' and message['sender_id'] != BOT_ID_FACEBOOK and 'message' in webhook_event[0]:
            message['text'] = entry[0]['messaging'][0]['message']['text']
            message['dm_array'] = message['text'].split(" ")
            message['dm_action'] = message['dm_array'][0].lower()

            parseAction(message)

    elif 'changes' in entry[0]:
        logging.info("{}: post received".format(datetime.now()))
        webhook_event = entry[0]['changes']

        if webhook_event[0]['value']['verb'] == 'remove':
            logging.info("post deleted, ignore this")
            return '', HTTPStatus.OK

        elif 'field' in webhook_event[0]['value']:
            if webhook_event[0]['value']['field'] == 'mention':
                logging.info("mention received")
                return '', HTTPStatus.OK
            else:
                return '', HTTPStatus.OK

        else:
            message['sender_id'] = webhook_event[0]['value']['from']['id']
            message['sender_screen_name'] = webhook_event[0]['value']['from']['name']
            message['id'] = webhook_event[0]['value']['post_id']
            message['text'] = webhook_event[0]['value']['message']
            message['text'] = message['text'].replace('\n', ' ')
            message['text'] = message['text'].lower()
            message['text'] = message['text'].split(' ')

            checkMessageAction(message)
            if message['action'] is None:
                logging.info("{}: Mention of nano tip bot without a !tip command.".format(datetime.now(TIMEZONE)))
                return '', HTTPStatus.OK

            validateTipAmount(message)
            if message['tip_amount'] <= 0:
                return '', HTTPStatus.OK

            if message['action'] != -1 and str(message['sender_id']) != str(BOT_ID_FACEBOOK):
                new_pid = os.fork()
                if new_pid == 0:
                    try:
                        tipProcess(message, users_to_tip)
                    except Exception as e:
                        logging.info("Exception: {}".format(e))
                        raise e

                    os._exit(0)
                else:
                    return '', HTTPStatus.OK

    return '', HTTPStatus.OK


@app.route("/webhooks/twitter", methods=["POST"])
def twitterEventReceived():
    message = {}
    users_to_tip = []

    message['system'] = 'twitter'
    request_json = request.get_json()

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

        logging.info("Processing direct message.")

        # Update DB with new DM
        dm_insert_call = ("INSERT INTO dm_list (dm_id, processed, sender_id, dm_text) "
                          "VALUES ({}, 0, {}, '{}')".format(message['dm_id'], message['sender_id'], message['text']))
        setDBData(dm_insert_call)

        logging.info("{}: action identified: {}".format(datetime.now(), message['dm_action']))
        # Check for action on DM
        parseAction(message)

    elif 'tweet_create_events' in request_json.keys():
        """
        A tweet was received.  The bot will parse the tweet, see if there are any tips and process them.
        Error handling will cover if the sender doesn't have an account, doesn't have enough to cover the tips,
        sent to an invalid username, didn't send an amount to tip or didn't send a !tip command.
        """

        tweet_object = request_json['tweet_create_events'][0]

        setMessageInfo(tweet_object, message)
        if message['id'] is None:
            return '', HTTPStatus.OK

        checkMessageAction(message)
        if message['action'] is None:
            logging.info("{}: Mention of nano tip bot without a !tip command.".format(datetime.now(TIMEZONE)))
            return '', HTTPStatus.OK

        validateTipAmount(message)
        if message['tip_amount'] <= 0:
            return '', HTTPStatus.OK

        logging.info("{}: User Screen Name: {}".format(datetime.now(TIMEZONE), message['sender_screen_name']))
        logging.info(u'{}: Text of dm: {}'.format(datetime.now(TIMEZONE), message['text']))

        if message['action'] != -1 and str(message['sender_id']) != str(BOT_ID_TWITTER):
            new_pid = os.fork()
            if new_pid == 0:
                try:
                    tipProcess(message, users_to_tip)
                except Exception as e:
                    logging.info("Exception: {}".format(e))
                    raise e

                os._exit(0)
            else:
                return '', HTTPStatus.OK

        elif str(message['sender_id']) == str(BOT_ID_TWITTER):
            logging.info("{}: TipBot sent a message.".format(datetime.now(TIMEZONE)))

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

        helpProcess(message)

        return '', HTTPStatus.OK

    else:
        # Event type not supported
        return '', HTTPStatus.OK

if __name__ == "__main__":
    app.run()
