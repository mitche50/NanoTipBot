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
                WHERE register = 0 AND DATE(created_ts) < DATE_SUB(NOW(), INTERVAL 10 DAY)")
unregistered_users = cursor.fetchall()

for row in unregistered_users:
    api.send_direct_message(user=row[0], text="Just a reminder that someone sent you a tip and you haven't"
                            " registered your account yet!  Reply to this message with !register to do so, then"
                            " !help to see all my commands!")

# Find users who have not registered in 29 days and give them a final reminder
unregistered_users = []
cursor = db.cursor()
cursor.execute("SELECT user_id FROM users\
               WHERE register = 0 AND DATE(created_ts) < DATE_SUB(NOW(), INTERVAL 30 DAY)")
unregistered_users = cursor.fetchall()

for row in unregistered_users:
    api.send_direct_message(user=row[0], text="This is your final notice!  If you do not register your account"
                                                   " by tomorrow, your tip will be sent back to the user that tipped"
                                                   " you.")

# TODO:Send back the tip