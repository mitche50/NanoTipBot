#!/usr/bin/env python3

from datetime import datetime
from pytz import timezone
import MySQLdb
import re
import nano
import tweepy
import configparser
import logging
from nano import convert

# Read config and parse constants
config = configparser.ConfigParser()
config.read('/root/nanotipbottest/config.ini')

# Set Log File
logging.basicConfig(handlers=[logging.FileHandler('/root/nanotipbottest/publictip.log', 'a', 'utf-8')], level=logging.INFO)

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

# Twitter ID of bot
BOT_ID = config.get('main', 'bot_id')
# Twitter handle of bot
BOT_NAME = config.get('main', 'bot_name')
# Bot Nano account
BOT_ACCOUNT = config.get('main', 'bot_account')
# Minimum Tip Amount
MIN_TIP = config.get('main', 'min_tip')
# Emoji unicode to remove it before entering into DB (prevents issues with storage of messages)
RE_EMOJI = re.compile('[\U00010000-\U0010ffff\U000026A1]', flags=re.UNICODE)
# Default to US Eastern time zone
TIMEZONE = timezone('US/Eastern')
# Unicode bullet for formatting
BULLET = u"\u2022"

# Connect to Twitter
auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
api = tweepy.API(auth, wait_on_rate_limit=True)

# Connect to Node
rpc = nano.rpc.Client(NODE_IP)


def setTweetInfo(status, message):
    """
    Set the tweet information into the message dictionary
    """
    logging.info("{}: Entered setTweetInfo.".format(datetime.now(TIMEZONE)))
    if hasattr(status, 'retweeted_status'):
        logging.info("{}: Retweets are ignored.".format(datetime.now(TIMEZONE)))
        message['id'] = None
    else:
        message['id'] = status.id
        message['sender_id'] = status.user.id
        message['sender_screen_name'] = status.user.screen_name

        if status.truncated is False:
            dm_text = status.text
        else:
            dm_text = status.extended_tweet['full_text']

        message['text'] = dm_text.split(" ")
        logging.info("{}: Message: {}".format(datetime.now(TIMEZONE), message))


def checkTweetAction(message):
    """
    Check to see if there are any key action values mentioned in the tweet.
    """
    logging.info("{}: Entered checkTweetAction".format(datetime.now(TIMEZONE)))
    logging.info("{}: Message before: {}".format(datetime.now(TIMEZONE), message))
    try:
        message['action_index'] = message['text'].index("!tip")
    except ValueError:
        message['action'] = None
        return

    message['action'] = message['text'][message['action_index']].lower()
    message['starting_point'] = message['action_index'] + 1
    logging.info("{}: Message after: {}".format(datetime.now(TIMEZONE), message))


def validateTipAmount(message):
    """
    Validate the tweet includes an amount to tip, and if that tip amount is greater than the minimum tip amount.
    """
    logging.info("{}: Entered validateTipAmount".format(datetime.now(TIMEZONE)))
    try:
        message['tip_amount'] = float(message['text'][message['starting_point']])
    except ValueError:
        logging.info("{}: Tip amount was not a number: {}".format(datetime.now(TIMEZONE), message['text'][message['starting_point']]))
        try:
            api.update_status("@{} Looks like the value you entered to tip was not a number.  You can try"
                              " to tip again using the format !tip 1234 @username".format(message['sender_screen_name']),
                              message['id'])
        except tweepy.TweepError as e:
            logging.info("{}: Tweepy Error: {}".format(datetime.now(TIMEZONE), e))

        message['tip_amount'] = -1
        return

    logging.info("{}: message['tip_amount']: {}".format(datetime.now(TIMEZONE), message['tip_amount']))

    if float(message['tip_amount']) < float(MIN_TIP):
        try:
            api.update_status("@{} The minimum tip amount is {} NANO.  Please update your tip amount"
                              " and try again.".format(message['sender_screen_name'], MIN_TIP), message['id'])
        except tweepy.TweepError as e:
            logging.info("{}: Tweepy Error: {}".format(datetime.now(TIMEZONE), e))

        message['tip_amount'] = -1
        logging.info("{}: User tipped less than {} NANO.".format(datetime.now(TIMEZONE), MIN_TIP))
        return

    logging.info("{}: Converting tip amount to raw.".format(datetime.now(TIMEZONE)))
    try:
        message['tip_amount_raw'] = convert(str(message['tip_amount']), from_unit='XRB', to_unit='raw')
    except Exception as e:
        logging.info("{}: Exception converting tip_amount to tip_amount_raw".format(datetime.now(TIMEZONE)))
        logging.info("{}: {}".format(datetime.now(TIMEZONE), e))

    # create a string to remove scientific notation from small decimal tips
    if str(message['tip_amount'])[0] == ".":
        message['tip_amount_text'] = "0{}".format(str(message['tip_amount']))
    else:
        message['tip_amount_text'] = str(message['tip_amount'])

    logging.info("{}: tip_amount_text: {}".format(datetime.now(TIMEZONE), message['tip_amount_text']))


def validateTotalTipAmount(message):
    """
    Validate that the sender has enough Nano to cover the tip to all users
    """
    if float(message['sender_balance']) < float(message['total_tip_amount']):
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


def setTipList(message, users_to_tip):
    """
    Loop through the message starting after the tip amount and identify any users that were tagged for a tip.  Add the
    user object to the users_to_tip dict to process the tips.
    """
    logging.info("{}: Entered setTipList".format(datetime.now(TIMEZONE)))
    for index in range(message['starting_point'] + 1, len(message['text'])):
        if len(message['text'][index]) > 0:
            logging.info("message['text'][index][0]: {}".format(str(message['text'][index])[0]))
            if str(message['text'][index][0]) == "@" and str(message['text'][index]).lower() != ("@" + str(message['sender_screen_name']).lower()):
                try:
                    user_info = api.get_user(message['text'][index])
                except tweepy.TweepError as e:
                    logging.info(
                        "{}: The user sent a !tip command with a mistyped user: {}".format(
                            datetime.now(TIMEZONE), message['text'][index]))
                    logging.info("{}: Tweep error: {}".format(datetime.now(TIMEZONE), e))
                    return

                logging.info("{}: User {} added to tip list.".format(datetime.now(TIMEZONE), message['text'][index]))
                user_dict = {'receiver_id': user_info.id, 'receiver_screen_name': user_info.screen_name, 'receiver_account': None, 'receiver_register': None}
                users_to_tip.append(user_dict)
                logging.info("{}: Users_to_tip: {}".format(datetime.now(TIMEZONE), users_to_tip))

    logging.info("{}: len(users_to_tip): {}".format(datetime.now(TIMEZONE), len(users_to_tip)))
    logging.info("{}: message['tip_amount']")

    if len(users_to_tip) > 0 and message['tip_amount'] != -1:
        message['total_tip_amount'] = message['tip_amount'] * len(users_to_tip)

    else:
        return


def getDBData(db_call):
    """
    Retrieve data from DB
    """
    db = MySQLdb.connect(host=DB_HOST, port=3306, user=DB_USER, passwd=DB_PW, db=DB_SCHEMA, use_unicode=True,
                         charset="utf8")
    logging.info("{}: Entered getDBData".format(datetime.now(TIMEZONE)))
    db_cursor = db.cursor()
    logging.info("{}: cursor created".format(datetime.now(TIMEZONE)))
    db_cursor.execute(db_call)
    logging.info("{}: SQL executed".format(datetime.now(TIMEZONE)))
    db_data = db_cursor.fetchall()
    logging.info("{}: info retrieved".format(datetime.now(TIMEZONE)))
    db_cursor.close()
    logging.info("{}: cursor closed".format(datetime.now(TIMEZONE)))
    db.close()
    logging.info("{}: DB closed".format(datetime.now(TIMEZONE)))
    return db_data


def setDBData(db_call):
    """
    Enter data into DB
    """
    logging.info("{}: entered setDBData".format(datetime.now(TIMEZONE)))
    db = MySQLdb.connect(host=DB_HOST, port=3306, user=DB_USER, passwd=DB_PW, db=DB_SCHEMA, use_unicode=True,
                         charset="utf8")
    try:
        db_cursor = db.cursor()
        db_cursor.execute(db_call)
        db.commit()
        db_cursor.close()
        db.close()
    except MySQLdb.ProgrammingError as e:
        logging.info("{}: Exception entering data into database".format(datetime.now(TIMEZONE)))
        logging.info("{}: {}".format(datetime.now(TIMEZONE), e))
        raise e


def stripEmoji(text):
    """
    Remove Emojis from tweet text to prevent issues with logging
    """
    logging.info("{}: entered stripEmoji".format(datetime.now(TIMEZONE)))
    text = str(text)
    return RE_EMOJI.sub(r'', text)


def receivePending(account):
    """
    Receive the pending blocks for the provided account.
    """
    logging.info("{}: Entered receivePending".format(datetime.now(TIMEZONE)))
    pending_blocks = rpc.pending(account='{}'.format(account))
    if len(pending_blocks) > 0:
        for block in pending_blocks:
            rpc.receive(wallet='{}'.format(WALLET), account='{}'.format(account), block='{}'.format(block))
    return


def sendDM(receiver_id, dm_text):
    """
    Send a Direct Message to the provided receiver ID including the provided text.
    """
    logging.info("{}: entered sendDM".format(datetime.now(TIMEZONE)))
    try:
        api.send_direct_message(user_id=receiver_id, text=dm_text)
    except tweepy.TweepError as e:
        logging.info("{}: Exception sending DM".format(datetime.now(TIMEZONE)))
        logging.info("{}: {}".format(datetime.now(TIMEZONE), e))
    except:
        logging.info("{}: There was an unexpected error with sending a DM.".format(datetime.now(TIMEZONE)))
        raise


def setDBDataTip(message, users_to_tip, index):
    """
    Special case to update DB information to include tip data
    """
    db = MySQLdb.connect(host=DB_HOST, port=3306, user=DB_USER, passwd=DB_PW, db=DB_SCHEMA, use_unicode=True,
                         charset="utf8")
    logging.info("{}: Entered setDBDataTip".format(datetime.now(TIMEZONE)))
    try:
        db_cursor = db.cursor()
        db_cursor.execute("INSERT INTO tip_list (dm_id, tx_id, processed, sender_id, receiver_id, dm_text, amount)"
                          " VALUES (%s, %s, 2, %s, %s, %s, %s)", (message['id'], message['tip_id'], message['sender_id'],
                                                                  users_to_tip[index]['receiver_id'], message['text'],
                                                                  float(message['tip_amount'])))
        db.commit()
        db_cursor.close()
        db.close()
    except MySQLdb.ProgrammingError as e:
        logging.info("{}: Exception in setDBDataTip".format(datetime.now(TIMEZONE)))
        logging.info("{}: {}".format(datetime.now(TIMEZONE), e))
        raise e


def validateSender(message):
    """
    Validate that the sender has an account with the tip bot, and has enough NANO to cover the tip.
    """
    logging.info("{}: Entered validateSender".format(datetime.now(TIMEZONE)))
    db_call = "SELECT account, register FROM users where user_id = {}".format(message['sender_id'])
    logging.info("{}:Sending account information request.".format(datetime.now(TIMEZONE)))
    sender_account_info = getDBData(db_call)
    logging.info("{}: Account information retrieved.".format(datetime.now(TIMEZONE)))

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
        logging.info("{}: Updated the register value for sender's account.".format(datetime.now(TIMEZONE)))

    logging.info("{}: account {} register {} retrieved.".format(datetime.now(TIMEZONE), message['sender_account'], message['sender_register']))

    receivePending(message['sender_account'])
    message['sender_balance_raw'] = rpc.account_balance(account='{}'.format(message['sender_account']))
    message['sender_balance'] = convert(message['sender_balance_raw']['balance'], from_unit='raw', to_unit='XRB')


def sendTip(message, users_to_tip, index):
    """
    Process tip for specified user
    """
    logging.info("{}: Entered sendTip".format(datetime.now(TIMEZONE)))
    logging.info("{}: sending tip to {}".format(datetime.now(TIMEZONE), users_to_tip[index]['receiver_screen_name']))
    if str(users_to_tip[index]['receiver_id']) == str(message['sender_id']):
        try:
            api.update_status("@{} Self tipping is not allowed.  Please use this bot to spread the "
                              "$NANO to other Twitter users!".format(message['sender_screen_name']), message['id'])
        except tweepy.TweepError as e:
            logging.info("{}: Tweepy Error: {}".format(datetime.now(TIMEZONE), e))

        logging.info("{}: User tried to tip themself").format(datetime.now(TIMEZONE))
        return

    # Check if the receiver has an account
    receiver_account_get = ("SELECT account FROM users where user_id = {}".format(int(users_to_tip[index]['receiver_id'])))
    logging.info("{}: SQL to get receiver: {}".format(datetime.now(TIMEZONE), receiver_account_get))
    receiver_account_data = getDBData(receiver_account_get)
    # If they don't, create an account for them
    if not receiver_account_data:
        users_to_tip[index]['receiver_account'] = rpc.account_create(wallet="{}".format(WALLET), work=True)
        create_receiver_account = ("INSERT INTO users (user_id, account, register) VALUES({}, "
                                   "'{}',0)".format(users_to_tip[index]['receiver_id'], users_to_tip[index]['receiver_account']))
        setDBData(create_receiver_account)
        logging.info("{}: Sender sent to a new receiving account.  Created  account {}".format(
            datetime.now(TIMEZONE), users_to_tip[index]['receiver_account']))
    else:
        users_to_tip[index]['receiver_account'] = receiver_account_data[0][0]

    # Send the tip
    message['tip_id'] = "{}{}".format(message['id'], index)
    message['send_hash'] = rpc.send(wallet="{}".format(WALLET), source="{}".format(message['sender_account']),
                                    destination="{}".format(users_to_tip[index]['receiver_account']),
                                    amount="{:f}".format(message['tip_amount_raw']), id="tip-{}".format(message['tip_id']))
    # Update the DB
    message['text'] = stripEmoji(message['text'])
    setDBDataTip(message, users_to_tip, index)

    # Send a DM to the receiver
    receiver_tip_text = ("@{} just sent you a {} NANO tip!  If you have not registered an account,"
                         " send a reply with !register to get started, or !help to see a list of "
                         "commands!  Learn more about NANO at https://nano.org/".format(
                          message['sender_screen_name'], message['tip_amount_text']))
    sendDM(users_to_tip[index]['receiver_id'], receiver_tip_text)
    logging.info("{}: tip sent to {} via hash {}".format(datetime.now(TIMEZONE), users_to_tip[index]['receiver_screen_name'],
                                                         message['send_hash']))


def tipProcess(message, users_to_tip):
    """
    Main orchestration process to handle tips
    """
    logging.info("{}: Entered tipProcess, message['action']: {}".format(datetime.now(TIMEZONE), message['action']))

    setTipList(message, users_to_tip)
    if len(users_to_tip) < 1:
        try:
            api.update_status("@{}  Looks like you didn't enter in anyone to tip, or you mistyped someone's handle.  You can try to tip"
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


class MyStreamListener(tweepy.StreamListener):

    def on_status(self, status):
        """
        Overload of Tweepy on_status function to execute program when the bot's Twitter handle is mentioned
        """
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

        logging.info("{}: Message received.".format(datetime.now(TIMEZONE)))
        logging.info("hasattr retweet: {}".format(hasattr(status, 'retweeted_status')))

        setTweetInfo(status, message)
        if message['id'] is None:
            return

        checkTweetAction(message)
        if message['action'] is None:
            logging.info("{}: Mention of nano tip bot without a !tip command.".format(datetime.now(TIMEZONE)))
            return

        validateTipAmount(message)
        if message['tip_amount'] <= 0:
            return

        logging.info("{}: DM ID: {}".format(datetime.now(TIMEZONE), message['id']))
        logging.info("{}: User ID: {}".format(datetime.now(TIMEZONE), message['sender_id']))
        logging.info("{}: User Screen Name: {}".format(datetime.now(TIMEZONE), message['sender_screen_name']))
        logging.info(u'{}: Text of dm: {}'.format(datetime.now(TIMEZONE), message['text']))

        if message['action'] != -1 and str(message['sender_id']) != str(BOT_ID):
            try:
                tipProcess(message, users_to_tip)
            except Exception as e:
                logging.info("{}: Exception in tipProcess".format(datetime.now(TIMEZONE)))
                logging.info("{}: {}".format(datetime.now(TIMEZONE), e))
        elif str(message['sender_id']) == str(BOT_ID):
            logging.info("{}: TipBot sent a message.".format(datetime.now(TIMEZONE)))


def main():

    # Launch stream to track for mentions
    my_stream_listener = MyStreamListener()
    my_stream = tweepy.Stream(auth=api.auth, listener=my_stream_listener)
    my_stream.filter(track=[str(BOT_NAME)], async=True)


main()
