# DEPENDENCIES =========================================
from datetime import datetime
from pytz import timezone

import MySQLdb
import nano
import tweepy
import configparser
from nano import convert

# CONFIG CONSTANTS =====================================
config = configparser.ConfigParser()
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
TIMEZONE = timezone('US/Eastern')

# Connect to Twitter
auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
api = tweepy.API(auth)
rpc = nano.rpc.Client('http://[::1]:7076')


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
    except MySQLdb.ProgrammingError as e:
        print("{}: Exception entering data into database".format(datetime.now(TIMEZONE)))
        print("{}: {}".format(datetime.now(TIMEZONE), e))
        raise e


def userCheck(day_difference, dm_text):
    """
    Check for unregistered users day_difference away from the current day and send a DM with the provided dm_text
    """
    db_call = "SELECT user_id FROM users WHERE register = 0 AND DATE(create_ts) BETWEEN DATE_SUB(NOW(), INTERVAL {} DAY) AND DATE_SUB(NOW(), INTERVAL {} DAY)".format(day_difference, day_difference - 1)
    unregistered_users = getDBData(db_call)

    for user in unregistered_users:
        api.send_direct_message(user=user[0], text=dm_text)
        print("{}: User {} reminded after {} days.".format(str(datetime.now()), row[0], day_difference))


def removeUser(user_id, user_account):
    """
    If the user's tips were all successfully returned, remove the user from the database.  If not, throw an error to be investigated.
    """
    pending_blocks = rpc.pending(account='{}'.format(user_account))
    if len(pending_blocks) > 0:
        for block in pending_blocks:
            rpc.receive(wallet='{}'.format(WALLET), account='{}'.format(user_account), block='{}'.format(block))

    balance_raw = rpc.account_balance(account='{}'.format(user_account))
    balance = convert(balance_raw, from_unit='raw', to_unit='XRB')

    if balance == 0:
        remove_call = "DELETE FROM users WHERE user_id = {}".format(user_id)
        setDBData(remove_call)
        print("{}: Unregistered user {} deleted after 30 days.".format(str(datetime.now(TIMEZONE)), user_id))
        api.send_direct_message(user=user_id,
                                text="Your tips have been returned due to your account not being registered.")
        print("{}: User informed that they have had their tips returned.".format(str(datetime.now())))
    else:
        print("{}: ERROR: User {}, account {} still has a balance, but should have had all tips sent back.  Please check to see where the issue is.".format(datetime.now(TIMEZONE), user_id, user_account))


def main():
    # Check for users who need reminders
    userCheck(10, "Just a reminder that someone sent you a tip and you haven't registered your account yet!  Reply to this message with !register to do so, then !help to see all my commands!")
    userCheck(20, "You still have not registered your account.  If you do not register within 30 days, your tip will be returned.  Please respond with !register to complete your registration, or !help to see my commands!")
    userCheck(29, "This is your final notice!  If you do not register your account before tomorrow, your tips will be sent back to the users that tipped you!")

    # Send back the tip to users not registered in 30 days
    return_call = "SELECT user_id, account FROM users WHERE register = 0 AND DATE(created_ts) BETWEEN DATE_SUB(NOW(), INTERVAL 30 DAY) AND DATE_SUB(NOW(), INTERVAL 29 DAY)"
    unregistered_users = getDBData(return_call)

    for row in unregistered_users:
        receiver_id = row[0]
        receiver_account = row[1]

        tip_call = "SELECT sender_id, amount FROM dm_list WHERE receiver_id = {} AND dm_text LIKE '%!tip%'".format(receiver_id)
        tips_to_return = getDBData(tip_call)

        for tip in tips_to_return:
            sender_id = tip[0]
            amount = tip[1]
            sender_account_call = "SELECT account FROM users WHERE user_id = {}".format(sender_id)
            sender_account_info = getDBData(sender_account_call)
            sender_account = sender_account_info[0][0]
            send_amount = convert(str(amount), from_unit='XRB', to_unit='raw')
            send_hash = rpc.send(wallet="{}".format(WALLET), source="{}".format(receiver_account),
                                 destination="{}".format(sender_account), amount=send_amount)
            print("{}: Tip returned under hash: {}".format(str(datetime.now()), send_hash))
            # Inform the sender that the receiver did not claim their tips and they have been returned
            receiver_id_info = api.get_user(receiver_id)
            api.send_direct_message(user=sender_id, text="Your tip to @{} was returned due to them not registering.  "
                                                         "If you know this person, make sure you tell them you're tipping"
                                                         " them before you resend!".format(receiver_id_info.screen_name))

        # After tips are returned, remove user from the account list and inform their tips have been sent back.
        removeUser(receiver_id, receiver_account)


main()
