# DEPENDENCIES =========================================
from datetime import datetime

import MySQLdb
import nano
import tweepy
from ConfigParser import SafeConfigParser
from nano import convert

# TODO LIST ===========================================
# TODO: Make user register before gaining access to any other command.
# TODO: Add !privatetip to allow users to tip without sending a public tweet
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


def main():

    global stored_response
    dm_list, num_waiting_messages, new_dm, old_file = getOldDm()

    setDMList(dm_list, num_waiting_messages, new_dm, old_file)

    # Retrieve all unprocessed messages from dm_list table
    get_unprocessed_call = ("SELECT dm_id, sender_id, dm_text FROM dm_list WHERE processed=0 AND sender_id <> {}".format(BOT_ID))
    unprocessed_dms = getDBInfo(get_unprocessed_call)

    for current_dm in unprocessed_dms:
        # Initialize values
        tip_error = 0
        temp_dm_id = current_dm[0]
        temp_sender_id = current_dm[1]
        temp_dm_text = current_dm[2]
        dm = setDM(temp_dm_id, temp_sender_id, temp_dm_text)

        # Mark that the dm has started processing
        flag_in_process = ("UPDATE dm_list SET processed=1 WHERE dm_id={}".format(dm.id))
        setDBInfo(flag_in_process)
        dm_array = dm.text.split(" ")
        print('Sender ID: {} - DM ID {}: {}'.format(dm.sender_id, dm.id, dm.text))

        # Check the command sent by the user
        if dm_array[0].lower() == '!help':
            stored_response, tip_error = helpProcess(dm, tip_error)

        elif dm_array[0].lower() == '!balance':
            stored_response, tip_error = balanceProcess(dm, tip_error)

        elif dm_array[0].lower() == '!register':
            tip_error = registerProcess(dm, tip_error)

        elif dm_array[0].lower() == '!tip':
            tip_error = tipProcess(dm, dm_array, tip_error)

        elif dm_array[0].lower() == '!withdraw':
            tip_error = withdrawProcess(dm, dm_array, tip_error)

        elif dm_array[0].lower() == '!donate':
            tip_error = donateProcess(dm, dm_array, tip_error)

        elif dm_array[0].lower() == '!account':
            tip_error = accountProcess(dm, tip_error)

        else:
            tip_error = wrongMessageProcess(dm)

        # Check if there are any errors and log them
        errorCheck(dm, stored_response, tip_error)

        old_file.close()
        db.commit()


def errorCheck(dm, stored_response, tip_error):

    if tip_error == 1:
        error_set = ("UPDATE dm_list SET processed=3 WHERE dm_id={}".format(dm.id))
        setDBInfo(error_set)
    elif tip_error == 2:
        print(stored_response)
        rate_limit_fix = ("UPDATE dm_list SET processed=4, dm_response='{}' "
                            "WHERE dm_id={}".format(str(stored_response), dm.id))
        setDBInfo(rate_limit_fix)
        print("{}: Rate limit hit.  DM set to reprocess.".format(str(datetime.now())))
    else:
        processed_set = ("UPDATE dm_list SET processed=2 "
                            "WHERE dm_id={}".format(dm.id))
        setDBInfo(processed_set)


def wrongMessageProcess(dm):
    global stored_response
    tip_error = 1
    wrong_format_text = ("The command or syntax you sent is not recognized.  Please send !help for a list of "
                         "commands and what they do.")
    stored_response = wrong_format_text
    tip_error = sendDM(dm.sender_id, wrong_format_text, tip_error)
    print("{}: User sent message that does not match any key commands".format(str(datetime.now())))
    return tip_error


def accountProcess(dm, tip_error):
    global stored_response
    sender_account_call = ("SELECT account FROM users where user_id = {}".format(dm.sender_id))
    account_data = getDBInfo(sender_account_call)
    if not account_data:
        account_none_text = "You do not have an account.  Respond with !register to set one up."
        tip_error = 1
        stored_response = account_none_text
        tip_error = sendDM(dm.sender_id, account_none_text, tip_error)
        print("{}: User tried to find their account with no account".format(str(datetime.now())))
    else:
        sender_account = account_data[0][0]
        set_register_call = ("UPDATE users SET register = 1 WHERE user_id = {} AND register = 0".format(dm.sender_id))
        setDBInfo(set_register_call)
        account_text = ("Your account number is {}".format(sender_account))
        stored_response = account_text
        tip_error = sendDM(dm.sender_id, account_text, tip_error)
        print("{}: Sent the user their account number.".format(str(datetime.now())))
    return tip_error


def donateProcess(dm, dm_array, tip_error):
    global stored_response
    # check if there are 2 arguments
    if len(dm_array) == 2:
        # if there are, retrieve the sender's account
        sender_account_call = ("SELECT account FROM users where user_id = {}".format(dm.sender_id))
        donate_data = getDBInfo(sender_account_call)
        sender_account = donate_data[0][0]
        # check pending blocks for the user's account
        receivePending(sender_account)
        # find the total balance of the account
        balance_return = rpc.account_balance(account='{}'.format(sender_account))
        receiver_account = BOT_ACCOUNT
        # Convert the balance to Nano units
        balance = convert(balance_return['balance'], from_unit='raw', to_unit='XRB')
        # Check to see if the tip amount is formatted correctly.
        wrong_donate = 0
        try:
            print("{}: The user is donating {} NANO".format(str(datetime.now()), float(dm_array[1])))
        except:
            wrong_donate = 1
        if wrong_donate == 1:
            tip_error = 1
            wrong_donate_text = "Only number amounts are accepted.  Please resend as !donate 1234"
            stored_response = wrong_donate_text
            tip_error = sendDM(dm.sender_id, wrong_donate_text, tip_error)
            print("{}: User sent a donation that wasn't a number.".format(str(datetime.now())))
        elif float(balance) < float(dm_array[1]):
            tip_error = 1
            large_donate_text = ("Your balance is only {} NANO and you tried to send {}.  Please add more NANO"
                                 " to your account, or lower your donation amount.".format(balance, float(dm_array[1])))
            stored_response = large_donate_text
            tip_error = sendDM(dm.sender_id, large_donate_text, tip_error)
            print("User tried to donate more than their balance.")
        elif float(dm_array[1]) < 0.000001:
            tip_error = 1
            small_donate_text = ("The minimum donation amount is 0.000001.  Please update your donation amount "
                                 "and resend.")
            stored_response = small_donate_text
            tip_error = sendDM(dm.sender_id, small_donate_text, tip_error)
            print("User tried to donate less than 0.000001")
        else:
            # convert the send amount to raw
            send_amount = convert(dm_array[1], from_unit='XRB', to_unit='raw')
            # Send the tip
            send_hash = rpc.send(wallet="{}".format(WALLET), source="{}".format(sender_account),
                                 destination="{}".format(receiver_account), amount="{:f}".format(send_amount))
            # Inform the user that the tip was sent with the hash
            donate_text = ("Thank you for your generosity!  You've successfully donated {} NANO!  You can check the "
                           "transaction at https://www.nanode.co/block/{}".format(float(dm_array[1]), send_hash))
            stored_response = donate_text
            tip_error = sendDM(dm.sender_id, donate_text, tip_error)
            print(
                "{}: {} NANO donation processed.  Hash: {}".format(str(datetime.now()), float(dm_array[1]), send_hash))
    else:
        tip_error = 1
        incorrect_donate_text = "Incorrect syntax.  Please use the format !donate 1234"
        stored_response = incorrect_donate_text
        tip_error = sendDM(dm.sender_id, incorrect_donate_text, tip_error)
        print("{}: User sent a donation with invalid syntax".format(str(datetime.now())))
    return tip_error


def withdrawProcess(dm, dm_array, tip_error):
    global stored_response
    # check if there is a 2nd argument
    if len(dm_array) == 2:
        # if there is, retrieve the sender's account and wallet
        withdraw_account_call = ("SELECT account FROM users where user_id = {}".format(dm.sender_id))
        withdraw_data = getDBInfo(withdraw_account_call)
        if not withdraw_data:
            withdraw_no_account_text = "You do not have an account.  Respond with !register to set one up."
            tip_error = 1
            stored_response = withdraw_no_account_text
            tip_error = sendDM(dm.sender_id, withdraw_no_account_text, tip_error)
            print("{}: User tried to withdraw with no account".format(str(datetime.now())))
        else:
            sender_account = withdraw_data[0][0]
            # check if there are pending blocks for the user's account
            receivePending(sender_account)
            # find the total balance of the account
            balance_return = rpc.account_balance(account='{}'.format(sender_account))
            receiver_account = dm_array[1].lower()
            # if the balance is 0, send a message that they have nothing to withdraw
            if rpc.validate_account_number(receiver_account) == 0:
                tip_error = 1
                invalid_account_text = ("The account number you provided is invalid.  Please double check and "
                                        "resend your request.")
                stored_response = invalid_account_text
                tip_error = sendDM(dm.sender_id, invalid_account_text, tip_error)
                print("{}: The xrb account number is invalid: {}".format(str(datetime.now()), receiver_account))
            elif balance_return['balance'] == 0:
                tip_error = 1
                no_balance_text = ("You have 0 balance in your account.  Please deposit to your address {} to "
                                   "send more tips!".format(sender_account))
                stored_response = no_balance_text
                tip_error = sendDM(dm.sender_id, no_balance_text, tip_error)
                print("{}: The user tried to withdraw with 0 balance".format(str(datetime.now())))
            else:
                # send the total balance to the provided account
                send_hash = rpc.send(wallet="{}".format(WALLET), source="{}".format(sender_account),
                                     destination="{}".format(receiver_account), amount=balance_return['balance'])
                # respond that the withdraw has been processed
                balance = convert(balance_return['balance'], from_unit='raw', to_unit='XRB')
                withdraw_text = ("You've successfully withdrawn {} NANO!  You can check the "
                                 "transaction at https://www.nanode.co/block/{}".format(float(balance), send_hash))
                stored_response = withdraw_text
                tip_error = sendDM(dm.sender_id, withdraw_text, tip_error)
                print("{}: Withdraw processed.  Hash: {}".format(str(datetime.now()), send_hash))
    else:
        tip_error = 1
        incorrect_withdraw_text = "Incorrect syntax.  Please use the format !withdraw xrb_1234"
        stored_response = incorrect_withdraw_text
        tip_error = sendDM(dm.sender_id, incorrect_withdraw_text, tip_error)
        print("{}: User sent a withdraw with invalid syntax.".format(str(datetime.now())))
    return tip_error


def tipProcess(dm, dm_array, tip_error):
    global stored_response
    # check if there are 3 arguments
    if len(dm_array) == 3:
        # check if dm_array[1] is a valid username
        try:
            receiver_id_info = api.get_user(dm_array[1])
        except:
            invalid_username_text = "The username you provided is not valid.  Please double check and resend."
            tip_error = 1
            stored_response = invalid_username_text
            tip_error = sendDM(dm.sender_id, invalid_username_text, tip_error)
            print("{}: Sender sent invalid username".format(str(datetime.now())))
        else:
            if float(receiver_id_info.id) == float(BOT_ID):
                tip_the_bot_text = "You can't tip the bot, silly!  If you'd like to donate, try using the !donate command"
                tip_error = 1
                stored_response = tip_the_bot_text
                tip_error = sendDM(dm.sender_id, tip_the_bot_text, tip_error)
                print("{}: Sender tried to tip the bot".format(str(datetime.now())))
            elif float(receiver_id_info.id) == float(dm.sender_id):
                tip_yourself_text = "You can't tip yourself.  Please review your tip message and make sure you SPREAD the NANO!"
                tip_error = 1
                stored_response = tip_yourself_text
                tip_error = sendDM(dm.sender_id, tip_yourself_text, tip_error)
                print("{}: Sender tried to tip themselves.".format(str(datetime.now())))
            else:
                receiver_id = receiver_id_info.id
                # check if the sender has an account
                account_check = ("SELECT account FROM users where user_id = {}".format(dm.sender_id))
                tip_data = getDBInfo(account_check)
                if not tip_data:
                    no_account_text = ("There is no account linked to yor username.  Please respond with !register "
                                       "to create an account!")
                    tip_error = 1
                    stored_response = no_account_text
                    tip_error = sendDM(dm.sender_id, no_account_text, tip_error)
                    print("{}: Sender tried to tip without an account".format(str(datetime.now())))
                else:
                    sender_account = tip_data[0][0]
                    # check if there are pending blocks for the user's account
                    receivePending(sender_account)
                    # Get the balance for the returned account
                    balance_return = rpc.account_balance(account="{}".format(sender_account))
                    # Convert the balance to Nano units
                    balance = convert(balance_return['balance'], from_unit='raw', to_unit='XRB')
                    # Check to see if the tip amount is formatted correctly.
                    wrong_tip = 0
                    try:
                        print("{}: The user is sending {} NANO".format(str(datetime.now()), float(dm_array[2])))
                    except:
                        wrong_tip = 1
                    if wrong_tip == 1:
                        wrong_tip_text = "Only number amounts are accepted.  Please resend as !tip @username 1234"
                        tip_error = 1
                        stored_response = wrong_tip_text
                        tip_error = sendDM(dm.sender_id, wrong_tip_text, tip_error)
                        print("{}: User sent a tip that wasn't a number.".format(str(datetime.now())))
                    elif float(balance) < float(dm_array[2]):
                        low_balance_text = ("Your balance is only {} NANO and you tried to send {}.  Please add "
                                            "more NANO to your account, or lower your tip amount."
                                            .format(balance, float(dm_array[2])))
                        tip_error = 1
                        stored_response = low_balance_text
                        tip_error = sendDM(dm.sender_id, low_balance_text, tip_error)
                        print("{}: Sender tried to send more than their account".format(str(datetime.now())))
                    elif float(dm_array[2]) < 0.00001:
                        small_tip_text = ("The minimum tip amount is 0.00001.  Please update your tip amount and "
                                          "resend.")
                        tip_error = 1
                        stored_response = small_tip_text
                        tip_error = sendDM(dm.sender_id, small_tip_text, tip_error)
                        print("{}: Sender tried to send less than 0.00001".format(str(datetime.now())))
                    else:
                        # retrieve the receiver's account from the db
                        receiver_account_get = ("SELECT account FROM users where user_id = {}".format(receiver_id))
                        receiver_account_data = getDBInfo(receiver_account_get)
                        if not receiver_account_data:
                            # Create an account number and insert into the db
                            receiver_account = rpc.account_create(wallet="{}".format(WALLET), work=True)
                            create_receiver_account = ("INSERT INTO users (user_id, account, register) VALUES({}, "
                                                       "'{}',0)".format(receiver_id, receiver_account))
                            setDBInfo(create_receiver_account)
                            print("{}: Sender sent to a new receiving account.  Created  account {}".format(
                                                                        str(datetime.now()),receiver_account))
                        else:
                            receiver_account = receiver_account_data[0][0]
                        # convert the send amount to raw
                        send_amount = convert(dm_array[2], from_unit='XRB', to_unit='raw')
                        # Send the tip
                        send_hash = rpc.send(wallet="{}".format(WALLET), source="{}".format(sender_account),
                                             destination="{}".format(receiver_account),
                                             amount="{:f}".format(send_amount))
                        # Inform the user that the tip was sent with the hash
                        sent_tip_text = ("You've successfully sent a {} NANO tip to @{}!  You can check the transaction"
                                         "at https://www.nanode.co/block/{}".format(dm_array[2],
                                                                                    receiver_id_info.screen_name,
                                                                                    send_hash))
                        stored_response = sent_tip_text
                        tip_error = sendDM(dm.sender_id, sent_tip_text, tip_error)
                        # Inform the receiver that they got a tip!
                        sender_id_info = api.get_user(dm.sender_id)
                        api.update_status(status="Hey @{}, @{} just sent you a {} $NANO tip!  Send @NanoTipBot a DM "
                                                 "with !register to claim your funds or !help for more commands.  "
                                                 "If you want to learn more about Nano, go to https://nano.org/"
                                          .format(receiver_id_info.screen_name, sender_id_info.screen_name,
                                                  dm_array[2]))
                        # Update the dm_list with the receiver's ID and amount sent
                        update_receiver_info = ("UPDATE dm_list SET receiver_id = {}, amount = {} WHERE dm_id={}"
                                                .format(receiver_id, float(dm_array[2]), dm.id))
                        setDBInfo(update_receiver_info)
                        print("{}: Tip processed successfully under hash {}.".format(str(datetime.now()), send_hash))
    else:
        invalid_tip_text = "Incorrect syntax.  Please use the format !tip @username 123"
        tip_error = 1
        stored_response = invalid_tip_text
        tip_error = sendDM(dm.sender_id, invalid_tip_text, tip_error)
        print("{}: Tip sent with incorrect syntax.".format(str(datetime.now())))
    return tip_error


def registerProcess(dm, tip_error):
    global stored_response
    # Find the user's account information from the db
    register_call = ("SELECT account, register FROM users where user_id = {}".format(dm.sender_id))
    data = getDBInfo(register_call)
    if not data:
        # Create an account for the user
        sender_account = rpc.account_create(wallet="{}".format(WALLET), work=True)
        account_create_call = ("INSERT INTO users (user_id, account, register) "
                               "VALUES({}, '{}',1)".format(dm.sender_id, sender_account))
        setDBInfo(account_create_call)
        account_create_text = ("You have successfully registered for an account.  Your account is {}".format(
            sender_account))
        stored_response = account_create_text
        tip_error = sendDM(dm.sender_id, account_create_text, tip_error)
        print("{}: Register successful!".format(str(datetime.now())))
    elif data[0][1] == 0:
        # The user has an account, but needed to register, so send a message to the user with their account
        sender_account = data[0][0]
        account_registration_update = ("UPDATE users SET register = 1 WHERE user_id = {} AND "
                                       "register = 0".format(dm.sender_id))
        setDBInfo(account_registration_update)
        account_registration_text = ("You have successfully registered for an account.  Your account "
                                     "number is {}".format(sender_account))
        stored_response = account_registration_text
        tip_error = sendDM(dm.sender_id, account_registration_text, tip_error)
        print("{}: User has an account, but needed to register.  Message sent".format(str(datetime.now())))
    else:
        # The user had an account and already registered, so let them know their account.
        sender_account = data[0][0]
        account_already_registered = ("You already have registered your account.  Your account number "
                                      "is {}".format(sender_account))
        stored_response = account_already_registered
        tip_error = sendDM(dm.sender_id, account_already_registered, tip_error)
        print("{}: User has a registered account.  Message sent.".format(str(datetime.now())))
    return tip_error


def balanceProcess(dm, tip_error):
    global stored_response
    # Find the user's account information from the db
    balance_call = ("SELECT account FROM users where user_id = {}".format(dm.sender_id))
    data = getDBInfo(balance_call)
    if not data:
        print("{}: User tried to check balance without an account".format(str(datetime.now())))
        tip_error = 1
        balance_message = ("There is no account linked to your username.  Please respond with !register to "
                           "create an account.")
        stored_response = balance_message
        tip_error = sendDM(dm.sender_id, balance_message, tip_error)
    else:
        sender_account = data[0][0]
        # Check for pending blocks, receive them and send the user their balance
        receivePending(sender_account)
        # Update the user's account to registered if it wasn't already
        account_registration_update = ("UPDATE users SET register = 1 WHERE user_id = {} AND "
                                       "register = 0".format(dm.sender_id))
        setDBInfo(account_registration_update)
        balance_return = rpc.account_balance(account="{}".format(sender_account))
        balance = convert(balance_return['balance'], from_unit='raw', to_unit='XRB')
        balance_text = "Your balance is {} NANO.".format(balance)
        stored_response = balance_text
        tip_error = sendDM(dm.sender_id, balance_text, tip_error)
        print("{}: Balance Message Sent!".format(str(datetime.now())))
    return stored_response, tip_error


def setDMList(dm_list, num_waiting_messages, new_dm, old_file):
    for curr_dm in dm_list:
        # Store the most recent DM inserted into the table
        if num_waiting_messages == 0:
            new_dm = curr_dm.id
        # Insert the DM into the table
        if curr_dm.sender_id != BOT_ID:
            db_entry = ("INSERT INTO dm_list (dm_id, processed, sender_id, dm_text) \
                    VALUES ({}, 0, {}, '{}')".format(curr_dm.id, curr_dm.sender_id, curr_dm.text))
            setDBInfo(db_entry)
        num_waiting_messages += 1
    # if there were new DMs found, update the most recent DM
    if num_waiting_messages > 0:
        print("{} new DMs found".format(num_waiting_messages))
        old_file.seek(0)
        old_file.write(str(new_dm))
        old_file.truncate()
        print("old_file updated")
    else:
        print("No new DMs")


def getOldDm():
    # pull old most recent DM
    old_file = open("/root/nanotipbot/mostrecentdm.txt", "r+")
    old_dm = old_file.read()
    print(str(datetime.now()))
    print("The oldest dm is: {}".format(old_dm))
    new_dm = old_dm
    # get most recent dms from twitter
    dm_list = api.direct_messages(old_dm)
    num_waiting_messages = 0
    return dm_list, num_waiting_messages, new_dm, old_file


def helpProcess(dm, tip_error):
    global stored_response
    help_message = ("Thank you for using the Nano Tip Bot!  Below is a list of commands, and a description of "
                    "what they do:\n\n" + BULLET + " !help: That's this command! Shows a list of "
                    "all available commands and what they do.\n" + BULLET + " !register: Registers your twitter ID for"
                    " an account that's tied to it.  This is used to store your tips. Make sure to withdraw to a "
                    "private wallet, as the tip bot is not meant to be a long term storage device for Nano.\n" + BULLET
                    + " !balance: This returns the balance of the account linked with your Twitter ID.\n" + BULLET +
                    " !tip: Proper usage is !tip @username 1234.  This will send the requested amount of Nano to the "
                    "account linked to that user's twitter ID.\n" + BULLET + " !account: Once your registered, send "
                    "!account to see your account.  You can use this to deposit more Nano to tip from your personal "
                    "wallet.\n" + BULLET + " !withdraw: Proper usage is !withdraw xrb_12345.  This will send "
                    "the full balance of your tip account to the provided Nano account.\n" + BULLET + " !donate: Proper "
                    "usage is !donate 1234.  This will send the requested donation to the Nano Tip Bot donation account"
                    " to help fund the developer's efforts.\n\nNOTE: The tip bot processes actions at the top of every "
                    "minute.  Please be patient!")
    stored_response = help_message
    tip_error = sendDM(dm.sender_id, help_message, tip_error)
    print("{}: Help message sent!".format(str(datetime.now())))
    return stored_response, tip_error


# Send Direct Message with API Limit checking
def sendDM(receiver, message, tip_error):
    try:
        api.send_direct_message(user_id=receiver, text=message)
    except tweepy.TweepError:
        tip_error = 2
    except:
        print("{}: There was an unexpected error with sending a DM.".format(str(datetime.now())))
        raise

    return tip_error


# Get Information from DB
def getDBInfo(db_call):
    db_cursor = db.cursor()
    db_cursor.execute(db_call)
    db_data = db_cursor.fetchall()
    db_cursor.close()
    return db_data


# Set Information to DB
def setDBInfo(db_call):
    db_cursor = db.cursor()
    db_cursor.execute(db_call)
    db.commit()
    db_cursor.close()
    return


# Receive Pending Blocks
def receivePending(sender_account):
    pending_blocks = rpc.pending(account='{}'.format(sender_account))
    if len(pending_blocks) > 0:
        for block in pending_blocks:
            rpc.receive(wallet='{}'.format(WALLET), account='{}'.format(sender_account), block='{}'.format(block))
    return


def rateLimitResend():
    rate_limit_resend_call = "SELECT dm_id, sender_id, dm_response, first_attempt FROM dm_list WHERE processed=4"
    rate_limit_resend_data = getDBInfo(rate_limit_resend_call)
    for dm in rate_limit_resend_data:
        if dm[3] == 0:
            first_time_set = ("UPDATE dm_list SET first_attempt=1 WHERE dm_id={}".format(dm[0]))
            setDBInfo(first_time_set)
        else:
            tip_error = 0
            tip_error = sendDM(dm[1], dm[2], tip_error)
            if tip_error == 2:
                print("{}: Rate limit retried and failed.  Will retry in 1 minute.".format(str(datetime.now())))
            else:
                processed_set = ("UPDATE dm_list SET processed=2 WHERE dm_id={}".format(dm[0]))
                setDBInfo(processed_set)


class setDM:
    def __init__(self, dm_id, sender_id, dm_text):
        self.id = dm_id
        self.sender_id = sender_id
        self.text = dm_text


main()
rateLimitResend()
