# DEPENDENCIES =========================================
from datetime import datetime

import MySQLdb
import nano
import tweepy
from ConfigParser import SafeConfigParser
from nano import convert

# TODO LIST ===========================================
# TODO: Make user register before gaining access to any other command.
# TODO: Make a tipcheck.py script that checks accounts that have register = 0 and reminds them to register
# TODO: Add to tipcheck.py to return a tip if the sent account does not register in 30 days
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
BULLET = u"\u2022"

# Connect to Twitter
auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
api = tweepy.API(auth)
rpc = nano.rpc.Client('http://[::1]:7076')

# Connect to DB
db = MySQLdb.connect(DB_HOST, DB_USER, DB_PW, DB_SCHEMA)

# pull old most recent DM
old_file = open("/root/nanotipbot/mostrecentdm.txt", "r+")
old_dm = old_file.read()
print(str(datetime.now()))
print("The oldest dm is: {}".format(old_dm))
new_dm = old_dm
# get most recent dms from twitter
dm_list = api.direct_messages(old_dm)
index = 0

for dm in dm_list:
    # Store the most recent DM inserted into the table
    if index == 0:
        new_dm = dm.id
    # Insert the DM into the table
    if dm.sender_id != 966739513195335680:
        cursor = db.cursor()
        print("DM ID: {} inserted into table".format(dm.id))
        try:
            cursor.execute(
                "INSERT INTO dm_list (dm_id, processed, sender_id, dm_text) \
                VALUES ({}, 0, {}, '{}')".format(dm.id,
                                                 dm.sender_id,
                                                 dm.text))
            db.commit()
            # api.send_direct_message(user_id = dm.sender_id, text = "Tip bot is under maintenance.  Your message
            # will be processed once we turn back on the system.  Do not resend commands you do not want processed.
            # Please send feedback to nanotipbot@gmail.com!")
        except MySQLdb.IntegrityError:
            print("Caught the error")
            raise
        except:
            raise
    """
    elif dm.sender_id == 158041278:
        cursor = db.cursor()
        print("Sender is admin.  DM ID {} entered into table".format(dm.id))
        cursor.execute("INSERT INTO dm_list (dm_id, processed, sender_id, dm_text) VALUES ({}, 0, {}, '{}')".format(
                                                                                        dm.id,dm.sender_id, dm.text))
    """
    index += 1
# if there were new DMs found, update the most recent DM
if index > 0:
    print("{} new DMs found".format(index))
    old_file.seek(0)
    old_file.write(str(new_dm))
    old_file.truncate()
    print("old_file updated")
else:
    print("No new DMs")

# Retrieve all unprocessed messages from dm_list table
unprocessed_dms = []
cursor = db.cursor()
cursor.execute("SELECT dm_id FROM dm_list\
                    WHERE processed=0\
                    AND sender_id <> {}".format(BOT_ID))
unprocessed_dms = cursor.fetchall()
for row in unprocessed_dms:
    dm = api.get_direct_message(row[0])
    # Mark that the dm has started processing
    cursor = db.cursor()
    cursor.execute("UPDATE dm_list SET processed=1 WHERE dm_id={}".format(dm.id))
    db.commit()
    dm_array = dm.text.split(" ")
    print('Sender ID: {} - DM ID {}: {}'.format(dm.sender_id, dm.id, dm.text))
    if dm_array[0].lower() == '!help':
        api.send_direct_message(user_id=dm.sender_id, text="Thank you for using the Nano Tip Bot!  Below is a list of "
        "commands, and a description of what they do:\n\n" + BULLET.encode("utf-8") + "!help: That's this command! "
        "Shows a list of all available commands and what they do.\n" + BULLET.encode( "utf-8") + " !register: Registers"
        " your twitter ID for an account that's tied to it.  This is used to store your tips. Make sure to withdraw to"
        " a private wallet, as the tip bot is not meant to be a long term storage device for Nano.\n" +
        BULLET.encode("utf-8") + " !balance: This returns the balance of the account linked with your Twitter ID.\n" +
        BULLET.encode("utf-8") + " !tip: Proper usage is !tip @username 1234.  This will send the "
        "requested amount of Nano to the account linked to that user's twitter ID.\n" + BULLET.encode("utf-8") +
        " !account: Once your registered, send !account to see your account.  You can use this to deposit more Nano to "
        "tip from your personal wallet.\n" + BULLET.encode("utf-8") + " !withdraw: Proper usage is !withdraw xrb_12345."
        "  This will send the full balance of your tip account to the provided Nano account.\n" +
        BULLET.encode("utf-8") + " !donate: Proper usage is !donate 1234.  This will send the requested donation to the"
        " Nano Tip Bot donation account to help fund the developer's efforts.\n\nNOTE: The tipbot processes actions at"
        " the top of every minute.  Please be patient!")
        print("Help message sent!")
    elif dm_array[0].lower() == '!balance':
        # Find the user's account information from the db
        cursor = db.cursor()
        cursor.execute("SELECT account FROM users\
                    where user_id = {}".format(dm.sender_id))
        data = cursor.fetchone()
        if data is None:
            print("User tried to check balance without an account")
            api.send_direct_message(user_id=dm.sender_id,
                                    text="There is no account linked to your username.  Please respond with "
                                    "!register to create an account!")
        else:
            sender_account = data[0]
            # check if there are pending blocks for the user's account
            pending_blocks = rpc.pending(account='{}'.format(sender_account))
            # if there are pending blocks, receive them
            if len(pending_blocks) > 0:
                for block in pending_blocks:
                    rpc.receive(wallet='{}'.format(WALLET), account='{}'.format(sender_account),
                                block='{}'.format(block))
            # Get the balance for the returned account
            balance_return = rpc.account_balance(account="{}".format(sender_account))
            # Convert the balance to Nano units
            balance = convert(balance_return['balance'], from_unit='raw', to_unit='XRB')
            balance_text = "Your balance is {} Nano.".format(balance)
            # Send a message to the user with their balance.
            api.send_direct_message(user_id=dm.sender_id, text=balance_text)
            print("Balance Message Sent!")
    elif dm_array[0].lower() == '!register':
        # Find the user's account information from the db
        cursor = db.cursor()
        cursor.execute("SELECT account, processed FROM users\
                           where user_id = {}".format(dm.sender_id))
        data = cursor.fetchone()
        if data is None:
            # Create a wallet to generate the account number
            sender_account = rpc.account_create(wallet="{}".format(WALLET), work=True)
            cursor.execute("INSERT INTO users\
                    (user_id, account, register) VALUES({}, '{}',1)".format(dm.sender_id, sender_account))
            db.commit()
            api.send_direct_message(user_id=dm.sender_id,
                                    text="You have successfully registered for an account.  Your account is {}.".format(
                                        sender_account))
            print("Register successful!")
        elif data[1] == '0':
            # The user has an account, but needed to register, so send a message to the user with their account
            sender_account = data[0]
            cursor.execute("UPDATE users\
                        SET register = 1 WHERE user_id = {} AND register = 0".format(dm.sender_id))
            api.send_direct_message(user_id=dm.sender_id,
                                    text="You have successfully registered for an account.  Your account "
                                         "number is {}".format(sender_account))
            print("User has an account, but needed to register.  Message sent")
        else:
            # The user had an account and already registered, so let them know their account.
            sender_account = data[0]
            api.send_direct_message(user_id=dm.sender_id,
                                    text="You already have registered your account.  Your account number "
                                         "is {}".format(sender_account))
            print("User has a registered account.  Message sent.")
    elif dm_array[0].lower() == '!tip':
        # check if there are 3 arguments
        if len(dm_array) == 3:
            # check if dm_array[1] is a valid username
            try:
                receiver_id_info = api.get_user(dm_array[1])
            except:
                api.send_direct_message(user_id=dm.sender_id,
                                        text="The username you provided is not valid.  Please double check and resend.")
                print("Sender sent invalid username")
                receiver_id_info = 0
            if float(receiver_id_info.id) == float(BOT_ID):
                print("Sender tried to tip the bot")
                api.send_direct_message(user_id=dm.sender_id,
                                        text="You can't tip the bot, silly!  If you'd like to donate, \
                                              try using the !donate command.")
            if receiver_id_info != 0 and receiver_id_info.id != BOT_ID:
                receiver_id = receiver_id_info.id
                # check if the sender has an account
                cursor = db.cursor()
                cursor.execute("SELECT account FROM users\
                    where user_id = {}".format(dm.sender_id))
                data = cursor.fetchone()
                if data is None:
                    print("Sender tried to tip without an account")
                    api.send_direct_message(user_id=dm.sender_id,
                                            text="There is no account linked to your username.  Please respond with "
                                                  "!register to create an account!")
                else:
                    sender_account = data[0]
                    # check if there are pending blocks for the user's account
                    pending_blocks = rpc.pending(account='{}'.format(sender_account))
                    # if there are pending blocks, receive them
                    if len(pending_blocks) > 0:
                        for block in pending_blocks:
                            rpc.receive(wallet='{}'.format(WALLET), account='{}'.format(sender_account),
                                        block='{}'.format(block))
                    # Get the balance for the returned account
                    balance_return = rpc.account_balance(account="{}".format(sender_account))
                    # Convert the balance to Nano units
                    balance = convert(balance_return['balance'], from_unit='raw', to_unit='XRB')
                    # Check to see if the tip amount is formatted correctly.
                    wrong_tip = 0
                    try:
                        print("The user is sending {} NANO".format(float(dm_array[2])))
                    except:
                        wrong_tip = 1
                    if wrong_tip == 1:
                        api.send_direct_message(user_id=dm.sender_id, text="Only number amounts are accepted.  "
                                                        "Please resend as !tip @username 1234")
                    elif float(balance) < float(dm_array[2]):
                        print("Sender tried to send more than their account")
                        api.send_direct_message(user_id=dm.sender_id, text="Your balance is only {} Nano and you tried"
                                            " to send {}.  Please add more Nano to your account, or lower your "
                                            "tip amount.".format(balance, float(dm_array[2])))
                    elif float(dm_array[2]) < 0.00001:
                        print("Sender tried to send less than 0.00001")
                        api.send_direct_message(user_id=dm.sender_id,
                                                text="The minimum tip amount is 0.00001.  Please update your tip "
                                                      "amount and resend.")
                    else:
                        # retrieve the receiver's account from the db
                        cursor.execute("SELECT account FROM users\
                            where user_id = {}".format(receiver_id))
                        receiver_account_data = cursor.fetchone()
                        if receiver_account_data is None:
                            # Create an account number and insert into the db
                            receiver_account = rpc.account_create(wallet="{}".format(WALLET), work=True)
                            cursor.execute("INSERT INTO users\
                                            (user_id, account, register) VALUES({}, '{}',0)".format(receiver_id,
                                                                                                    receiver_account))
                            db.commit()
                            print("Sender sent to a new receiving account.  Created {}.".format(receiver_account))
                        else:
                            receiver_account = receiver_account_data[0]
                        # convert the send amount to raw
                        send_amount = convert(dm_array[2], from_unit='XRB', to_unit='raw')
                        # Send the tip
                        send_hash = rpc.send(wallet="{}".format(WALLET), source="{}".format(sender_account),
                                             destination="{}".format(receiver_account),
                                             amount="{:f}".format(send_amount))
                        # Inform the user that the tip was sent with the hash
                        api.send_direct_message(user_id=dm.sender_id, text="You've successfully sent a {} NANO tip to "
                                                        "@{}! You can check block hash {} "
                                                        "on https://www.nanode.co/".format(dm_array[2],
                                                                                          receiver_id_info.screen_name,
                                                                                          send_hash))
                        # Inform the receiver that they got a tip!
                        dm_send_amount = float(dm_array[2])
                        sender_id_info = api.get_user(dm.sender_id)
                        api.update_status(status="Hey @{}, @{} just sent you a {} $NANO tip!  Send @nanotipbot a DM "
                                                  "with !register to claim your funds or !help for more commands.  "
                                                  "If you want to learn more about Nano, go to https://nano.org/".format(
                                                                            receiver_id_info.screen_name,
                                                                            sender_id_info.screen_name, dm_array[2]))
        else:
            api.send_direct_message(user_id=dm.sender_id,
                                    text="Incorrect syntax.  Please use the format !tip @username 123")
    elif dm_array[0].lower() == '!withdraw':
        # check if there is a 2nd argument
        if len(dm_array) == 2:
            # if there is, retrieve the sender's account and wallet
            cursor = db.cursor()
            cursor.execute("SELECT account FROM users\
                            where user_id = {}".format(dm.sender_id))
            data = cursor.fetchone()
            if data is None:
                api.send_direct_message(user_id=dm.sender_id,
                                        text="You do not have an account.  Respond with !register to set one up.")
                print("User tried to withdraw with no account")
            else:
                sender_account = data[0]
                # check if there are pending blocks for the user's account
                pending_blocks = rpc.pending(account='{}'.format(sender_account))
                # if there are pending blocks, receive them
                if len(pending_blocks) > 0:
                    for block in pending_blocks:
                        rpc.receive(wallet='{}'.format(WALLET), account='{}'.format(sender_account),
                                    block='{}'.format(block))
                # find the total balance of the account
                balance_return = rpc.account_balance(account='{}'.format(sender_account))
                receiver_account = dm_array[1].lower()
                # if the balance is 0, send a message that they have nothing to withdraw
                if rpc.validate_account_number(receiver_account) == 0:
                    print("The xrb account number is invalid: {}".format(receiver_account))
                    api.send_direct_message(user_id=dm.sender_id,
                                            text="The account number you provided is invalid.  Please double check "
                                                  "and resend your request.")
                elif balance_return['balance'] == 0:
                    print("The user tried to withdraw with 0 balance")
                    api.send_direct_message(user_id=dm.sender_id, text="You have a 0 balance in your account.  Please "
                                                    "deposit to your address {} to send more tips!".format(
                                                                                                    sender_account))
                else:
                    # send the total balance to the provided account
                    send_hash = rpc.send(wallet="{}".format(WALLET), source="{}".format(sender_account),
                                         destination="{}".format(receiver_account), amount=balance_return['balance'])
                    # respond that the withdraw has been processed
                    balance = convert(balance_return['balance'], from_unit='raw', to_unit='XRB')
                    api.send_direct_message(user_id=dm.sender_id, text="You've successfully withdrawn {} NANO to "
                    "account {}.  You can check block hash {} on https://www.nanode.co/".format(float(balance),
                                                                                                receiver_account,
                                                                                                send_hash))
                    print("Withdraw processed.  Hash: {}".format(send_hash))
        else:
            print("User sent a withdraw with invalid syntax.")
            api.send_direct_message(user_id=dm.sender_id,
                                    text="Incorrect syntax.  Please use the format !withdraw (account)")
    elif dm_array[0].lower() == '!donate':
        # check if there are 2 arguments
        if len(dm_array) == 2:
            # if there are, retrieve the sender's account and wallet
            cursor = db.cursor()
            cursor.execute("SELECT account FROM users\
                           where user_id = {}".format(dm.sender_id))
            data = cursor.fetchone()
            sender_account = data[0]
            # check if there are pending blocks for the user's account
            pending_blocks = rpc.pending(account='{}'.format(sender_account))
            # if there are pending blocks, receive them
            if len(pending_blocks) > 0:
                for block in pending_blocks:
                    rpc.receive(wallet='{}'.format(WALLET), account='{}'.format(sender_account),
                                block='{}'.format(block))
            # find the total balance of the account
            balance_return = rpc.account_balance(account='{}'.format(sender_account))
            receiver_account = BOT_ACCOUNT
            # Convert the balance to Nano units
            balance = convert(balance_return['balance'], from_unit='raw', to_unit='XRB')
            if float(balance) < float(dm_array[1]):
                print("User tried to donate more than their balance.")
                api.send_direct_message(user_id=dm.sender_id, text="Your balance is only {} Nano and you tried to send "
                                 "{}. Please add more Nano to your account, or lower your donation "
                                 "amount.".format(balance, float(dm_array[1])))
            elif float(dm_array[1]) < 0.000001:
                print("User tried to donate less than 0.000001")
                api.send_direct_message(user_id=dm.sender_id,
                                        text="The minimum donation amount is 0.000001.  Please update your donation "
                                              "amount and resend.")
            else:
                # convert the send amount to raw
                send_amount = convert(dm_array[1], from_unit='XRB', to_unit='raw')
                # Send the tip
                send_hash = rpc.send(wallet="{}".format(WALLET), source="{}".format(sender_account),
                                     destination="{}".format(receiver_account), amount="{:f}".format(send_amount))
                # Inform the user that the tip was sent with the hash
                api.send_direct_message(user_id=dm.sender_id, text="Thank you for your generosity! "
                                                                    "You can check your donation status "
                                                                    "under block hash {} on "
                                                                    "https://www.nanode.co/".format(send_hash))
                print("Donation processed.  Hash: {}".format(send_hash))
        else:
            print("User sent a donation with invalid syntax")
            api.send_direct_message(user_id=dm.sender_id, text="Incorrect synatx.  Please use the format !donate 1234")

    elif dm_array[0].lower() == '!account':
        cursor = db.cursor()
        cursor.execute("SELECT account FROM users\
                                where user_id = {}".format(dm.sender_id))
        data = cursor.fetchone()
        if data is None:
            api.send_direct_message(user_id=dm.sender_id,
                                    text="You do not have an account.  Please respond with !register to set one up.")
            print("User tried to find their account, but is not registered")
        else:
            sender_account = data[0]
            cursor.execute("UPDATE users\
                        SET register = 1 WHERE user_id = {} AND register = 0".format(dm.sender_id))
            db.commit()
            print("Sending the user their account number.")
            api.send_direct_message(user_id=dm.sender_id, text="Your account number is {}.".format(sender_account))
    else:
        print("User sent message that does not match any key commands")
        api.send_direct_message(user_id=dm.sender_id,
                                text="That command or syntax is not recognized.  Please send !help for a list of "
                                      "commands and what they do.")
        cursor.execute("UPDATE dm_list\
                SET processed=2 WHERE dm_id={}".format(dm.id))
        db.commit()
    index += 1

old_file.close()
db.close()