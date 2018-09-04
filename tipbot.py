from flask import Flask, render_template, request, send_from_directory, make_response
from TwitterAPI import TwitterAPI
from datetime import datetime
from decimal import *
from http import HTTPStatus
from pytz import timezone
from nano import convert
import MySQLdb, re, requests, base64, hashlib, hmac, json, logging, configparser, nano, tweepy, os, time

# Set Log File
logging.basicConfig(handlers=[logging.FileHandler('/root/webhooks/twitter.log', 'a', 'utf-8')],
                    level=logging.INFO)

# Read config and parse constants
config = configparser.ConfigParser()
config.read('config.ini')

# Twitter API connection settings
CONSUMER_KEY = config.get('main', 'consumer_key')
CONSUMER_SECRET = config.get('main', 'consumer_secret')
ACCESS_TOKEN = config.get('main', 'access_token')
ACCESS_TOKEN_SECRET = config.get('main', 'access_token_secret')

# DB connection settings
DB_HOST = config.get('main', 'host')
DB_USER = config.get('main', 'user')
DB_PW = config.get('main', 'password')
DB_SCHEMA = config.get('main', 'schema')

# Nano Node connection settings
WALLET = config.get('main', 'wallet')
NODE_IP = config.get('main', 'node_ip')
BOT_ID = config.get('main', 'bot_id')
BOT_NAME = config.get('main', 'bot_name')
BOT_ACCOUNT = config.get('main', 'bot_account')
MIN_TIP = config.get('main', 'min_tip')
WORK_SERVER = config.get('main', 'work_server')
RE_EMOJI = re.compile('[\U00010000-\U0010ffff\U000026A1]', flags=re.UNICODE)
TIMEZONE = timezone('US/Eastern')
BULLET = u"\u2022"

# Set key for webhook challenege from Twitter
key = config.get('main', 'consumer_secret')

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
                # Try to receive blocks using json
                # work = getPOW(sender_account) - Activate to enable the dPoW system
                receive_data = {'action': "receive", 'wallet': WALLET, 'account': sender_account, 'block': block}
                # receive_data['work'] = work - Activate to enable the dPoW system
                receive_json = json.dumps(receive_data)
                r = requests.post('{}'.format(NODE_IP), data=receive_json)
                logging.info("{}: block {} received".format(datetime.now(), block))
        else:
            logging.info('{}: No blocks to receive.'.format(datetime.now()))

    except Exception as e:
        logging.info("Error: {}".format(e))
        raise e

    return


def sendDM(receiver, message):
    """
    Send the provided message to the provided receiver
    """
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


def helpProcess(sender_id):
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
    sendDM(sender_id, help_message)
    logging.info("{}: Help message sent!".format(str(datetime.now())))


def balanceProcess(sender_id):
    """
    When the user sends a DM containing !balance, reply with the balance of the account linked with their Twitter ID
    """
    logging.info("{}: In balance process".format(datetime.now()))
    balance_call = ("SELECT account FROM users where user_id = {}".format(sender_id))
    data = getDBData(balance_call)
    if not data:
        logging.info("{}: User tried to check balance without an account".format(str(datetime.now())))
        balance_message = ("There is no account linked to your username.  Please respond with !register to "
                           "create an account.")
        sendDM(sender_id, balance_message)
    else:
        sender_account = data[0][0]
        receivePending(sender_account)
        account_registration_update = ("UPDATE users SET register = 1 WHERE user_id = {} AND "
                                       "register = 0".format(sender_id))
        setDBData(account_registration_update)
        balance_return = rpc.account_balance(account="{}".format(sender_account))
        balance = balance_return['balance'] / 1000000000000000000000000000000
        if balance == 0:
            balance_text = "Your balance is 0 NANO."
        else:
            balance_text = "Your balance is {} NANO.".format(balance)
        sendDM(sender_id, balance_text)
        logging.info("{}: Balance Message Sent!".format(str(datetime.now())))




def registerProcess(sender_id):
    """
    When the user sends !register, create an account for them and mark it registered.  If they already have an account
    reply with their account number.
    """
    logging.info("{}: In register process.".format(datetime.now()))
    register_call = ("SELECT account, register FROM users where user_id = {}".format(sender_id))
    data = getDBData(register_call)
    if not data:
        # Create an account for the user
        sender_account = rpc.account_create(wallet="{}".format(WALLET), work=True)
        account_create_call = ("INSERT INTO users (user_id, account, register) "
                               "VALUES({}, '{}',1)".format(sender_id, sender_account))
        setDBData(account_create_call)
        account_create_text = "You have successfully registered for an account.  Your account number is:"
        sendDM(sender_id, account_create_text)
        sendDM(sender_id, sender_account)
        logging.info("{}: Register successful!".format(str(datetime.now())))
    elif data[0][1] == 0:
        # The user has an account, but needed to register, so send a message to the user with their account
        sender_account = data[0][0]
        account_registration_update = ("UPDATE users SET register = 1 WHERE user_id = {} AND "
                                       "register = 0".format(sender_id))
        setDBData(account_registration_update)
        account_registration_text = "You have successfully registered for an account.  Your account number is:"
        sendDM(sender_id, account_registration_text)
        sendDM(sender_id, sender_account)
        logging.info("{}: User has an account, but needed to register.  Message sent".format(str(datetime.now())))
    else:
        # The user had an account and already registered, so let them know their account.
        sender_account = data[0][0]
        account_already_registered = ("You already have registered your account.  Your account number "
                                      "is:")
        sendDM(sender_id, account_already_registered)
        sendDM(sender_id, sender_account)
        logging.info("{}: User has a registered account.  Message sent.".format(str(datetime.now())))




def accountProcess(sender_id):
    """
    If the user sends !account command, reply with their account.  If there is no account, create one, register it
    and reply to the user.
    """
    logging.info("{}: In account process.".format(datetime.now()))
    sender_account_call = ("SELECT account FROM users where user_id = {}".format(sender_id))
    account_data = getDBData(sender_account_call)
    if not account_data:
        # Create an account for the user
        sender_account = rpc.account_create(wallet="{}".format(WALLET), work=True)
        account_create_call = ("INSERT INTO users (user_id, account, register) "
                               "VALUES({}, '{}',1)".format(sender_id, sender_account))
        setDBData(account_create_call)
        account_create_text = "You didn't have an account set up, so I set one up for you.  Your account number is:"
        sendDM(sender_id, account_create_text)
        sendDM(sender_id, sender_account)
        logging.info("{}: Created an account for the user!".format(str(datetime.now())))
    else:
        sender_account = account_data[0][0]
        set_register_call = ("UPDATE users SET register = 1 WHERE user_id = {} AND register = 0".format(sender_id))
        setDBData(set_register_call)
        account_text = "Your account number is:"
        sendDM(sender_id, account_text)
        sendDM(sender_id, sender_account)
        logging.info("{}: Sent the user their account number.".format(str(datetime.now())))




def withdrawProcess(sender_id, dm_array):
    """
    When the user sends !withdraw, send their entire balance to the provided account.  If there is no provided account
    reply with an error.
    """
    logging.info('{}: in withdrawProcess.'.format(datetime.now()))
    # check if there is a 2nd argument
    if 3 >= len(dm_array) >= 2:
        # if there is, retrieve the sender's account and wallet
        withdraw_account_call = ("SELECT account FROM users where user_id = {}".format(sender_id))
        withdraw_data = getDBData(withdraw_account_call)
        if not withdraw_data:
            withdraw_no_account_text = "You do not have an account.  Respond with !register to set one up."
            sendDM(sender_id, withdraw_no_account_text)
            logging.info("{}: User tried to withdraw with no account".format(str(datetime.now())))
        else:
            sender_account = withdraw_data[0][0]
            # check if there are pending blocks for the user's account
            receivePending(sender_account)
            # find the total balance of the account
            balance_return = rpc.account_balance(account='{}'.format(sender_account))
            if len(dm_array) == 2:
                receiver_account = dm_array[1].lower()
            else:
                receiver_account = dm_array[2].lower()
            # if the balance is 0, send a message that they have nothing to withdraw
            if rpc.validate_account_number(receiver_account) == 0:
                invalid_account_text = ("The account number you provided is invalid.  Please double check and "
                                        "resend your request.")
                sendDM(sender_id, invalid_account_text)
                logging.info("{}: The xrb account number is invalid: {}".format(str(datetime.now()), receiver_account))
            elif balance_return['balance'] == 0:
                no_balance_text = ("You have 0 balance in your account.  Please deposit to your address {} to "
                                   "send more tips!".format(sender_account))
                sendDM(sender_id, no_balance_text)
                logging.info("{}: The user tried to withdraw with 0 balance".format(str(datetime.now())))
            else:
                # check to see if an amount to send was provided
                if len(dm_array) == 3:
                    try:
                        logging.info(dm_array[1])
                        withdraw_amount = Decimal(dm_array[1])
                        logging.info(withdraw_amount)
                    except Exception as e:
                        logging.info(e)
                        invalid_amount_text = ("You did not send a number to withdraw.  Please resend with the format"
                                               "!withdraw <account> or !withdraw <amount> <account>")
                        sendDM(sender_id, invalid_amount_text)
                        return
                    withdraw_amount_raw = '{:f}'.format((withdraw_amount * 1000000000000000000000000000000))
                    if Decimal(withdraw_amount_raw) > Decimal(balance_return['balance']):
                        not_enough_balance_text = ("You do not have that much NANO in your account.  To withdraw your "
                                                   "full amount, send !withdraw <account>")
                        sendDM(sender_id, not_enough_balance_text)
                        return
                else:
                    withdraw_amount_raw = balance_return['balance']
                    withdraw_amount = balance_return['balance'] / 1000000000000000000000000000000
                # send the total balance to the provided account
                # work = getPOW(sender_account)
                logging.info(withdraw_amount_raw)
                send_hash = rpc.send(wallet="{}".format(WALLET), source="{}".format(sender_account),
                                     destination="{}".format(receiver_account), amount=withdraw_amount_raw)
                logging.info("{}: send_hash = {}".format(datetime.now(), send_hash))
                # respond that the withdraw has been processed
                withdraw_text = ("You have successfully withdrawn {} NANO!  You can check the "
                                 "transaction at https://www.nanode.co/block/{}".format(withdraw_amount, send_hash))
                sendDM(sender_id, withdraw_text)
                logging.info("{}: Withdraw processed.  Hash: {}".format(str(datetime.now()), send_hash))
    else:
        incorrect_withdraw_text = "I didn't understand your withdraw request.  Please resend with !withdraw <optional:amount> <account>.  Example, !withdraw 1 xrb_aigakjkfa343tm3h1kj would withdraw 1 NANO to account xrb_aigakjkfa343tm3h1kj.  Also, !withdraw xrb_aigakjkfa343tm3h1kj would withdraw your entire balance to account xrb_aigakjkfa343tm3h1kj."
        sendDM(sender_id, incorrect_withdraw_text)
        logging.info("{}: User sent a withdraw with invalid syntax.".format(str(datetime.now())))



def donateProcess(sender_id, dm_array):
    """
    When the user sends !donate, send the provided amount from the user's account to the tip bot's donation wallet.
    If the user has no balance or account, reply with an error.
    """
    logging.info("{}: in donateProcess.".format(datetime.now()))
    # check if there are 2 arguments
    if len(dm_array) >= 2:
        # if there are, retrieve the sender's account
        sender_account_call = ("SELECT account FROM users where user_id = {}".format(sender_id))
        donate_data = getDBData(sender_account_call)
        sender_account = donate_data[0][0]
        send_amount = dm_array[1]
        # check pending blocks for the user's account
        receivePending(sender_account)
        # find the total balance of the account
        balance_return = rpc.account_balance(account='{}'.format(sender_account))
        receiver_account = BOT_ACCOUNT
        # Convert the balance to Nano units
        balance = balance_return['balance'] / 1000000000000000000000000000000
        # Check to see if the tip amount is formatted correctly.
        wrong_donate = 0
        try:
            logging.info("{}: The user is donating {} NANO".format(str(datetime.now()), Decimal(send_amount)))
        except Exception as e:
            wrong_donate = 1

        if wrong_donate == 1:
            wrong_donate_text = "Only number amounts are accepted.  Please resend as !donate 1234"
            sendDM(sender_id, wrong_donate_text)
            logging.info("{}: User sent a donation that was not a number.".format(str(datetime.now())))
        elif Decimal(balance) < Decimal(send_amount):
            large_donate_text = ("Your balance is only {} NANO and you tried to send {}.  Please add more NANO"
                                 " to your account, or lower your donation amount.".format(balance, Decimal(send_amount)))
            sendDM(sender_id, large_donate_text)
            logging.info("{}: User tried to donate more than their balance.".format(datetime.now()))
        elif Decimal(send_amount) < Decimal(MIN_TIP):
            small_donate_text = ("The minimum donation amount is {}.  Please update your donation amount "
                                 "and resend.".format(MIN_TIP))
            sendDM(sender_id, small_donate_text)
            logging.info("{}: User tried to donate less than 0.000001".format(datetime.now()))
        else:
            # convert the send amount to raw
            send_amount_raw = convert(send_amount, from_unit='XRB', to_unit='raw')
            # Send the tip
            # work = getPOW(sender_account) - Activate to use dPoW system & add work=work to rpc.send
            send_hash = rpc.send(wallet="{}".format(WALLET), source="{}".format(sender_account),
                                 destination="{}".format(receiver_account), amount="{:f}".format(send_amount_raw))
            logging.info("{}: send_hash = {}".format(datetime.now(), send_hash))
            # Inform the user that the tip was sent with the hash
            donate_text = ("Thank you for your generosity!  You have successfully donated {} NANO!  You can check the "
                           "transaction at https://www.nanode.co/block/{}".format(send_amount, send_hash))
            sendDM(sender_id, donate_text)
            logging.info("{}: {} NANO donation processed.  Hash: {}".format(str(datetime.now()), Decimal(send_amount), send_hash))

    else:
        incorrect_donate_text = "Incorrect syntax.  Please use the format !donate 1234"
        sendDM(sender_id, incorrect_donate_text)
        logging.info("{}: User sent a donation with invalid syntax".format(str(datetime.now())))




def setTweetInfo(status, message):
    """
    Set the tweet information into the message dictionary
    """
    logging.info("{}: in setTweetInfo".format(datetime.now()))
    if status.get('retweeted_status'):
        logging.info("{}: Retweets are ignored.".format(datetime.now(TIMEZONE)))
        message['id'] = None
    else:
        message['id'] = status.get('id')
        message['sender_id_str'] = status.get('user',{}).get('id_str')
        message['sender_id'] = Decimal(message['sender_id_str'])

        if Decimal(message['sender_id']) == Decimal(BOT_ID):
            logging.info('Messages from the bot are ignored.')
            message['id'] = None
            return

        message['sender_screen_name'] = status.get('user',{}).get('screen_name')

        if status.get('truncated') is False:
            dm_text = status.get('text')
        else:
            dm_text = status.get('extended_tweet',{}).get('full_text')

        dm_text = dm_text.replace('\n', ' ')
        message['text'] = dm_text.split(" ")


def checkTweetAction(message):
    """
    Check to see if there are any key action values mentioned in the tweet.
    """
    logging.info("{}: in checkTweetAction.".format(datetime.now()))
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
        logging.info("{}: Tip amount was not a number: {}".format(datetime.now(TIMEZONE),
                                                                  message['text'][message['starting_point']]))
        try:
            api.update_status("@{} Looks like the value you entered to tip was not a number.  You can try"
                              " to tip again using the format !tip 1234 @username".format(
                message['sender_screen_name']),
                              message['id'])
        except tweepy.TweepError as e:
            logging.info("{}: Tweepy Error: {}".format(datetime.now(TIMEZONE), e))

        message['tip_amount'] = -1
        return

    if Decimal(message['tip_amount']) < Decimal(MIN_TIP):
        try:
            api.update_status("@{} The minimum tip amount is {} NANO.  Please update your tip amount"
                              " and try again.".format(message['sender_screen_name'], MIN_TIP), message['id'])
        except tweepy.TweepError as e:
            logging.info("{}: Tweepy Error: {}".format(datetime.now(TIMEZONE), e))

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
    db_call = "SELECT account, register FROM users where user_id = {}".format(message['sender_id'])
    sender_account_info = getDBData(db_call)

    if not sender_account_info:
        try:
            api.update_status("@{} You do not have an account with the bot.  Please send a DM to me with "
                              "!register to set up an account.".format(message['sender_screen_name']), message['id'])
        except tweepy.TweepError as e:
            logging.info("{}: Tweepy Error: {}".format(datetime.now(TIMEZONE), e))

        logging.info("{}: User tried to send a tip without an account.".format(datetime.now(TIMEZONE)))
        message['sender_account'] = None
        return

    message['sender_account'] = sender_account_info[0][0]
    message['sender_register'] = sender_account_info[0][1]

    if message['sender_register'] != 1:
        db_call = "UPDATE users SET register = 1 WHERE user_id = {}".format(message['sender_id'])
        setDBData(db_call)

    receivePending(message['sender_account'])
    message['sender_balance_raw'] = rpc.account_balance(account='{}'.format(message['sender_account']))
    message['sender_balance'] = Decimal(message['sender_balance_raw']['balance'] / 1000000000000000000000000000000)




def validateTotalTipAmount(message):
    """
    Validate that the sender has enough Nano to cover the tip to all users
    """
    logging.info("{}: validating total tip amount".format(datetime.now()))
    if Decimal(message['sender_balance']) < Decimal(message['total_tip_amount']):
        try:
            api.update_status("@{} You do not have enough NANO to cover this {} NANO tip.  Please check your "
                              "balance by sending a DM to me with !balance"
                              " and retry.".format(message['sender_screen_name'], message['total_tip_amount']),
                              message['id'])
        except tweepy.TweepError as e:
            logging.info("{}: Tweepy Error: {}".format(datetime.now(TIMEZONE), e))

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
        db_cursor.execute("INSERT INTO tip_list (dm_id, tx_id, processed, sender_id, receiver_id, dm_text, amount)"
                          " VALUES (%s, %s, 2, %s, %s, %s, %s)",
                          (message['id'], message['tip_id'], message['sender_id'],
                           users_to_tip[index]['receiver_id'], message['text'],
                           Decimal(message['tip_amount'])))
        db.commit()
        db_cursor.close()
        db.close()
    except Exception as e:
        logging.info("{}: Exception in setDBDataTip".format(datetime.now(TIMEZONE)))
        logging.info("{}: {}".format(datetime.now(TIMEZONE), e))
        raise e


def sendTip(message, users_to_tip, tip_index):
    """
    Process tip for specified user
    """
    logging.info("{}: sending tip to {}".format(datetime.now(TIMEZONE), users_to_tip[tip_index]['receiver_screen_name']))
    if str(users_to_tip[tip_index]['receiver_id']) == str(message['sender_id']):
        try:
            api.update_status("@{} Self tipping is not allowed.  Please use this bot to spread the "
                              "$NANO to other Twitter users!".format(message['sender_screen_name']), message['id'])
        except tweepy.TweepError as e:
            logging.info("{}: Tweepy Error: {}".format(datetime.now(TIMEZONE), e))

        logging.info("{}: User tried to tip themself").format(datetime.now(TIMEZONE))
        return

    # Check if the receiver has an account
    receiver_account_get = ("SELECT account FROM users where user_id = {}".format(int(users_to_tip[tip_index]['receiver_id'])))
    receiver_account_data = getDBData(receiver_account_get)
    # If they don't, create an account for them
    if not receiver_account_data:
        users_to_tip[tip_index]['receiver_account'] = rpc.account_create(wallet="{}".format(WALLET), work=True)
        create_receiver_account = ("INSERT INTO users (user_id, account, register) VALUES({}, "
                                   "'{}',0)".format(users_to_tip[tip_index]['receiver_id'],
                                                    users_to_tip[tip_index]['receiver_account']))
        setDBData(create_receiver_account)
        logging.info("{}: Sender sent to a new receiving account.  Created  account {}".format(
            datetime.now(TIMEZONE), users_to_tip[tip_index]['receiver_account']))
    else:
        users_to_tip[tip_index]['receiver_account'] = receiver_account_data[0][0]

    # Send the tip
    message['tip_id'] = "{}{}".format(message['id'], tip_index)

    # work = getPOW(message['sender_account']) - Activate to use dPoW system.  Also add work=work to rpc.send
    message['send_hash'] = rpc.send(wallet="{}".format(WALLET), source="{}".format(message['sender_account']),
                                    destination="{}".format(users_to_tip[tip_index]['receiver_account']),
                                    amount="{:f}".format(message['tip_amount_raw']),
                                    id="tip-{}".format(message['tip_id']))
    # Update the DB
    message['text'] = stripEmoji(message['text'])
    setDBDataTip(message, users_to_tip, tip_index)

    # Get receiver's new balance
    receivePending(users_to_tip[tip_index]['receiver_account'])
    balance_return = rpc.account_balance(account="{}".format(users_to_tip[tip_index]['receiver_account']))
    users_to_tip[tip_index]['balance'] = Decimal(balance_return['balance'] / 1000000000000000000000000000000)

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
    sendDM(users_to_tip[tip_index]['receiver_id'], receiver_tip_text)
    logging.info(
        "{}: tip sent to {} via hash {}".format(datetime.now(TIMEZONE), users_to_tip[tip_index]['receiver_screen_name'],
                                                message['send_hash']))




def tipProcess(message, users_to_tip):
    """
    Main orchestration process to handle tips
    """
    logging.info("{}: in tipProcess".format(datetime.now()))
    setTipList(message, users_to_tip)
    if len(users_to_tip) < 1:
        try:
            api.update_status(
                "@{}  Looks like you didn't enter in anyone to tip, or you mistyped someone's handle.  You can try to tip"
                " again using the format !tip 1234 @username".format(message['sender_screen_name']), message['id'])
        except tweepy.TweepError as e:
            logging.info("{}: Tweepy Error: {}".format(datetime.now(TIMEZONE), e))
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
        try:
            api.update_status("@{} You have successfully sent your {} $NANO tips.  Check your account at "
                              "nanode.co/account/{}".format(message['sender_screen_name'], message['tip_amount_text'],
                                                            message['sender_account']), message['id'])
        except tweepy.TweepError as e:
            logging.info("{}: Tweepy Error: {}".format(datetime.now(TIMEZONE), e))

    elif len(users_to_tip) == 1:
        try:
            api.update_status("@{} You have successfully sent your {} $NANO tip.  Check your account at "
                              "nanode.co/account/{}".format(message['sender_screen_name'], message['tip_amount_text'],
                                                            message['sender_account']), message['id'])
        except tweepy.TweepError as e:
            logging.info("{}: Tweepy Error: {}".format(datetime.now(TIMEZONE), e))


def getPOW(sender_account):
    """
    Retrieves the frontier (hash of previous transaction) of the provided account and generates work for the next block.
    """
    logging.info("{}: in getPOW".format(datetime.now()))
    account_info = rpc.account_info(account="{}".format(sender_account))
    hash = account_info['frontier']
    work = ''
    while work == '':
        try:
            json_request = '{"hash" : "%s" }' % hash
            r = requests.post('{}'.format(WORK_SERVER), data=json_request)
            rx = r.json()
            work = rx['work']
            logging.info("{}: Work generated: {}".format(datetime.now(), work))
        except Exception as e:
            logging.info("{}: Error generating work: {}".format(datetime.now(), e))
            pass

        return work


# Flask routing
@app.route('/tutorial.html')
def tutorial():
    return render_template('tutorial.html')


@app.route('/about.html')
def about():
    return render_template('about.html')


@app.route('/contact.html')
def contact():
    return render_template('contact.html')


@app.route('/contact-form-handler.php')
def contacthandler():
    return render_template('contact-form-handler.php')


@app.route('/contact-form-thank-you.html')
def thanks():
    return render_template('contact-form-thank-you.html')


@app.route('/')
@app.route('/index.html')
def index():
    return render_template('index.html')


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


@app.route("/webhooks/twitter", methods=["POST"])
def twitterEventReceived():
    request_json = request.get_json()

    # dump to console for debugging purposes

    if 'direct_message_events' in request_json.keys():
        """
        User sent a DM to the bot.  Parse the DM, see if there is an action provided and perform it.
        If no action is provided, reply with an error.
        Each action spawns a child process that will handle the requested action and terminate after completion.
        """
        request_json = request.get_json()

        # DM received, process that
        dm_object = request_json['direct_message_events'][0]
        message_object = request_json['direct_message_events'][0].get('message_create', {})

        sender_id = message_object.get('sender_id')

        if sender_id == BOT_ID:
            logging.info("Message from bot ignored.")
            return '', HTTPStatus.OK

        dm_id = dm_object.get('id')
        text = message_object.get('message_data', {}).get('text')
        dm_array = text.split(" ")
        dm_action = dm_array[0].lower()

        logging.info("Processing direct message.")

        # Update DB with new DM
        dm_insert_call = ("INSERT INTO dm_list (dm_id, processed, sender_id, dm_text) "
                          "VALUES ({}, 0, {}, '{}')".format(dm_id, sender_id, text))
        setDBData(dm_insert_call)

        logging.info("{}: action identified: {}".format(datetime.now(), dm_action))
        # Check for action on DM
        if dm_action == '!help':
            new_pid = os.fork()
            if new_pid == 0:
                try:
                    helpProcess(sender_id)
                except Exception as e:
                    logging.info("Exception: {}".format(e))
                    raise e
                os._exit(0)
            else:
                return '', HTTPStatus.OK


        elif dm_action == '!balance':
            new_pid = os.fork()
            if new_pid == 0:
                try:
                    balanceProcess(sender_id)
                except Exception as e:
                    logging.info("Exception: {}".format(e))
                    raise e
                os._exit(0)
            else:
                return '', HTTPStatus.OK

        elif dm_action == '!register':
            new_pid = os.fork()
            if new_pid == 0:
                try:
                    registerProcess(sender_id)
                except Exception as e:
                    logging.info("Exception: {}".format(e))
                    raise e
                os._exit(0)
            else:
                return '', HTTPStatus.OK

        elif dm_action == '!tip':
            new_pid = os.fork()
            if new_pid == 0:
                try:
                    redirect_tip_text = "Tips are processed through tweets now.  Please send in the format @NanoTipBot !tip .0001 @user1."
                    sendDM(sender_id, redirect_tip_text)
                except Exception as e:
                    logging.info("Exception: {}".format(e))
                    raise e
                os._exit(0)
            else:
                return '', HTTPStatus.OK

        elif dm_action == '!withdraw':
            new_pid = os.fork()
            if new_pid == 0:
                try:
                    withdrawProcess(sender_id, dm_array)
                except Exception as e:
                    logging.info("Exception: {}".format(e))
                    raise e
                os._exit(0)
            else:
                return '', HTTPStatus.OK


        elif dm_action == '!donate':
            new_pid = os.fork()
            if new_pid == 0:
                try:
                    donateProcess(sender_id, dm_array)
                except Exception as e:
                    logging.info("Exception: {}".format(e))
                    raise e
                os._exit(0)
            else:
                return '', HTTPStatus.OK

        elif dm_action == '!account':
            new_pid = os.fork()
            if new_pid == 0:
                try:
                    accountProcess(sender_id)
                except Exception as e:
                    logging.info("Exception: {}".format(e))
                    raise e
                os._exit(0)
            else:
                return '', HTTPStatus.OK

        elif dm_action == '!privatetip':
            new_pid = os.fork()
            if new_pid == 0:
                try:
                    redirect_tip_text = "Private Tip is under maintenance.  To send your tip, use the !tip function in a tweet or reply!"
                    sendDM(sender_id, redirect_tip_text)
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
                    wrong_format_text = ("The command or syntax you sent is not recognized.  Please send !help for a list of "
                                         "commands and what they do.")
                    sendDM(sender_id, wrong_format_text)
                    logging.info('unrecognized syntax')
                except Exception as e:
                    logging.info("Exception: {}".format(e))
                    raise e
                os._exit(0)
            else:
                return '', HTTPStatus.OK

        return '', HTTPStatus.OK

    elif 'tweet_create_events' in request_json.keys():
        """
        A tweet was received.  The bot will parse the tweet, see if there are any tips and process them.
        Error handling will cover if the sender doesn't have an account, doesn't have enough to cover the tips,
        sent to an invalid username, didn't send an amount to tip or didn't send a !tip command.
        """

        tweet_object = request_json['tweet_create_events'][0]

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
        }

        users_to_tip = [
            # List including dictionaries for each user to send a tip.  Each index will include
            # the below parameters
            #    receiver_id:            Twitter ID of the user receiving a tip
            #    receiver_screen_name:   Twitter Handle of the user receiving a tip
            #    receiver_account:       Nano account of receiver
            #    receiver_register:      Registration status with Tip Bot of reciever account
        ]

        setTweetInfo(tweet_object, message)
        if message['id'] is None:
            return '', HTTPStatus.OK

        checkTweetAction(message)
        if message['action'] is None:
            logging.info("{}: Mention of nano tip bot without a !tip command.".format(datetime.now(TIMEZONE)))
            return '', HTTPStatus.OK

        validateTipAmount(message)
        if message['tip_amount'] <= 0:
            return '', HTTPStatus.OK

        logging.info("{}: User Screen Name: {}".format(datetime.now(TIMEZONE), message['sender_screen_name']))
        logging.info(u'{}: Text of dm: {}'.format(datetime.now(TIMEZONE), message['text']))

        if message['action'] != -1 and str(message['sender_id']) != str(BOT_ID):
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

        elif str(message['sender_id']) == str(BOT_ID):
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
        sender_id = follow_source.get('id')

        helpProcess(sender_id)

        return '', HTTPStatus.OK

    else:
        # Event type not supported
        return '', HTTPStatus.OK

if __name__ == "__main__":
    app.run()
