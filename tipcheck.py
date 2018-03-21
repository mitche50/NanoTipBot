# DEPENDENCIES =========================================
from datetime import datetime

import MySQLdb
import nano
import tweepy
from ConfigParser import SafeConfigParser
from nano import convert

# CONFIG CONSTANTS =====================================
config = SafeConfigParser()
config.read('/root/nanotipbot/config.ini')

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
BOT_ACCOUNT = config.get('main', 'bot_account')

# Connect to Twitter
auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
api = tweepy.API(auth)
rpc = nano.rpc.Client('http://[::1]:7076')

# Connect to DB
db = MySQLdb.connect(DB_HOST, DB_USER, DB_PW, DB_SCHEMA)

# Find users who have not registered in 10 days and remind them to register
unregistered_users = []
cursor = db.cursor()
cursor.execute("SELECT user_id FROM users\
                WHERE register = 0 AND DATE(created_ts) BETWEEN DATE_SUB(NOW(), INTERVAL 10 DAY)\
                                                                AND DATE_SUB(NOW(), INTERVAL 9 DAY)")
unregistered_users = cursor.fetchall()

for row in unregistered_users:
    api.send_direct_message(user=row[0], text="Just a reminder that someone sent you a tip and you haven't"
                            " registered your account yet!  Reply to this message with !register to do so, then"
                            " !help to see all my commands!")
    print("{}: User {} reminded after 10 days.".format(str(datetime.now()), row[0]))

# Find users who have not registered in 29 days and give them a final reminder
unregistered_users = []
cursor = db.cursor()
cursor.execute("SELECT user_id FROM users\
               WHERE register = 0 AND DATE(created_ts) BETWEEN DATE_SUB(NOW(), INTERVAL 29 DAY)\
                                                               AND DATE_SUB(NOW(), INTERVAL 28 DAY)")
unregistered_users = cursor.fetchall()

for row in unregistered_users:
    api.send_direct_message(user=row[0], text="This is your final notice!  If you do not register your account"
                                                   " by tomorrow, your tips will be sent back to the users that tipped"
                                                   " you.")
    print("{}: User {} given final notice after 29 days.".format(str(datetime.now()), row[0]))

# TODO:Send back the tip to users not registered in 30 days
unregistered_users = []
cursor = db.cursor()
cursor.execute("SELECT user_id, account FROM users\
               WHERE register = 0 AND DATE(created_ts) BETWEEN DATE_SUB(NOW(), INTERVAL 30 DAY) \
                                                        AND DATE_SUB(NOW(), INTERVAL 29 DAY)")
unregistered_users = cursor.fetchall()

for row in unregistered_users:
    api.send_direct_message(user=row[0], text="Your tips have been returned due to your account not being registered.")
    print("{}: User informed that they have had their tips returned.".format(str(datetime.now())))
    receiver_id = row[0]
    receiver_account = row[1]
    cursor = db.cursor()
    cursor.execute("SELECT sender_id, amount FROM dm_list\
                   WHERE receiver_id = {} AND dm_text LIKE '!tip%'".format(receiver_id))
    tips_to_return = cursor.fetchall()

    for tip in tips_to_return:
        sender_id = tip[0]
        amount = tip[1]
        cursor = db.cursor()
        cursor.execute("SELECT account FROM users\
                        WHERE user_id = {}".format(sender_id))
        sender_account_info = cursor.fetchone()
        sender_account = sender_account_info[0]
        send_hash = rpc.send(wallet="{}".format(WALLET), source="{}".format(receiver_account),
                             destination="{}".format(sender_account), amount=amount)
        print("{}: Tip returned under hash: {}".format(str(datetime.now()), send_hash))
        # Inform the sender that the receiver did not claim their tips and they have been returned
        receiver_id_info = api.get_user(receiver_id)
        api.send_direct_message(user=sender_id, text="Your tip to @{} was returned due to them not registering.  "
                                                     "If you know this person, make sure you tell them you're tipping"
                                                     " them before you resend!".format(receiver_id_info.screen_name))

    # After tips are returned, remove user from the account list
    cursor = db.cursor()
    cursor.execute("DELETE FROM users\
                       WHERE user_id = {}".format(receiver_id))
    print("{}: Unregistered user deleted after 30 days.".format(str(datetime.now())))
