import configparser
import json
import logging
import os
import requests
from datetime import datetime
from decimal import Decimal
from http import HTTPStatus
from logging.handlers import TimedRotatingFileHandler

import nano

import modules.currency
import modules.db
import modules.social
import modules.translations as translations

# Set logging info
logger = logging.getLogger("orchestration_log")
logger.setLevel(logging.INFO)
handler = TimedRotatingFileHandler('{}/logs/{:%Y-%m-%d}-orchestration.log'.format(os.getcwd(), datetime.now()),
                                   when="d",
                                   interval=1,
                                   backupCount=5)
logger.addHandler(handler)

# Read config and parse constants
config = configparser.ConfigParser()
config.read('{}/webhookconfig.ini'.format(os.getcwd()))

# Check the currency of the bot
CURRENCY = config.get('main', 'currency')

# Set constants
BULLET = u"\u2022"
NODE_IP = config.get(CURRENCY, 'node_ip')
WALLET = config.get(CURRENCY, 'wallet')
BOT_ID_TWITTER = config.get(CURRENCY, 'bot_id_twitter')
BOT_NAME_TWITTER = config.get(CURRENCY, 'bot_name_twitter')
BOT_NAME_TELEGRAM = config.get(CURRENCY, 'bot_name_telegram')
BOT_ACCOUNT = config.get(CURRENCY, 'bot_account')
MIN_TIP = config.get(CURRENCY, 'min_tip')
EXPLORER = config.get('routes', '{}_explorer'.format(CURRENCY))
CONVERT_MULTIPLIER = {
    'nano': 1000000000000000000000000000000,
    'banano': 100000000000000000000000000000
}

# Connect to global functions
rpc = nano.rpc.Client(NODE_IP)


def parse_action(message):
    # If the bot is in maintenance status, send a message and return.
    try:
        bot_status = config.get('main', 'bot_status')
        if bot_status == 'maintenance':
            modules.social.send_dm(message['sender_id'],
                                translations.maintenance_text[message['language']].format(BOT_NAME_TWITTER),
                                message['system'])
            return ''
        elif message['system'] == 'twitter' and bot_status == 'twitter-maintenance':
            modules.social.send_dm(message['sender_id'],
                                translations.maintenance_text[message['language']].format(BOT_NAME_TWITTER),
                                message['system'])
            return ''
        elif message['system'] == 'telegram' and bot_status == 'telegram-maintenance':
            modules.social.send_dm(message['sender_id'],
                                translations.maintenance_text[message['language']].format(BOT_NAME_TWITTER),
                                message['system'])
            return ''
        # Set tip commands
        if CURRENCY == 'banano':
            tip_commands = modules.translations.banano_tip_commands['en']
        else:
            tip_commands = modules.translations.nano_tip_commands[message['language']]
            logger.info("language: {}".format(message['language']))
            if message['language'] != 'en':
                english_commands = modules.translations.nano_tip_commands['en']
                for command in english_commands:
                    logger.info("commad: {}".format(command))
                    tip_commands.append(command)

        logger.info('tip commands: {}'.format(tip_commands))

        if message['dm_action'] in translations.help_commands['en'] or \
                message['dm_action'] in translations.help_commands[message['language']]:
            new_pid = os.fork()
            if new_pid == 0:
                try:
                    help_process(message)
                except Exception as e:
                    logger.info("Exception: {}".format(e))
                    raise e
                os._exit(0)
            else:
                return '', HTTPStatus.OK

        if message['dm_action'] in translations.set_mute_commands['en'] or \
                message['dm_action'] in translations.set_mute_commands[message['language']]:
            new_pid = os.fork()
            if new_pid == 0:
                try:
                    mute_process(message, 1)
                except Exception as e:
                    logger.info("Exception: {}".format(e))
                    raise e
                os._exit(0)
            else:
                return '', HTTPStatus.OK

        if message['dm_action'] in translations.set_unmute_commands['en'] or \
                message['dm_action'] in translations.set_unmute_commands[message['language']]:
            new_pid = os.fork()
            if new_pid == 0:
                try:
                    mute_process(message, 0)
                except Exception as e:
                    logger.info("Exception: {}".format(e))
                    raise e
                os._exit(0)
            else:
                return '', HTTPStatus.OK

        elif message['dm_action'] in translations.balance_commands['en'] or \
                message['dm_action'] in translations.balance_commands[message['language']]:
            new_pid = os.fork()
            if new_pid == 0:
                try:
                    balance_process(message)
                except Exception as e:
                    logger.info("Exception: {}".format(e))
                    raise e
                os._exit(0)
            else:
                return '', HTTPStatus.OK

        elif message['dm_action'] in translations.register_commands['en'] or \
                message['dm_action'] in translations.register_commands[message['language']]:
            new_pid = os.fork()
            if new_pid == 0:
                try:
                    register_process(message)
                except Exception as e:
                    logger.info("Exception: {}".format(e))
                    raise e
                os._exit(0)
            else:
                return '', HTTPStatus.OK

        elif message['dm_action'] in tip_commands:
            new_pid = os.fork()
            if new_pid == 0:
                try:
                    modules.social.send_dm(message['sender_id'],
                                        translations.redirect_tip_text[message['language']].format(BOT_NAME_TWITTER,
                                                                                                    tip_commands[0]),
                                        message['system'])
                except Exception as e:
                    logger.info("Exception: {}".format(e))
                    raise e
                os._exit(0)
            else:
                return '', HTTPStatus.OK

        elif message['dm_action'] in translations.withdraw_commands['en'] or \
                message['dm_action'] in translations.withdraw_commands[message['language']]:
            new_pid = os.fork()
            if new_pid == 0:
                try:
                    withdraw_process(message)
                except Exception as e:
                    logger.info("Exception: {}".format(e))
                    raise e
                os._exit(0)
            else:
                return '', HTTPStatus.OK

        elif message['dm_action'] in translations.donate_commands['en'] or \
                message['dm_action'] in translations.donate_commands[message['language']]:
            new_pid = os.fork()
            if new_pid == 0:
                try:
                    donate_process(message)
                except Exception as e:
                    logger.info("Exception: {}".format(e))
                    raise e
                os._exit(0)
            else:
                return '', HTTPStatus.OK

        elif message['dm_action'] in translations.account_commands['en'] or \
                message['dm_action'] in translations.account_commands[message['language']]:
            new_pid = os.fork()
            if new_pid == 0:
                try:
                    account_process(message)
                except Exception as e:
                    logger.info("Exception: {}".format(e))
                    raise e
                os._exit(0)
            else:
                return '', HTTPStatus.OK

        elif message['dm_action'] in translations.private_tip_commands['en'] or \
                message['dm_action'] in translations.private_tip_commands[message['language']]:
            new_pid = os.fork()
            if new_pid == 0:
                try:
                    if CURRENCY == 'banano':
                        tip_command = modules.translations.banano_tip_commands['en'][0]
                    else:
                        if len(modules.translations.nano_tip_commands[message['language']]) > 0:
                            tip_command = modules.translations.nano_tip_commands[message['language']][0]
                        else:
                            tip_command = modules.translations.nano_tip_commands['en'][0]

                    modules.social.send_dm(message['sender_id'],
                                        translations.private_tip_text[message['language']].format(tip_command),
                                        message['system'])
                except Exception as e:
                    logger.info("Exception: {}".format(e))
                    raise e
                os._exit(0)
            else:
                return '', HTTPStatus.OK

        elif message['dm_action'] in translations.language_commands:
            new_pid = os.fork()
            if new_pid == 0:
                try:
                    try:
                        new_language = message['text'].split(' ')[1].lower()
                        if new_language == 'chinese':
                            new_language += ' ' + message['text'].split(' ')[2].lower()
                        language_process(message, new_language)
                    except Exception as f:
                        logger.info("{}: Error in language process: {}".format(datetime.now(), f))
                        modules.social.send_dm(message['sender_id'], translations.missing_language[message['language']],
                                            message['system'])
                except Exception as e:
                    logger.info("Exception: {}".format(e))
                    raise e
                os._exit(0)
            else:
                return '', HTTPStatus.OK

        elif message['dm_action'] in translations.language_list_commands:
            new_pid = os.fork()
            if new_pid == 0:
                try:
                    language_list_process(message)
                except Exception as e:
                    logger.info("Exception: {}".format(e))
                    raise e
                os._exit(0)
            else:
                return '', HTTPStatus.OK

        elif message['dm_action'] in translations.auto_donate_commands['en'] or \
                message['dm_action'] in translations.auto_donate_commands[message['language']]:
            logger.info("auto donate command identified")
            new_pid = os.fork()
            if new_pid == 0:
                try:
                    auto_donation_process(message)
                except Exception as e:
                    logger.info(
                        "{}: Exception in auto_donate_commands section of parse_action: {}".format(datetime.now(), e))
                os._exit(0)
            else:
                return '', HTTPStatus.OK

        elif message['dm_action'] in translations.set_return_commands['en'] or \
                message['dm_action'] in translations.set_return_commands[message['language']]:
            logger.info("set return address command identified")
            new_pid = os.fork()
            if new_pid == 0:
                try:
                    set_return_address_process(message)
                except Exception as e:
                    logger.info(
                        "{}: Exception in set_return_address_process section of parse_action: {}".format(datetime.now(), e))
                os._exit(0)
            else:
                return '', HTTPStatus.OK

        else:
            new_pid = os.fork()
            if new_pid == 0:
                try:
                    modules.social.send_dm(message['sender_id'], translations.wrong_format_text[message['language']],
                                        message['system'])
                    logger.info('unrecognized syntax')
                except Exception as e:
                    logger.info("Exception: {}".format(e))
                    raise e
                os._exit(0)
            else:
                return '', HTTPStatus.OK
    except Exception as e:
        logger.info("{}: Error identified: {}".format(datetime.now, e))
    return '', HTTPStatus.OK


def help_process(message):
    """
    Reply to the sender with help commands
    """
    if CURRENCY == 'banano':
        tip_command = modules.translations.banano_tip_commands['en'][0]
    else:
        if len(modules.translations.nano_tip_commands[message['language']]) > 0:
            tip_command = modules.translations.nano_tip_commands[message['language']][0]
        else:
            tip_command = modules.translations.nano_tip_commands['en'][0]

    modules.social.send_dm(message['sender_id'],
                           translations.help_message[message['language']].format(CURRENCY.title(),
                                                                                 BOT_NAME_TWITTER,
                                                                                 BOT_ACCOUNT,
                                                                                 BOT_NAME_TELEGRAM,
                                                                                 tip_command),
                           message['system'])
    logger.info("{}: Help message sent!".format(datetime.now()))


def auto_donation_process(message):
    """
    Update the donation percentage on returned tips.
    """
    logger.info("{}: Updating auto donation percentage".format(datetime.now()))
    message['text'] = message['text'].split(' ')
    logger.info(len(message['text']) >= 2)
    logger.info(message['text'])
    logger.info(message['text'][1])
    if len(message['text']) >= 2:
        try:
            logger.info(message['text'][1])
            new_percent = float(message['text'][1])
        except ValueError:
            # send a message that the new percentage is not a number
            modules.social.send_dm(message['sender_id'],
                                   translations.auto_donate_notanum[message['language']],
                                   message['system'])
            return ''
        if 0 <= new_percent <= 100:
            # update the donation percentage
            auto_donate_call = ("UPDATE donation_info SET donation_percent = %s "
                                "WHERE user_id = %s AND system = %s ")
            auto_donate_values = [int(new_percent), message['sender_id'], message['system']]
            modules.db.set_db_data(auto_donate_call, auto_donate_values)
            modules.social.send_dm(message['sender_id'],
                                   translations.auto_donate_success[message['language']].format(int(new_percent)),
                                   message['system'])

        else:
            # send a message that the new percentage must be greater than or equal to zero, but less than or equal to 100
            modules.social.send_dm(message['sender_id'],
                                   translations.auto_donate_negative[message['language']],
                                   message['system'])

    else:
        # send a message that they didn't include a new percent to update to
        modules.social.send_dm(message['sender_id'],
                               translations.auto_donate_missing_num[message['language']],
                               message['system'])


def mute_process(message, mute_value):
    """
    Update user's mute preferences to prevent or resume messaging / replies.
    """
    logger.info("{}: in mute process".format(datetime.now()))
    account_check_call = ("SELECT mute FROM users WHERE user_id = {} AND users.system = '{}'"
                          .format(message['sender_id'], message['system']))
    data = modules.db.get_db_data(account_check_call)
    if not data:
        # Create an account for the user
        sender_account = modules.db.get_spare_account()
        account_create_call = ("INSERT INTO users (user_id, system, user_name, account, register, mute) "
                               "VALUES(%s, %s, %s, %s, 1, %s)")
        account_create_values = [message['sender_id'], message['system'], message['sender_screen_name'], sender_account, mute_value]
        modules.db.set_db_data(account_create_call, account_create_values)
    else:
        mute_call = ("UPDATE users SET mute = %s WHERE user_id = %s AND system = %s")
        mute_values = [mute_value, message['sender_id'], message['system']]
        modules.db.set_db_data(mute_call, mute_values)
    
    if mute_value == 1:
        modules.social.send_dm(message['sender_id'], translations.mute[message['language']], message['system'])
    else:
        modules.social.send_dm(message['sender_id'], translations.unmute[message['language']], message['system'])


def balance_process(message):
    """
    When the user sends a DM containing !balance, reply with the balance of the account linked with their Twitter ID
    """
    logger.info("{}: In balance process".format(datetime.now()))
    balance_call = ("SELECT account, register FROM users WHERE user_id = {} "
                    "AND users.system = '{}'".format(message['sender_id'], message['system']))
    data = modules.db.get_db_data(balance_call)
    if not data:
        logger.info("{}: User tried to check balance without an account".format(datetime.now()))
        modules.social.send_dm(message['sender_id'], translations.no_account_text['language'], message['system'])
    else:
        message['sender_account'] = data[0][0]
        sender_register = data[0][1]

        if sender_register == 0:
            set_register_call = "UPDATE users SET register = 1 WHERE user_id = %s AND users.system = %s AND register = 0"
            set_register_values = [message['sender_id'], message['system']]
            modules.db.set_db_data(set_register_call, set_register_values)
        new_pid = os.fork()
        if new_pid == 0:
            modules.currency.receive_pending(message['sender_account'])
            os._exit(0)
        else:
            balance_return = rpc.account_balance(account="{}".format(message['sender_account']))
            message['sender_balance_raw'] = balance_return['balance']
            message['sender_pending_raw'] = balance_return['pending']
            message['sender_balance'] = balance_return['balance'] / CONVERT_MULTIPLIER[CURRENCY]
            message['sender_pending'] = balance_return['pending'] / CONVERT_MULTIPLIER[CURRENCY]

            modules.social.send_dm(message['sender_id'], translations.balance_text[message['language']]
                                   .format(message['sender_balance'],
                                           CURRENCY.upper(),
                                           message['sender_pending'],
                                           CURRENCY.upper()),
                                   message['system'])
            logger.info("{}: Balance Message Sent!".format(datetime.now()))
            return ''


def register_process(message):
    """
    When the user sends !register, create an account for them and mark it registered.  If they already have an account
    reply with their account number.
    """
    logger.info("{}: In register process.".format(datetime.now()))
    register_call = ("SELECT account, register FROM users WHERE user_id = {} AND users.system = '{}'"
                     .format(message['sender_id'], message['system']))
    data = modules.db.get_db_data(register_call)

    if not data:
        # Create an account for the user
        sender_account = modules.db.get_spare_account()
        account_create_call = ("INSERT INTO users (user_id, system, user_name, account, register) "
                               "VALUES(%s, %s, %s, %s, 1)")
        account_create_values = [message['sender_id'], message['system'], message['sender_screen_name'], sender_account]
        modules.db.set_db_data(account_create_call, account_create_values)
        try:
            account_register_text = translations.account_register_text[message['language']]
            modules.social.send_account_message(account_register_text, message, sender_account)
        except KeyError:
            account_register_text = "You did not have an account before you set your language.  I have created " \
                                    "an account for you:"
            modules.social.send_account_message(account_register_text, message, sender_account)

        logger.info("{}: Register successful!".format(datetime.now()))

    elif data[0][1] == 0:
        # The user has an account, but needed to register, so send a message to the user with their account
        sender_account = data[0][0]
        account_registration_update = "UPDATE users SET register = 1 WHERE user_id = %s AND register = 0"
        account_registration_values = [message['sender_id'], ]
        modules.db.set_db_data(account_registration_update, account_registration_values)

        account_register_text = translations.account_register_text[message['language']]
        modules.social.send_account_message(account_register_text, message, sender_account)

        logger.info("{}: User has an account, but needed to register.  Message sent".format(datetime.now()))

    else:
        # The user had an account and already registered, so let them know their account.
        sender_account = data[0][0]
        account_already_registered = translations.account_already_registered[message['language']]
        modules.social.send_account_message(account_already_registered, message, sender_account)

        logger.info("{}: User has a registered account.  Message sent.".format(datetime.now()))


def account_process(message):
    """
    If the user sends !account command, reply with their account.  If there is no account, create one, register it
    and reply to the user.
    """
    logger.info("{}: In account process.".format(datetime.now()))
    sender_account_call = (
        "SELECT account, register FROM users WHERE user_id = {} AND users.system = '{}'".format(message['sender_id'],
                                                                                                message['system']))
    account_data = modules.db.get_db_data(sender_account_call)
    if not account_data:
        sender_account = modules.db.get_spare_account()
        account_create_call = ("INSERT INTO users (user_id, system, user_name, account, register) "
                               "VALUES(%s, %s, %s, %s, 1)")
        account_create_values = [message['sender_id'], message['system'], message['sender_screen_name'], sender_account]
        modules.db.set_db_data(account_create_call, account_create_values)

        account_create_text = translations.account_create_text[message['language']]
        modules.social.send_account_message(account_create_text, message, sender_account)

        logger.info("{}: Created an account for the user!".format(datetime.now()))

    else:
        sender_account = account_data[0][0]
        sender_register = account_data[0][1]

        if sender_register == 0:
            set_register_call = (
                "UPDATE users SET register = 1 WHERE user_id = %s AND users.system = %s AND register = 0")
            set_register_values = [message['sender_id'], message['system']]
            modules.db.set_db_data(set_register_call, set_register_values)

        account_text = translations.account_text[message['language']]
        modules.social.send_account_message(account_text, message, sender_account)

        logger.info("{}: Sent the user their account number.".format(datetime.now()))


def withdraw_process(message):
    """
    When the user sends !withdraw, send their entire balance to the provided account.  If there is no provided account
    reply with an error.
    """
    logger.info('{}: in withdraw process.'.format(datetime.now()))
    # check if there is a 2nd argument
    if 3 >= len(message['dm_array']) >= 2:
        # if there is, retrieve the sender's account and wallet
        withdraw_account_call = ("SELECT account, register FROM users WHERE user_id = {} AND users.system = '{}'"
                                 .format(message['sender_id'], message['system']))
        withdraw_data = modules.db.get_db_data(withdraw_account_call)

        if not withdraw_data:

            modules.social.send_dm(message['sender_id'], translations.no_account_text[message['language']],
                                   message['system'])
            logger.info("{}: User tried to withdraw with no account".format(datetime.now()))

        else:
            sender_account = withdraw_data[0][0]
            sender_register = withdraw_data[0][1]

            if sender_register == 0:
                set_register_call = (
                    "UPDATE users SET register = 1 WHERE user_id = %s AND users.system = %s AND register = 0")
                set_register_values = [message['sender_id'], message['system']]
                modules.db.set_db_data(set_register_call, set_register_values)

            modules.currency.receive_pending(sender_account)
            balance_return = rpc.account_balance(account='{}'.format(sender_account))

            if len(message['dm_array']) == 2:
                receiver_account = message['dm_array'][1].lower()
            else:
                receiver_account = message['dm_array'][2].lower()

            if rpc.validate_account_number(receiver_account) == 0:
                modules.social.send_dm(message['sender_id'], translations.invalid_account_text[message['language']],
                                       message['system'])
                logger.info("{}: The xrb account number is invalid: {}".format(datetime.now(), receiver_account))

            elif balance_return['balance'] == 0:
                modules.social.send_dm(message['sender_id'], translations.no_balance_text[message['language']]
                                       .format(sender_account), message['system'])
                logger.info("{}: The user tried to withdraw with 0 balance".format(datetime.now()))

            else:
                if len(message['dm_array']) == 3:
                    try:
                        withdraw_amount = Decimal(message['dm_array'][1])
                    except Exception as e:
                        logger.info("{}: withdraw no number ERROR: {}".format(datetime.now(), e))
                        modules.social.send_dm(message['sender_id'],
                                               translations.invalid_amount_text[message['language']],
                                               message['system'])
                        return
                    withdraw_amount_raw = int(withdraw_amount * CONVERT_MULTIPLIER[CURRENCY])
                    if Decimal(withdraw_amount_raw) > Decimal(balance_return['balance']):
                        modules.social.send_dm(message['sender_id'],
                                               translations.not_enough_balance_text[message['language']].format(
                                                   CURRENCY),
                                               message['system'])
                        return
                else:
                    withdraw_amount_raw = balance_return['balance']
                    withdraw_amount = balance_return['balance'] / CONVERT_MULTIPLIER[CURRENCY]
                # send the total balance to the provided account
                work = modules.currency.get_pow(sender_account)
                if work == '':
                    logger.info("{}: processed without work".format(datetime.now()))
                    send_hash = rpc.send(wallet="{}".format(WALLET), source="{}".format(sender_account),
                                         destination="{}".format(receiver_account), amount=withdraw_amount_raw)
                else:
                    logger.info("{}: processed with work: {} using wallet: {}".format(datetime.now(), work, WALLET))
                    send_hash = rpc.send(wallet="{}".format(WALLET), source="{}".format(sender_account),
                                         destination="{}".format(receiver_account), amount=withdraw_amount_raw,
                                         work=work)
                logger.info("{}: send_hash = {}".format(datetime.now(), send_hash))
                # respond that the withdraw has been processed
                modules.social.send_dm(message['sender_id'], translations.withdraw_text[message['language']]
                                       .format(withdraw_amount, CURRENCY, EXPLORER, send_hash), message['system'])
                logger.info("{}: Withdraw processed.  Hash: {}".format(datetime.now(), send_hash))
    else:
        modules.social.send_dm(message['sender_id'],
                               translations.incorrect_withdraw_text[message['language']].format(BOT_ACCOUNT,
                                                                                                CURRENCY),
                               message['system'])
        logger.info("{}: User sent a withdraw with invalid syntax.".format(datetime.now()))


def donate_process(message):
    """
    When the user sends !donate, send the provided amount from the user's account to the tip bot's donation wallet.
    If the user has no balance or account, reply with an error.
    """
    logger.info("{}: in donate_process.".format(datetime.now()))

    if len(message['dm_array']) >= 2:
        sender_account_call = (
            "SELECT account FROM users where user_id = {} and users.system = '{}'".format(message['sender_id'],
                                                                                          message['system']))
        donate_data = modules.db.get_db_data(sender_account_call)
        sender_account = donate_data[0][0]
        send_amount = message['dm_array'][1]

        modules.currency.receive_pending(sender_account)

        balance_return = rpc.account_balance(account='{}'.format(sender_account))
        balance = balance_return['balance'] / CONVERT_MULTIPLIER[CURRENCY]
        receiver_account = BOT_ACCOUNT

        try:
            logger.info("{}: The user is donating {} NANO".format(datetime.now(), Decimal(send_amount)))
        except Exception as e:
            logger.info("{}: ERROR IN CONVERTING DONATION AMOUNT: {}".format(datetime.now(), e))
            modules.social.send_dm(message['sender_id'], translations.wrong_donate_text[message['language']],
                                   message['system'])
            return ''
        logger.info("balance: {} - send_amount: {}".format(Decimal(balance), Decimal(send_amount)))
        # We need to reduce the send_amount for a proper comparison - Decimal will not store exact amounts
        # (e.g. 0.0003 = 0.00029999999999452123)
        if Decimal(balance) < (Decimal(send_amount) - Decimal(0.00001)):
            modules.social.send_dm(message['sender_id'],
                                   translations.large_donate_text[message['language']]
                                   .format(balance,
                                           CURRENCY.upper(),
                                           Decimal(send_amount)),
                                   message['system'])
            logger.info("{}: User tried to donate more than their balance.".format(datetime.now()))

        elif Decimal(send_amount) < Decimal(MIN_TIP):
            modules.social.send_dm(message['sender_id'], translations.small_donate_text[message['language']]
                                   .format(MIN_TIP), message['system'])
            logger.info("{}: User tried to donate less than 0.000001".format(datetime.now()))
            return ''
        else:
            # If the send amount > balance, send the whole balance.  If not, send the send amount.
            # This is to take into account for Decimal value conversions.
            if Decimal(send_amount) > Decimal(balance):
                send_amount_raw = Decimal(balance) * CONVERT_MULTIPLIER[CURRENCY]
            else:
                send_amount_raw = Decimal(send_amount) * CONVERT_MULTIPLIER[CURRENCY]
            logger.info(('{}; send_amount_raw: {}'.format(datetime.now(), int(send_amount_raw))))
            work = modules.currency.get_pow(sender_account)
            if work == '':
                logger.info("{}: Processing donation without work.".format(datetime.now()))
                send_hash = rpc.send(wallet="{}".format(WALLET), source="{}".format(sender_account),
                                     destination="{}".format(receiver_account),
                                     amount="{}".format(int(send_amount_raw)))
            else:
                logger.info("{}: Processing donation with work: {}".format(datetime.now(), work))
                send_hash = rpc.send(wallet="{}".format(WALLET), source="{}".format(sender_account),
                                     destination="{}".format(receiver_account),
                                     amount="{}".format(int(send_amount_raw)),
                                     work=work)

            logger.info("{}: send_hash = {}".format(datetime.now(), send_hash))

            modules.social.send_dm(message['sender_id'], translations.donate_text[message['language']]
                                   .format(send_amount, CURRENCY, EXPLORER, send_hash), message['system'])
            logger.info("{}: {} NANO donation processed.  Hash: {}".format(datetime.now(), Decimal(send_amount),
                                                                            send_hash))

    else:
        modules.social.send_dm(message['sender_id'], translations.incorrect_donate_text[message['language']],
                               message['system'])
        logger.info("{}: User sent a donation with invalid syntax".format(datetime.now()))


def tip_process(message, users_to_tip, request_json):
    """
    Main orchestration process to handle tips
    """
    logger.info("{}: in tip_process".format(datetime.now()))

    # Set tip commands
    if CURRENCY == 'banano':
        tip_commands = modules.translations.banano_tip_commands['en']
    else:
        tip_commands = modules.translations.nano_tip_commands[message['language']]
        if message['language'] != 'en':
            english_commands = modules.translations.nano_tip_commands['en']
            for command in english_commands:
                logger.info("commad: {}".format(command))
                tip_commands.append(command)

    message, users_to_tip = modules.social.set_tip_list(message, users_to_tip, request_json)
    if len(users_to_tip) < 1 and message['system'] != 'telegram':
        modules.social.send_reply(message, translations.no_users_text[message['language']].format(BOT_NAME_TWITTER,
                                                                                                  tip_commands[0]))
        return

    message = modules.social.validate_sender(message)
    if message['sender_account'] is None or message['tip_amount'] <= 0:
        return

    message = modules.social.validate_total_tip_amount(message)
    if message['tip_amount'] <= 0:
        return

    for t_index in range(0, len(users_to_tip)):
        modules.currency.send_tip(message, users_to_tip, t_index)

    # Inform the user that all tips were sent.
    if len(users_to_tip) >= 2:
        try:
            modules.social.send_reply(message, translations.multi_tip_success[message['language']]
                                      .format(message['tip_amount_text'], CURRENCY.upper(), EXPLORER,
                                              message['sender_account']))
            modules.social.send_dm(message['sender_id'],
                                   translations.multi_tip_success_dm[message['language']].format(
                                       message['tip_amount_text'],
                                       CURRENCY.upper(), EXPLORER,
                                       message['sender_account']),
                                   message['system'])
        except KeyError:
            modules.social.send_reply(message, translations.multi_tip_success['en']
                                      .format(message['tip_amount_text'], CURRENCY.upper(), EXPLORER,
                                              message['sender_account']))
            modules.social.send_dm(message['sender_id'],
                                   translations.multi_tip_success_dm['en'].format(message['tip_amount_text'],
                                                                                  CURRENCY.upper(), EXPLORER,
                                                                                  message['sender_account']),
                                   message['system'])

    elif len(users_to_tip) == 1:
        try:
            modules.social.send_reply(message, translations.tip_success[message['language']]
                                      .format(message['tip_amount_text'], CURRENCY.upper(), EXPLORER,
                                              message['send_hash']))
            if message['system'] != 'twitter':
                modules.social.send_dm(message['sender_id'], translations.tip_success_dm[message['language']]
                                       .format(message['tip_amount_text'], CURRENCY.upper(), EXPLORER,
                                               message['send_hash']), message['system'])
        except KeyError:
            modules.social.send_reply(message, translations.tip_success['en']
                                      .format(message['tip_amount_text'], CURRENCY.upper(), EXPLORER,
                                              message['send_hash']))
            if message['system'] != 'twitter':
                modules.social.send_dm(message['sender_id'], translations.tip_success_dm['en']
                                       .format(message['tip_amount_text'], CURRENCY.upper(), EXPLORER,
                                               message['send_hash']), message['system'])


def set_return_address_process(message):
    """
    Sets the return address for inactive accounts.
    """
    logger.info("return address process activated.")
    if len(message['dm_array']) <= 1:
        modules.social.send_dm(message['sender_id'],
                               translations.set_return_invalid_account[message['language']],
                               message['system'])
        return
    check_address_data = {'action': 'validate_account_number', 'account': message['dm_array'][1]}
    json_request = json.dumps(check_address_data)
    r = requests.post('{}'.format(NODE_IP), data=json_request)
    rx = r.json()
    logger.info("request return: {}".format(rx))
    if rx['valid'] == '0':
        modules.social.send_dm(message['sender_id'],
                               translations.set_return_invalid_account[message['language']],
                               message['system'])
        return
    else:
        set_return_address_call = "UPDATE return_address SET account = %s WHERE system = %s AND user_id = %s "
        set_return_address_values = [message['dm_array'][1], message['system'], message['sender_id']]
        logger.info("set_return_address_call: {}".format(set_return_address_call))
        logger.info("set_return_address_values: {}".format(set_return_address_values))
        modules.db.set_db_data(set_return_address_call, set_return_address_values)
        logger.info("{}: {} return address set for user {} as {}".format(datetime.now(),
                                                                          message['system'],
                                                                          message['sender_id'],
                                                                          message['dm_array'][1]))
        modules.social.send_dm(message['sender_id'],
                               translations.set_return_success[message['language']].format(message['dm_array'][1]),
                               message['system'])
    return


def language_process(message, new_language):
    """
    Let user set the language they want the tip bot translated to.
    """
    logger.info("In language process.  new_language = {}".format(new_language))
    logger.info("message text: {}".format(message['text']))
    if new_language.lower() not in translations.language_dict.keys():
        modules.social.send_dm(message['sender_id'],
                               translations.missing_language[message['language']],
                               message['system'])
    else:
        set_language_call = "UPDATE languages SET language_code = %s WHERE user_id = %s AND system = %s"
        set_language_values = [translations.language_dict[new_language], message['sender_id'], message['system']]
        modules.db.set_db_data(set_language_call, set_language_values)
        modules.social.send_dm(message['sender_id'],
                               translations.language_change_success[translations.language_dict[new_language]],
                               message['system'])


def language_list_process(message):
    """
    Send a list of languages available for translation.
    """
    modules.social.send_dm(message['sender_id'], translations.language_list, message['system'])
