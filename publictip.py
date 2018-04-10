#!/usr/bin/env python

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
config.read('/root/nanotipbot/config.ini')

# Set Log File
logging.basicConfig(handlers=[logging.FileHandler('/root/nanotipbot/publictip.log', 'a', 'utf-8')], level=logging.INFO)

CONSUMER_KEY = config.get('main', 'consumer_key')
CONSUMER_SECRET = config.get('main', 'consumer_secret')
ACCESS_TOKEN = config.get('main', 'access_token')
ACCESS_TOKEN_SECRET = config.get('main', 'access_token_secret')
DB_HOST = config.get('main', 'host')
DB_USER = config.get('main', 'user')
DB_PW = config.get('main', 'password')
DB_SCHEMA = config.get('main', 'schema')
WALLET = config.get('main', 'wallet')
BOT_ID = config.get('main', 'bot_id')
NODE_IP = config.get('main', 'node_ip')
BOT_ACCOUNT = config.get('main', 'bot_account')
RE_EMOJI = re.compile('[\U00010000-\U0010ffff\U000026A1]', flags=re.UNICODE)
TIMEZONE = timezone('US/Eastern')
BULLET = u"\u2022"

# Connect to DB
db = MySQLdb.connect(host=DB_HOST, port=3306, user=DB_USER, passwd=DB_PW, db=DB_SCHEMA, use_unicode=True, charset="utf8")

# Connect to Twitter
auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
api = tweepy.API(auth, wait_on_rate_limit=True)

# Connect to Node
rpc = nano.rpc.Client(NODE_IP)



# override tweepy.StreamListener to add logic to on_status
class MyStreamListener(tweepy.StreamListener):

    def on_status(self, status):

        global starting_point

        dm_id = status.id
        sender_id = status.user.id
        sender_screen_name = status.user.screen_name
        if status.truncated is False:
            dm_text = status.text
        else:
            dm_text = status.extended_tweet['full_text']

        # dm_text = self.stripEmoji(dm_text)
        dm_array = dm_text.split(" ")

        try:
            action_index = dm_array.index("!tip")
        except ValueError:
            dm_action = -1
        else:
            dm_action = dm_array[action_index].lower()
            starting_point = dm_array.index("!tip") + 1

        logging.info("{}: DM ID: {}".format(datetime.now(TIMEZONE), dm_id))
        logging.info("{}: User ID: {}".format(datetime.now(TIMEZONE), sender_id))
        logging.info("{}: User Screen Name: {}".format(datetime.now(TIMEZONE), sender_screen_name))
        logging.info(u'{}: Text of dm: {}'.format(datetime.now(TIMEZONE), dm_text))
        if hasattr(status, 'retweeted_status'):
            logging.info("{}: Retweets are ignored.".format(datetime.now(TIMEZONE)))
        else:
            if dm_action != -1 and str(sender_id) != str(BOT_ID):
                self.tipProcess(dm_action, dm_array, dm_id, sender_screen_name, dm_text)
            elif str(sender_id) == str(BOT_ID):
                logging.info("{}: TipBot sent a message.".format(datetime.now(TIMEZONE)))
            else:
                logging.info("{}: Mention of nano tip bot without a !tip command.".format(datetime.now(TIMEZONE)))

    def tipProcess(self, dm_action, dm_array, dm_id, sender_screen_name, dm_text):
        logging.info("{}: dm_action: {}".format(datetime.now(TIMEZONE), dm_action))
        users_to_tip = []
        tip_amount = 0
        self_tip = 0
        for index in range(starting_point, len(dm_array)):
            # Set the tip amount
            if index == starting_point:
                try:
                    float(dm_array[index])
                except ValueError:
                    try:
                        api.update_status("@{} Looks like the value you entered to tip was not a number.  You can try"
                                      " to tip again using the format !tip 1234 @username".format(sender_screen_name)
                                                                                            , dm_id)
                    except tweepy.TweepError as e:
                         logging.info("{}: Tweepy Error: {}".format(datetime.now(TIMEZONE), e))

                    tip_amount = -1
                else:
                    if float(dm_array[index]) < 0.0001:
                        try:
                            api.update_status("@{} The minimum tip amount is 0.0001 NANO.  Please update your tip amount"
                                           " and try again.".format(sender_screen_name), dm_id)
                        except tweepy.TweepError as e:
                            logging.info("{}: Tweepy Error: {}".format(datetime.now(TIMEZONE), e))

                        tip_amount = -1
                        logging.info("{}: User tipped less than 0.0001 NANO.".format(datetime.now(TIMEZONE)))
                    else:
                        tip_amount = float(dm_array[index])
            # Set the users to tip
            if index > starting_point:
                # Check if the text is a valid username to tip
                if len(dm_array[index]) > 0:
                    logging.info("dm_array[index][0]: {}".format(str(dm_array[index])[0]))
                    if str(dm_array[index])[0] == "@":
                        try:
                            api.get_user(dm_array[index])
                        except tweepy.TweepError as e:
                            logging.info("{}: The user sent a !tip command with text after it that was not a user: {}".format(
                                datetime.now(TIMEZONE), dm_array[index]))
                            logging.info("{}: Tweep error: {}".format(datetime.now(TIMEZONE), e))
                        else:
                            if dm_array[index].lower() != 'nanotipbot' and dm_array[index].lower() != '@nanotipbot':
                                users_to_tip.append(dm_array[index])
                            else:
                                logging.info("{}: User tried to tip the tip bot, did not add".format(datetime.now(TIMEZONE)))
                        # Check to see if the user tried to tip without any receivers
                        if len(users_to_tip) <= 0:
                            try:
                                api.update_status("@{} Looks like you didn't enter in any users to tip.  You can try to tip"
                                              " again using the format !tip 1234 @username".format(sender_screen_name), dm_id)
                            except tweepy.TweepError as e:
                                logging.info("{}: Tweepy Error: {}".format(datetime.now(TIMEZONE), e))

                            logging.info("{}: User sent !tip command with no users to tip.".format(datetime.now(TIMEZONE)))

        # Check to see if the sender has an account & if it's registered
        sender_info = api.get_user(sender_screen_name)
        sender_id = sender_info.id
        db_call = "SELECT account, register FROM users where user_id = {}".format(sender_id)
        sender_account_info = self.getDBData(db_call)
        if not sender_account_info:
            try:
                api.update_status("@{} You do not have an account with the bot.  Please send a DM to me with "
                              "!register to set up an account.".format(sender_screen_name), dm_id)
            except tweepy.TweepError as e:
                logging.info("{}: Tweepy Error: {}".format(datetime.now(TIMEZONE), e))

            logging.info("{}: User tried to send a tip without an account.".format(datetime.now(TIMEZONE)))
        else:
            sender_account = sender_account_info[0][0]
            register = sender_account_info[0][1]
            if register != 1:
                db_call = "UPDATE users SET register = 1 WHERE user_id = {}".format(sender_id)
                self.setDBData(db_call)
                logging.info("{}: Updated the register value for sender's account.".format(datetime.now(TIMEZONE)))

            # Check the sender's balance and see if they have enough to cover tipping everyone
            self.receivePending(sender_account)
            balance_return = rpc.account_balance(account='{}'.format(sender_account))
            balance = convert(balance_return['balance'], from_unit='raw', to_unit='XRB')
            total_tip_amount = tip_amount * len(users_to_tip)
            if float(balance) < float(total_tip_amount):
                try:
                    api.update_status("@{} You do not have enough NANO to cover this {} NANO tip.  Please check your "
                                  "balance by sending a DM to me with !balance"
                                  " and retry.".format(sender_screen_name, total_tip_amount), dm_id)
                except tweepy.TweepError as e:
                    logging.info("{}: Tweepy Error: {}".format(datetime.now(TIMEZONE), e))

                logging.info("{}: User tried to send more than in their account.".format(datetime.now(TIMEZONE)))
            elif tip_amount > 0:
                # convert the send amount to raw
                send_amount = convert(str(tip_amount), from_unit='XRB', to_unit='raw')
                # create a string to remove scientific notation from small decimal tips
                if str(tip_amount)[0] == ".":
                    tip_amount_text = "0{}".format(str(tip_amount))
                else:
                    tip_amount_text = str(tip_amount)

                # Loop through users to tip and send the tips
                for receiver_number in range(0, len(users_to_tip)):
                    logging.info("{}: sending tip to {}".format(datetime.now(TIMEZONE), users_to_tip[receiver_number]))
                    receiver_screen_name = users_to_tip[receiver_number]
                    # Get the receiver ID from Twitter
                    receiver_id_info = api.get_user(users_to_tip[receiver_number])
                    receiver_id = receiver_id_info.id
                    if str(receiver_id) != str(sender_id):
                        self_tip = 0
                        # Check if the receiver has an account
                        receiver_account_get = ("SELECT account FROM users where user_id = {}".format(receiver_id))
                        receiver_account_data = self.getDBData(receiver_account_get)
                        # If they don't, create an account for them
                        if not receiver_account_data:
                            receiver_account = rpc.account_create(wallet="{}".format(WALLET), work=True)
                            create_receiver_account = ("INSERT INTO users (user_id, account, register) VALUES({}, "
                                                       "'{}',0)".format(receiver_id, receiver_account))
                            self.setDBData(create_receiver_account)
                            logging.info("{}: Sender sent to a new receiving account.  Created  account {}".format(
                                datetime.now(TIMEZONE), receiver_account))
                        else:
                            receiver_account = receiver_account_data[0][0]
                        # Send the tip
                        tip_id = "{}{}".format(dm_id, receiver_number)
                        send_hash = rpc.send(wallet="{}".format(WALLET), source="{}".format(sender_account),
                                             destination="{}".format(receiver_account),
                                             amount="{:f}".format(send_amount), id="tip-{}".format(tip_id))
                        # Update the DB
                        dm_text = self.stripEmoji(dm_text)
                        self.setDBDataTip(dm_id, tip_id, sender_id, receiver_id, dm_text, tip_amount)
                        # Send a DM to the receiver
                        receiver_tip_text = ("@{} just sent you a {} NANO tip!  If you have not registered an account,"
                                             " send a reply with !register to get started, or !help to see a list of "
                                             "commands!  Learn more about NANO at https://nano.org/".format(
                                            sender_screen_name, tip_amount))
                        self.sendDM(receiver_id, receiver_tip_text)

                        # Removing tagging tipped users due to Twitter API restrictions
                        """
                        try:
                            api.update_status("Hey {}!  @{} just sent you a {} $NANO tip!  Check out this transaction at "
                                          "https://www.nanode.co/block/{}".format(receiver_screen_name, sender_screen_name,
                                                                                  tip_amount, send_hash))
                        except tweepy.TweepError as e:
                            logging.info("{}: Tweepy Error: {}".format(datetime.now(TIMEZONE), e))
                        """

                        logging.info("{}: tip sent to {} via hash {}".format(datetime.now(TIMEZONE), receiver_id_info.screen_name,
                                                                      send_hash))
                    else:
                        try:
                            api.update_status("@{} Self tipping is not allowed.  Please use this bot to spread the "
                                              "$NANO to other Twitter users!".format(sender_screen_name), dm_id)
                        except tweepy.TweepError as e:
                            logging.info("{}: Tweepy Error: {}".format(datetime.now(TIMEZONE), e))
                        else:
                            self_tip = 1

                # Inform the user that all tips were sent.
                if len(users_to_tip) >= 2 and self_tip == 0:
                    try:
                        api.update_status("@{} You have successfully sent your {} $NANO tips.  Check your account at "
                                      "nanode.co/account/{}".format(sender_screen_name, tip_amount_text, sender_account), dm_id)
                    except tweepy.TweepError as e:
                        logging.info("{}: Tweepy Error: {}".format(datetime.now(TIMEZONE), e))

                elif len(users_to_tip) == 1 and self_tip == 0:
                    try:
                        api.update_status("@{} You have successfully sent your {} $NANO tip.  Check your account at "
                                      "nanode.co/account/{}".format(sender_screen_name, tip_amount_text, sender_account), dm_id)
                    except tweepy.TweepError as e:
                        logging.info("{}: Tweepy Error: {}".format(datetime.now(TIMEZONE), e))


    def getDBData(self, db_call):
        db_cursor = db.cursor()
        db_cursor.execute(db_call)
        db_data = db_cursor.fetchall()
        db_cursor.close()
        return db_data

    def setDBData(self, db_call):
        try:
            db_cursor = db.cursor()
            db_cursor.execute(db_call)
            db.commit()
            db_cursor.close()
        except MySQLdb.ProgrammingError as e:
            logging.info("{}: {}".format(datetime.now(TIMEZONE), e))
            raise e

        return

    def stripEmoji(self, text):
        return RE_EMOJI.sub(r'', text)

    def receivePending(self, account):
        pending_blocks = rpc.pending(account='{}'.format(account))
        if len(pending_blocks) > 0:
            for block in pending_blocks:
                rpc.receive(wallet='{}'.format(WALLET), account='{}'.format(account), block='{}'.format(block))
        return

    def sendDM(self, receiver_id, dm_text):
        try:
            api.send_direct_message(user_id=receiver_id, text=dm_text)
        except tweepy.TweepError as e:
            logging.info("{}: {}".format(datetime.now(TIMEZONE), e))
        except:
            logging.info("{}: There was an unexpected error with sending a DM.".format(datetime.now(TIMEZONE)))
            raise

    def setDBDataTip(self, dm_id, tip_id, sender_id, receiver_id, dm_text, tip_amount):
        try:
            db_cursor = db.cursor()
            db_cursor.execute("INSERT INTO tip_list (dm_id, tx_id, processed, sender_id, receiver_id, dm_text, amount)"
                              " VALUES (%s, %s, 2, %s, %s, %s, %s)", (dm_id, tip_id, sender_id,
                                                                      receiver_id, dm_text, float(tip_amount)))
            db.commit()
            db_cursor.close()
        except MySQLdb.ProgrammingError as e:
            logging.info("{}: {}".format(datetime.now(TIMEZONE), e))
            raise e


def main():

    # Launch stream to track for mentions
    my_stream_listener = MyStreamListener()
    my_stream = tweepy.Stream(auth=api.auth, listener=my_stream_listener)
    my_stream.filter(track=['@NanoTipBot'], async=True)


main()
