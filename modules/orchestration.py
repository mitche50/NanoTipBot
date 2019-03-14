import configparser
import logging
import os
from datetime import datetime
from decimal import Decimal
from http import HTTPStatus

import nano

import modules.currency
import modules.db
import modules.social
import modules.translations as translations

# Set Log File
logging.basicConfig(handlers=[logging.FileHandler('{}/webhooks.log'.format(os.getcwd()), 'a', 'utf-8')],
                    level=logging.INFO)

# Read config and parse constants
config = configparser.ConfigParser()
config.read('{}/webhookconfig.ini'.format(os.getcwd()))

# Set constants
BULLET = u"\u2022"
NODE_IP = config.get('webhooks', 'node_ip')
WALLET = config.get('webhooks', 'wallet')
BOT_ID_TWITTER = config.get('webhooks', 'bot_id_twitter')
BOT_NAME = config.get('webhooks', 'bot_name')
BOT_ACCOUNT = config.get('webhooks', 'bot_account')
MIN_TIP = config.get('webhooks', 'min_tip')

# Connect to global functions
rpc = nano.rpc.Client(NODE_IP)


def parse_action(message):
    if message['dm_action'] in translations.help_commands['en'] or \
            message['dm_action'] in translations.help_commands[message['language']]:
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

    elif message['dm_action'] in translations.balance_commands['en'] or \
            message['dm_action'] in translations.balance_commands[message['language']]:
        new_pid = os.fork()
        if new_pid == 0:
            try:
                bot_status = config.get('webhooks', 'bot_status')
                if bot_status == 'maintenance':
                    modules.social.send_dm(message['sender_id'], translations.maintenance_text[message['language']],
                                           message['system'])
                else:
                    balance_process(message)
            except Exception as e:
                logging.info("Exception: {}".format(e))
                raise e
            os._exit(0)
        else:
            return '', HTTPStatus.OK

    elif message['dm_action'] in translations.register_commands['en'] or \
            message['dm_action'] in translations.register_commands[message['language']]:
        new_pid = os.fork()
        if new_pid == 0:
            try:
                bot_status = config.get('webhooks', 'bot_status')
                if bot_status == 'maintenance':
                    modules.social.send_dm(message['sender_id'], translations.maintenance_text[message['language']],
                                           message['system'])
                else:
                    register_process(message)
            except Exception as e:
                logging.info("Exception: {}".format(e))
                raise e
            os._exit(0)
        else:
            return '', HTTPStatus.OK

    elif message['dm_action'] in translations.tip_commands['en'] or \
            message['dm_action'] in translations.tip_commands[message['language']]:
        new_pid = os.fork()
        if new_pid == 0:
            try:
                modules.social.send_dm(message['sender_id'], translations.redirect_tip_text[message['language']],
                                       message['system'])
            except Exception as e:
                logging.info("Exception: {}".format(e))
                raise e
            os._exit(0)
        else:
            return '', HTTPStatus.OK

    elif message['dm_action'] in translations.withdraw_commands['en'] or \
            message['dm_action'] in translations.withdraw_commands[message['language']]:
        new_pid = os.fork()
        if new_pid == 0:
            try:
                bot_status = config.get('webhooks', 'bot_status')
                if bot_status == 'maintenance':
                    modules.social.send_dm(message['sender_id'], translations.maintenance_text[message['language']],
                                           message['system'])
                else:
                    withdraw_process(message)
            except Exception as e:
                logging.info("Exception: {}".format(e))
                raise e
            os._exit(0)
        else:
            return '', HTTPStatus.OK

    elif message['dm_action'] in translations.donate_commands['en'] or \
            message['dm_action'] in translations.donate_commands[message['language']]:
        new_pid = os.fork()
        if new_pid == 0:
            try:
                bot_status = config.get('webhooks', 'bot_status')
                if bot_status == 'maintenance':
                    modules.social.send_dm(message['sender_id'], translations.maintenance_text[message['language']],
                                           message['system'])
                else:
                    donate_process(message)
            except Exception as e:
                logging.info("Exception: {}".format(e))
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
                logging.info("Exception: {}".format(e))
                raise e
            os._exit(0)
        else:
            return '', HTTPStatus.OK

    elif message['dm_action'] in translations.private_tip_commands['en'] or \
            message['dm_action'] in translations.private_tip_commands[message['language']]:
        new_pid = os.fork()
        if new_pid == 0:
            try:
                modules.social.send_dm(message['sender_id'], translations.private_tip_text[message['language']],
                                       message['system'])
            except Exception as e:
                logging.info("Exception: {}".format(e))
                raise e
            os._exit(0)
        else:
            return '', HTTPStatus.OK

    elif message['dm_action'] in translations.language_commands:
        new_pid = os.fork()
        if new_pid == 0:
            try:
                bot_status = config.get('webhooks', 'bot_status')
                if bot_status == 'maintenance':
                    modules.social.send_dm(message['sender_id'], translations.maintenance_text[message['language']],
                                           message['system'])
                else:
                    try:
                        new_language = message['text'].split(' ')[1].lower()
                        if new_language == 'chinese':
                            new_language += ' ' + message['text'].split(' ')[2].lower()
                        language_process(message, new_language)
                    except Exception as f:
                        logging.info("{}: Error in language process: {}".format(datetime.now(), f))
                        modules.social.send_dm(message['sender_id'], translations.missing_language[message['language']],
                                               message['system'])
            except Exception as e:
                logging.info("Exception: {}".format(e))
                raise e
            os._exit(0)
        else:
            return '', HTTPStatus.OK

    elif message['dm_action'] in translations.language_list_commands:
        new_pid = os.fork()
        if new_pid == 0:
            try:
                bot_status = config.get('webhooks', 'bot_status')
                if bot_status == 'maintenance':
                    modules.social.send_dm(message['sender_id'], translations.maintenance_text[message['language']],
                                           message['system'])
                else:
                    language_list_process(message)
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
                modules.social.send_dm(message['sender_id'], translations.wrong_format_text[message['language']],
                                       message['system'])
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
    modules.social.send_dm(message['sender_id'], translations.help_message[message['language']], message['system'])
    logging.info("{}: Help message sent!".format(datetime.now()))


def balance_process(message):
    """
    When the user sends a DM containing !balance, reply with the balance of the account linked with their Twitter ID
    """
    logging.info("{}: In balance process".format(datetime.now()))
    balance_call = ("SELECT account, register FROM users WHERE user_id = {} "
                    "AND users.system = '{}'".format(message['sender_id'], message['system']))
    data = modules.db.get_db_data(balance_call)
    if not data:
        logging.info("{}: User tried to check balance without an account".format(datetime.now()))
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

        balance_return = rpc.account_balance(account="{}".format(message['sender_account']))
        message['sender_balance_raw'] = balance_return['balance']
        message['sender_pending_raw'] = balance_return['pending']
        message['sender_balance'] = balance_return['balance'] / 1000000000000000000000000000000
        message['sender_pending'] = balance_return['pending'] / 1000000000000000000000000000000
        # if message['sender_balance'] == 0 and message['sender_pending'] == 0:
        #     balance_text = "Your balance is 0 NANO."
        # elif message['sender_balance'] == 0 and message['sender_pending'] > 0:
        #     balance_text = "Available: 0 NANO\n" \
        #                    "Pending: {} NANO".format(message['sender_pending'])
        # elif message['sender_balance'] > 0 and message['sender_pending'] == 0:
        #     balance_text = "Available: {} NANO\n" \
        #                    "Pending: 0 NANO".format(message['sender_balance'])
        # else:
        #     balance_text = "Available: {} NANO\n" \
        #                    "Pending: {} NANO".format(message['sender_balance'], message['sender_pending'])
        modules.social.send_dm(message['sender_id'], translations.balance_text[message['language']]
                               .format(message['sender_balance'], message['sender_pending']), message['system'])
        logging.info("{}: Balance Message Sent!".format(datetime.now()))
        modules.currency.receive_pending(message['sender_account'])


def register_process(message):
    """
    When the user sends !register, create an account for them and mark it registered.  If they already have an account
    reply with their account number.
    """
    logging.info("{}: In register process.".format(datetime.now()))
    register_call = ("SELECT account, register FROM users WHERE user_id = {} AND users.system = '{}'"
                     .format(message['sender_id'], message['system']))
    data = modules.db.get_db_data(register_call)

    if not data:
        # Create an account for the user
        sender_account = rpc.account_create(wallet="{}".format(WALLET), work=False)
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

        logging.info("{}: Register successful!".format(datetime.now()))

    elif data[0][1] == 0:
        # The user has an account, but needed to register, so send a message to the user with their account
        sender_account = data[0][0]
        account_registration_update = "UPDATE users SET register = 1 WHERE user_id = %s AND register = 0"
        account_registration_values = [message['sender_id'], ]
        modules.db.set_db_data(account_registration_update, account_registration_values)

        account_register_text = translations.account_register_text[message['language']]
        modules.social.send_account_message(account_register_text, message, sender_account)

        logging.info("{}: User has an account, but needed to register.  Message sent".format(datetime.now()))

    else:
        # The user had an account and already registered, so let them know their account.
        sender_account = data[0][0]
        account_already_registered = translations.account_already_registered[message['language']]
        modules.social.send_account_message(account_already_registered, message, sender_account)

        logging.info("{}: User has a registered account.  Message sent.".format(datetime.now()))


def account_process(message):
    """
    If the user sends !account command, reply with their account.  If there is no account, create one, register it
    and reply to the user.
    """
    logging.info("{}: In account process.".format(datetime.now()))
    sender_account_call = (
        "SELECT account, register FROM users WHERE user_id = {} AND users.system = '{}'".format(message['sender_id'],
                                                                                                message['system']))
    account_data = modules.db.get_db_data(sender_account_call)
    if not account_data:
        logging.info("Creating account using wallet: {}".format(WALLET))
        sender_account = rpc.account_create(wallet="{}".format(WALLET), work=True)
        account_create_call = ("INSERT INTO users (user_id, system, user_name, account, register) "
                               "VALUES(%s, %s, %s, %s, 1)")
        account_create_values = [message['sender_id'], message['system'], message['sender_screen_name'], sender_account]
        modules.db.set_db_data(account_create_call, account_create_values)

        account_create_text = translations.account_create_text[message['language']]
        modules.social.send_account_message(account_create_text, message, sender_account)

        logging.info("{}: Created an account for the user!".format(datetime.now()))

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
        withdraw_account_call = ("SELECT account, register FROM users WHERE user_id = {} AND users.system = '{}'"
                                 .format(message['sender_id'], message['system']))
        withdraw_data = modules.db.get_db_data(withdraw_account_call)

        if not withdraw_data:

            modules.social.send_dm(message['sender_id'], translations.withdraw_no_account_text[message['language']],
                                   message['system'])
            logging.info("{}: User tried to withdraw with no account".format(datetime.now()))

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
                logging.info("{}: The xrb account number is invalid: {}".format(datetime.now(), receiver_account))

            elif balance_return['balance'] == 0:
                modules.social.send_dm(message['sender_id'], translations.no_balance_text[message['language']]
                                       .format(sender_account), message['system'])
                logging.info("{}: The user tried to withdraw with 0 balance".format(datetime.now()))

            else:
                if len(message['dm_array']) == 3:
                    try:
                        withdraw_amount = Decimal(message['dm_array'][1])
                    except Exception as e:
                        logging.info("{}: withdraw no number ERROR: {}".format(datetime.now(), e))
                        modules.social.send_dm(message['sender_id'],
                                               translations.invalid_amount_text[message['language']],
                                               message['system'])
                        return
                    withdraw_amount_raw = int(withdraw_amount * 1000000000000000000000000000000)
                    if Decimal(withdraw_amount_raw) > Decimal(balance_return['balance']):
                        modules.social.send_dm(message['sender_id'],
                                               translations.not_enough_balance_text[message['language']],
                                               message['system'])
                        return
                else:
                    withdraw_amount_raw = balance_return['balance']
                    withdraw_amount = balance_return['balance'] / 1000000000000000000000000000000
                # send the total balance to the provided account
                work = modules.currency.get_pow(sender_account)
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
                modules.social.send_dm(message['sender_id'], translations.withdraw_text[message['language']]
                                       .format(withdraw_amount, send_hash), message['system'])
                logging.info("{}: Withdraw processed.  Hash: {}".format(datetime.now(), send_hash))
    else:
        modules.social.send_dm(message['sender_id'], translations.incorrect_withdraw_text[message['language']],
                               message['system'])
        logging.info("{}: User sent a withdraw with invalid syntax.".format(datetime.now()))


def donate_process(message):
    """
    When the user sends !donate, send the provided amount from the user's account to the tip bot's donation wallet.
    If the user has no balance or account, reply with an error.
    """
    logging.info("{}: in donate_process.".format(datetime.now()))

    if len(message['dm_array']) >= 2:
        sender_account_call = (
            "SELECT account FROM users where user_id = {} and users.system = '{}'".format(message['sender_id'],
                                                                                          message['system']))
        donate_data = modules.db.get_db_data(sender_account_call)
        sender_account = donate_data[0][0]
        send_amount = message['dm_array'][1]

        modules.currency.receive_pending(sender_account)

        balance_return = rpc.account_balance(account='{}'.format(sender_account))
        balance = balance_return['balance'] / 1000000000000000000000000000000
        receiver_account = BOT_ACCOUNT

        try:
            logging.info("{}: The user is donating {} NANO".format(datetime.now(), Decimal(send_amount)))
        except Exception as e:
            logging.info("{}: ERROR IN CONVERTING DONATION AMOUNT: {}".format(datetime.now(), e))
            modules.social.send_dm(message['sender_id'], translations.wrong_donate_text[message['language']],
                                   message['system'])
            return ''
        logging.info("balance: {} - send_amount: {}".format(Decimal(balance), Decimal(send_amount)))
        # We need to reduce the send_amount for a proper comparison - Decimal will not store exact amounts
        # (e.g. 0.0003 = 0.00029999999999452123)
        if Decimal(balance) < (Decimal(send_amount) - Decimal(0.00001)):
            modules.social.send_dm(message['sender_id'], translations.large_donate_text[message['language']]
                                   .format(balance, Decimal(send_amount)), message['system'])
            logging.info("{}: User tried to donate more than their balance.".format(datetime.now()))

        elif Decimal(send_amount) < Decimal(MIN_TIP):
            modules.social.send_dm(message['sender_id'], translations.small_donate_text[message['language']]
                                   .format(MIN_TIP), message['system'])
            logging.info("{}: User tried to donate less than 0.000001".format(datetime.now()))
            return ''
        else:
            # If the send amount > balance, send the whole balance.  If not, send the send amount.
            # This is to take into account for Decimal value conversions.
            if Decimal(send_amount) > Decimal(balance):
                send_amount_raw = Decimal(balance) * 1000000000000000000000000000000
            else:
                send_amount_raw = Decimal(send_amount) * 1000000000000000000000000000000
            logging.info(('{}; send_amount_raw: {}'.format(datetime.now(), int(send_amount_raw))))
            work = modules.currency.get_pow(sender_account)
            if work == '':
                logging.info("{}: Processing donation without work.".format(datetime.now()))
                send_hash = rpc.send(wallet="{}".format(WALLET), source="{}".format(sender_account),
                                     destination="{}".format(receiver_account),
                                     amount="{}".format(int(send_amount_raw)))
            else:
                logging.info("{}: Processing donation with work: {}".format(datetime.now(), work))
                send_hash = rpc.send(wallet="{}".format(WALLET), source="{}".format(sender_account),
                                     destination="{}".format(receiver_account),
                                     amount="{}".format(int(send_amount_raw)),
                                     work=work)

            logging.info("{}: send_hash = {}".format(datetime.now(), send_hash))

            modules.social.send_dm(message['sender_id'], translations.donate_text[message['language']]
                                   .format(send_amount, send_hash), message['system'])
            logging.info("{}: {} NANO donation processed.  Hash: {}".format(datetime.now(), Decimal(send_amount),
                                                                            send_hash))

    else:
        modules.social.send_dm(message['sender_id'], translations.incorrect_donate_text[message['language']],
                               message['system'])
        logging.info("{}: User sent a donation with invalid syntax".format(datetime.now()))


def tip_process(message, users_to_tip, request_json):
    """
    Main orchestration process to handle tips
    """
    logging.info("{}: in tip_process".format(datetime.now()))

    message, users_to_tip = modules.social.set_tip_list(message, users_to_tip, request_json)
    if len(users_to_tip) < 1 and message['system'] != 'telegram':
        modules.social.send_reply(message, translations.no_users_text[message['language']])
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
                                      .format(message['tip_amount_text'], message['sender_account']))
        except KeyError:
            modules.social.send_reply(message, translations.multi_tip_success['en']
                                      .format(message['tip_amount_text'], message['sender_account']))

    elif len(users_to_tip) == 1:
        try:
            modules.social.send_reply(message, translations.tip_success[message['language']]
                                      .format(message['tip_amount_text'], message['send_hash']))
        except KeyError:
            modules.social.send_reply(message, translations.tip_success['en']
                                      .format(message['tip_amount_text'], message['send_hash']))


def language_process(message, new_language):
    """
    Let user set the language they want the tip bot translated to.
    """
    logging.info("In language process.  new_language = {}".format(new_language))
    logging.info("message text: {}".format(message['text']))
    if new_language.lower() not in translations.language_dict.keys():
        modules.social.send_dm(message['sender_id'],
                               translations.missing_language[message['language']],
                               message['system'])
    else:
        set_language_call = "UPDATE tip_bot.languages SET language_code = %s WHERE user_id = %s AND system = %s"
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
