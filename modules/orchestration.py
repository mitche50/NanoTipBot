from modules.db import *
from modules.currency import *
from modules.social import *

import logging
import nano
import configparser
from datetime import datetime
from decimal import Decimal

# Set Log File
logging.basicConfig(handlers=[logging.FileHandler('/root/webhooks/webhooks.log', 'a', 'utf-8')],
                    level=logging.INFO)

# Read config and parse constants
config = configparser.ConfigParser()
config.read('/root/webhooks/webhookconfig.ini')

# Set constants
BULLET = u"\u2022"
NODE_IP = config.get('webhooks', 'node_ip')
WALLET = config.get('webhooks', 'wallet')
BOT_ID_TWITTER = config.get('webhooks', 'bot_id_twitter')
BOT_NAME = config.get('webhooks', 'bot_name')
BOT_ACCOUNT = config.get('webhooks', 'bot_account')
MIN_TIP = config.get('webhooks', 'min_tip')

balance_commands = [
    '!balance',
    '!bal',
    '!b',
    '/balance',
    '/bal',
    '/b'
]

account_commands = [
    '!account',
    '!acc',
    '!a',
    '!deposit',
    '!d',
    '/account',
    '/acc',
    '/a',
    '/deposit',
    '/d'
]

help_commands = [
    '!help',
    '!h',
    '/help',
    '/h',
    '/start'
]

register_commands = [
    '!register',
    '!reg',
    '!r',
    '/register',
    '/reg',
    '/r'
]

withdraw_commands = [
    '!withdraw',
    '!w',
    '/withdraw',
    '/w'
]

donate_commands = [
    '!donate',
    '/donate'
]

tip_commands = [
    '!tip',
    '!t',
    '/tip',
    '/t'
]

private_tip_commands = [
    '!privatetip',
    '!private',
    '!pt',
    '/privatetip',
    '/private',
    '/pt'
]

# Connect to global functions
rpc = nano.rpc.Client(NODE_IP)


def parse_action(message):
    if message['dm_action'] in help_commands:
        new_pid = os.fork()
        if new_pid == 0:
            try:
                help_process(message)
            except Exception as e:
                logging.info("Exception: {}".format(e))
                raise e
            os._exit(0)
        else:
            return '', HTTPStatus.OK

    elif message['dm_action'] in balance_commands:
        new_pid = os.fork()
        if new_pid == 0:
            try:
                bot_status = config.get('webhooks', 'bot_status')
                if bot_status == 'maintenance':
                    send_dm(message['sender_id'], "The tip bot is in maintenance.  Check @NanoTipBot on Twitter for more information.", message['system'])
                else:
                    balance_process(message)
            except Exception as e:
                logging.info("Exception: {}".format(e))
                raise e
            os._exit(0)
        else:
            return '', HTTPStatus.OK

    elif message['dm_action'] in register_commands:
        new_pid = os.fork()
        if new_pid == 0:
            try:
                bot_status = config.get('webhooks', 'bot_status')
                if bot_status == 'maintenance':
                    send_dm(message['sender_id'], "The tip bot is in maintenance.  Check @NanoTipBot on Twitter for more information.", message['system'])
                else:
                    register_process(message)
            except Exception as e:
                logging.info("Exception: {}".format(e))
                raise e
            os._exit(0)
        else:
            return '', HTTPStatus.OK

    elif message['dm_action'] in tip_commands:
        new_pid = os.fork()
        if new_pid == 0:
            try:
                redirect_tip_text = ("Tips are processed through public messages now.  Please send in the format "
                                     "@NanoTipBot !tip .0001 @user1.")
                send_dm(message['sender_id'], redirect_tip_text, message['system'])
            except Exception as e:
                logging.info("Exception: {}".format(e))
                raise e
            os._exit(0)
        else:
            return '', HTTPStatus.OK

    elif message['dm_action'] in withdraw_commands:
        new_pid = os.fork()
        if new_pid == 0:
            try:
                bot_status = config.get('webhooks', 'bot_status')
                if bot_status == 'maintenance':
                    send_dm(message['sender_id'], "The tip bot is in maintenance.  Check @NanoTipBot on Twitter for more information.", message['system'])
                else:
                    withdraw_process(message)
            except Exception as e:
                logging.info("Exception: {}".format(e))
                raise e
            os._exit(0)
        else:
            return '', HTTPStatus.OK

    elif message['dm_action'] in donate_commands:
        new_pid = os.fork()
        if new_pid == 0:
            try:
                bot_status = config.get('webhooks', 'bot_status')
                if bot_status == 'maintenance':
                    send_dm(message['sender_id'], "The tip bot is in maintenance.  Check @NanoTipBot on Twitter for more information.", message['system'])
                else:
                    donate_process(message)
            except Exception as e:
                logging.info("Exception: {}".format(e))
                raise e
            os._exit(0)
        else:
            return '', HTTPStatus.OK

    elif message['dm_action'] in account_commands:
        new_pid = os.fork()
        if new_pid == 0:
            try:
                account_process(message)
            except Exception as e:
                logging.info("Exception: {}".format(e))
                raise e
            os._exit(0)
        else:
            return '', HTTPStatus.OK

    elif message['dm_action'] in private_tip_commands:
        new_pid = os.fork()
        if new_pid == 0:
            try:
                redirect_tip_text = ("Private Tip is under maintenance.  To send your tip, use the !tip function in a "
                                     "tweet or reply!")
                send_dm(message['sender_id'], redirect_tip_text, message['system'])
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
                wrong_format_text = ("The command or syntax you sent is not recognized.  Please send !help for a list "
                                     "of commands and what they do.")
                send_dm(message['sender_id'], wrong_format_text, message['system'])
                logging.info('unrecognized syntax')
            except Exception as e:
                logging.info("Exception: {}".format(e))
                raise e
            os._exit(0)
        else:
            return '', HTTPStatus.OK

    return '', HTTPStatus.OK


def help_process(message):
    """
    Reply to the sender with help commands
    """
    help_message = (
            "Thank you for using the Nano Tip Bot!  Below is a list of commands, and a description of what they do:\n\n"
            + BULLET + " !help: The tip bot will respond to your DM with a list of commands and their functions. If you"
                       " forget something, use this to get a hint of how to do it!\n\n"
            + BULLET + " !register: Registers your user ID for an account that is tied to it.  This is used to store"
                       " your tips. Make sure to withdraw to a private wallet, as the tip bot is not meant to be a "
                       "long term storage device for Nano.\n\n"
            + BULLET + " !balance: This returns the balance of the account linked with your user ID.\n\n"
            + BULLET + " !tip: Tips are sent through public tweets or in Telegram groups.\n"
                       " On Twitter: Tag @NanoTipBot in a tweet and mention !tip <amount> <@username>.  "
                       "Example: @NanoTipBot !tip 1 @mitche50 would send a 1 Nano tip to user @mitche50.\n"
                       " On Telegram send !tip <amount> <@username> to tip in the group.\n\n"
            + BULLET + " !privatetip: Currently disabled.  This will send a tip to another user through DM.  If you "
                       "would like your tip amount to be private, use this function!  Proper usage is !privatetip "
                       "@username 1234\n\n"
            + BULLET + " !account: Returns the account number that is tied to your user ID (currently unique to "
                       "platform).  You can use this to deposit more Nano to tip from your personal wallet.\n\n"
            + BULLET + " !withdraw: Proper usage is !withdraw xrb_12345.  This will send the full balance of your tip "
                       "account to the provided Nano account.  Optional: You can include an amount to withdraw by "
                       "sending !withdraw <amount> <address>.  Example: !withdraw 1 xrb_iaoia83if221lodoepq would "
                       "withdraw 1 NANO to account xrb_iaoia83if221lodoepq.\n\n"
            + BULLET + " !donate: Proper usage is !donate 1234.  This will send the requested donation to the Nano Tip "
                       "Bot donation account to help fund development efforts."
    )
    send_dm(message['sender_id'], help_message, message['system'])
    logging.info("{}: Help message sent!".format(datetime.now()))


def balance_process(message):
    """
    When the user sends a DM containing !balance, reply with the balance of the account linked with their Twitter ID
    """
    logging.info("{}: In balance process".format(datetime.now()))
    balance_call = ("SELECT account, register FROM users WHERE user_id = {} "
                    "AND system = '{}'".format(message['sender_id'], message['system']))
    data = get_db_data(balance_call)
    if not data:
        logging.info("{}: User tried to check balance without an account".format(datetime.now()))
        balance_message = ("There is no account linked to your username.  Please respond with !register to "
                           "create an account.")
        send_dm(message['sender_id'], balance_message, message['system'])
    else:
        message['sender_account'] = data[0][0]
        sender_register = data[0][1]

        if sender_register == 0:
            set_register_call = "UPDATE users SET register = 1 WHERE user_id = %s AND system = %s AND register = 0"
            set_register_values = [message['sender_id'], message['system']]
            err = set_db_data(set_register_call, set_register_values)

        receive_pending(message['sender_account'])

        balance_return = rpc.account_balance(account="{}".format(message['sender_account']))
        message['sender_balance_raw'] = balance_return['balance']
        message['sender_pending_raw'] = balance_return['pending']
        message['sender_balance'] = balance_return['balance'] / 1000000000000000000000000000000
        message['sender_pending'] = balance_return['pending'] / 1000000000000000000000000000000
        if message['sender_balance'] == 0 and message['sender_pending'] == 0:
            balance_text = "Your balance is 0 NANO."
        elif message['sender_balance'] == 0 and message['sender_pending'] > 0:
            balance_text = "Available: 0 NANO\n" \
                           "Pending: {} NANO".format(message['sender_pending'])
        elif message['sender_balance'] > 0 and message['sender_pending'] == 0:
            balance_text = "Available: {} NANO\n" \
                           "Pending: 0 NANO".format(message['sender_balance'])
        else:
            balance_text = "Available: {} NANO\n" \
                           "Pending: {} NANO".format(message['sender_balance'], message['sender_pending'])
        send_dm(message['sender_id'], balance_text, message['system'])
        logging.info("{}: Balance Message Sent!".format(datetime.now()))
        receive_pending(message['sender_account'])


def register_process(message):
    """
    When the user sends !register, create an account for them and mark it registered.  If they already have an account
    reply with their account number.
    """
    logging.info("{}: In register process.".format(datetime.now()))
    register_call = ("SELECT account, register FROM users WHERE user_id = {} AND system = '{}'"
                     .format(message['sender_id'], message['system']))
    data = get_db_data(register_call)

    if not data:
        # Create an account for the user
        sender_account = rpc.account_create(wallet="{}".format(WALLET), work=False)
        account_create_call = ("INSERT INTO users (user_id, system, user_name, account, register) "
                               "VALUES(%s, %s, %s, %s, 1)")
        account_create_values = [message['sender_id'], message['system'], message['sender_screen_name'], sender_account]
        err = set_db_data(account_create_call, account_create_values)

        account_text = "You have successfully registered for an account.  Your account number is:"
        send_account_message(account_text, message, sender_account)

        logging.info("{}: Register successful!".format(datetime.now()))

    elif data[0][1] == 0:
        # The user has an account, but needed to register, so send a message to the user with their account
        sender_account = data[0][0]
        account_registration_update = "UPDATE users SET register = 1 WHERE user_id = %s AND register = 0"
        account_registration_values = [message['sender_id'],]
        err = set_db_data(account_registration_update, account_registration_values)

        account_registration_text = "You have successfully registered for an account.  Your account number is:"
        send_account_message(account_registration_text, message, sender_account)

        logging.info("{}: User has an account, but needed to register.  Message sent".format(datetime.now()))

    else:
        # The user had an account and already registered, so let them know their account.
        sender_account = data[0][0]
        account_already_registered = "You already have registered your account.  Your account number is:"
        send_account_message(account_already_registered, message, sender_account)

        logging.info("{}: User has a registered account.  Message sent.".format(datetime.now()))


def account_process(message):
    """
    If the user sends !account command, reply with their account.  If there is no account, create one, register it
    and reply to the user.
    """
    logging.info("{}: In account process.".format(datetime.now()))
    sender_account_call = (
        "SELECT account, register FROM users WHERE user_id = {} AND system = '{}'".format(message['sender_id'],
                                                                                          message['system']))
    account_data = get_db_data(sender_account_call)
    if not account_data:
        logging.info("Creating account using wallet: {}".format(WALLET))
        sender_account = rpc.account_create(wallet="{}".format(WALLET), work=True)
        account_create_call = ("INSERT INTO users (user_id, system, user_name, account, register) "
                               "VALUES(%s, %s, %s, %s, 1)")
        account_create_values = [message['sender_id'], message['system'], message['sender_screen_name'], sender_account]
        err = set_db_data(account_create_call, account_create_values)

        account_text = "You didn't have an account set up, so I set one up for you.  Your account number is:"
        send_account_message(account_text, message, sender_account)

        logging.info("{}: Created an account for the user!".format(datetime.now()))

    else:
        sender_account = account_data[0][0]
        sender_register = account_data[0][1]

        if sender_register == 0:
            set_register_call = (
                "UPDATE users SET register = 1 WHERE user_id = %s AND system = %s AND register = 0")
            set_register_values = [message['sender_id'], message['system']]
            err = set_db_data(set_register_call, set_register_values)

        account_text = "Your account number is:"
        send_account_message(account_text, message, sender_account)

        logging.info("{}: Sent the user their account number.".format(datetime.now()))


def withdraw_process(message):
    """
    When the user sends !withdraw, send their entire balance to the provided account.  If there is no provided account
    reply with an error.
    """
    logging.info('{}: in withdraw process.'.format(datetime.now()))
    # check if there is a 2nd argument
    if 3 >= len(message['dm_array']) >= 2:
        # if there is, retrieve the sender's account and wallet
        withdraw_account_call = ("SELECT account FROM users WHERE user_id = {} AND system = '{}'"
                                 .format(message['sender_id'], message['system']))
        withdraw_data = get_db_data(withdraw_account_call)

        if not withdraw_data:
            withdraw_no_account_text = "You do not have an account.  Respond with !register to set one up."
            send_dm(message['sender_id'], withdraw_no_account_text, message['system'])
            logging.info("{}: User tried to withdraw with no account".format(datetime.now()))

        else:
            sender_account = withdraw_data[0][0]
            receive_pending(sender_account)
            balance_return = rpc.account_balance(account='{}'.format(sender_account))

            if len(message['dm_array']) == 2:
                receiver_account = message['dm_array'][1].lower()
            else:
                receiver_account = message['dm_array'][2].lower()

            if rpc.validate_account_number(receiver_account) == 0:
                invalid_account_text = ("The account number you provided is invalid.  Please double check and "
                                        "resend your request.")
                send_dm(message['sender_id'], invalid_account_text, message['system'])
                logging.info("{}: The xrb account number is invalid: {}".format(datetime.now(), receiver_account))

            elif balance_return['balance'] == 0:
                no_balance_text = ("You have 0 balance in your account.  Please deposit to your address {} to "
                                   "send more tips!".format(sender_account))
                send_dm(message['sender_id'], no_balance_text, message['system'])
                logging.info("{}: The user tried to withdraw with 0 balance".format(datetime.now()))

            else:
                if len(message['dm_array']) == 3:
                    try:
                        withdraw_amount = Decimal(message['dm_array'][1])
                    except Exception as e:
                        logging.info("{}: withdraw no number ERROR: {}".format(datetime.now(), e))
                        invalid_amount_text = ("You did not send a number to withdraw.  Please resend with the format"
                                               "!withdraw <account> or !withdraw <amount> <account>")
                        send_dm(message['sender_id'], invalid_amount_text, message['system'])
                        return
                    withdraw_amount_raw = int(withdraw_amount * 1000000000000000000000000000000)
                    if Decimal(withdraw_amount_raw) > Decimal(balance_return['balance']):
                        not_enough_balance_text = ("You do not have that much NANO in your account.  To withdraw your "
                                                   "full amount, send !withdraw <account>")
                        send_dm(message['sender_id'], not_enough_balance_text, message['system'])
                        return
                else:
                    withdraw_amount_raw = balance_return['balance']
                    withdraw_amount = balance_return['balance'] / 1000000000000000000000000000000
                # send the total balance to the provided account
                work = get_pow(sender_account)
                if work == '':
                    logging.info("{}: processed without work".format(datetime.now()))
                    send_hash = rpc.send(wallet="{}".format(WALLET), source="{}".format(sender_account),
                                         destination="{}".format(receiver_account), amount=withdraw_amount_raw)
                else:
                    logging.info("{}: processed with work: {} using wallet: {}".format(datetime.now(), work, WALLET))
                    send_hash = rpc.send(wallet="{}".format(WALLET), source="{}".format(sender_account),
                                         destination="{}".format(receiver_account), amount=withdraw_amount_raw,
                                         work=work)
                logging.info("{}: send_hash = {}".format(datetime.now(), send_hash))
                # respond that the withdraw has been processed
                withdraw_text = ("You have successfully withdrawn {} NANO!  You can check the "
                                 "transaction at https://nanocrawler.cc/explorer/block/{}"
                                 .format(withdraw_amount, send_hash))
                send_dm(message['sender_id'], withdraw_text, message['system'])
                logging.info("{}: Withdraw processed.  Hash: {}".format(datetime.now(), send_hash))
    else:
        incorrect_withdraw_text = ("I didn't understand your withdraw request.  Please resend with !withdraw "
                                   "<optional:amount> <account>.  Example, !withdraw 1 xrb_aigakjkfa343tm3h1kj would "
                                   "withdraw 1 NANO to account xrb_aigakjkfa343tm3h1kj.  Also, !withdraw "
                                   "xrb_aigakjkfa343tm3h1kj would withdraw your entire balance to account "
                                   "xrb_aigakjkfa343tm3h1kj.")
        send_dm(message['sender_id'], incorrect_withdraw_text, message['system'])
        logging.info("{}: User sent a withdraw with invalid syntax.".format(datetime.now()))


def donate_process(message):
    """
    When the user sends !donate, send the provided amount from the user's account to the tip bot's donation wallet.
    If the user has no balance or account, reply with an error.
    """
    logging.info("{}: in donate_process.".format(datetime.now()))

    if len(message['dm_array']) >= 2:
        sender_account_call = (
            "SELECT account FROM users where user_id = {} and system = '{}'".format(message['sender_id'],
                                                                                    message['system']))
        donate_data = get_db_data(sender_account_call)
        sender_account = donate_data[0][0]
        send_amount = message['dm_array'][1]

        receive_pending(sender_account)

        balance_return = rpc.account_balance(account='{}'.format(sender_account))
        balance = balance_return['balance'] / 1000000000000000000000000000000
        receiver_account = BOT_ACCOUNT

        try:
            logging.info("{}: The user is donating {} NANO".format(datetime.now(), Decimal(send_amount)))
        except Exception as e:
            logging.info("{}: ERROR IN CONVERTING DONATION AMOUNT: {}".format(datetime.now(), e))
            wrong_donate_text = "Only number amounts are accepted.  Please resend as !donate 1234"
            send_dm(message['sender_id'], wrong_donate_text, message['system'])
            return ''
        logging.info("balance: {} - send_amount: {}".format(Decimal(balance), Decimal(send_amount)))
        if Decimal(balance) < Decimal(send_amount):
            large_donate_text = ("Your balance is only {} NANO and you tried to send {}.  Please add more NANO"
                                 " to your account, or lower your donation amount.".format(balance,
                                                                                           Decimal(send_amount)))
            send_dm(message['sender_id'], large_donate_text, message['system'])
            logging.info("{}: User tried to donate more than their balance.".format(datetime.now()))

        elif Decimal(send_amount) < Decimal(MIN_TIP):
            small_donate_text = ("The minimum donation amount is {}.  Please update your donation amount "
                                 "and resend.".format(MIN_TIP))
            send_dm(message['sender_id'], small_donate_text, message['system'])
            logging.info("{}: User tried to donate less than 0.000001".format(datetime.now()))

        else:
            send_amount_raw = Decimal(send_amount) * 1000000000000000000000000000000
            work = get_pow(sender_account)
            if work == '':
                logging.info("{}: Processing donation without work.".format(datetime.now()))
                send_hash = rpc.send(wallet="{}".format(WALLET), source="{}".format(sender_account),
                                     destination="{}".format(receiver_account), amount="{:f}".format(send_amount_raw))
            else:
                logging.info("{}: Processing donation with work: {}".format(datetime.now(), work))
                send_hash = rpc.send(wallet="{}".format(WALLET), source="{}".format(sender_account),
                                     destination="{}".format(receiver_account), amount="{:f}".format(send_amount_raw),
                                     work=work)

            logging.info("{}: send_hash = {}".format(datetime.now(), send_hash))

            donate_text = ("Thank you for your generosity!  You have successfully donated {} NANO!  You can check the "
                           "transaction at https://nanocrawler.cc/explorer/block/{}".format(send_amount, send_hash))
            send_dm(message['sender_id'], donate_text, message['system'])
            logging.info("{}: {} NANO donation processed.  Hash: {}".format(datetime.now(), Decimal(send_amount),
                                                                            send_hash))

    else:
        incorrect_donate_text = "Incorrect syntax.  Please use the format !donate 1234"
        send_dm(message['sender_id'], incorrect_donate_text, message['system'])
        logging.info("{}: User sent a donation with invalid syntax".format(datetime.now()))


def tip_process(message, users_to_tip, request_json):
    """
    Main orchestration process to handle tips
    """
    logging.info("{}: in tip_process".format(datetime.now()))

    # tips_suspended_text = "Tips have been temporarily suspended.  Please follow @NanoTipBot on Twitter for any updates."
    # send_dm(message['sender_id'], tips_suspended_text, message['system'])
    # return

    message, users_to_tip = set_tip_list(message, users_to_tip, request_json)
    if len(users_to_tip) < 1 and message['system'] != 'telegram':
        no_users_text = ("Looks like you didn't enter in anyone to tip, or you mistyped someone's handle.  You can try "
                         "to tip again using the format !tip 1234 @username")
        send_reply(message, no_users_text)
        return

    message = validate_sender(message)
    if message['sender_account'] is None or message['tip_amount'] <= 0:
        return

    message = validate_total_tip_amount(message)
    if message['tip_amount'] <= 0:
        return

    for t_index in range(0, len(users_to_tip)):
        send_tip(message, users_to_tip, t_index)

    # Inform the user that all tips were sent.
    if len(users_to_tip) >= 2:
        multi_tip_success = ("You have successfully sent your {} $NANO tips.  Check your account at "
                             "https://nanocrawler.cc/explorer/account/{}".format(message['tip_amount_text'],
                                                                                 message['sender_account']))
        send_reply(message, multi_tip_success)

    elif len(users_to_tip) == 1:
        tip_success = ("You have successfully sent your {} $NANO tip.  Check your account at "
                       "https://nanocrawler.cc/explorer/account/{}".format(message['tip_amount_text'],
                                                                           message['sender_account']))
        send_reply(message, tip_success)
