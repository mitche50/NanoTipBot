import nano
import logging
import re
import requests
import json
import configparser
import telegram
from datetime import datetime

from modules.db import *

# Set Log File
logging.basicConfig(handlers=[logging.FileHandler('/root/webhooks/webhooks.log', 'a', 'utf-8')],
                    level=logging.INFO)

# Read config and parse constants
config = configparser.ConfigParser()
config.read('/root/webhooks/webhookconfig.ini')

# Constants
WALLET = config.get('webhooks', 'wallet')
NODE_IP = config.get('webhooks', 'node_ip')
WORK_SERVER = config.get('webhooks', 'work_server')
WORK_KEY = config.get('webhooks', 'work_key')
RE_EMOJI = re.compile('[\U00010000-\U0010ffff\U000026A1]', flags=re.UNICODE)
TELEGRAM_KEY = config.get('webhooks', 'telegram_key')

# Connect to Nano node
rpc = nano.rpc.Client(NODE_IP)

# Connect to Telegram
telegram_bot = telegram.Bot(token=TELEGRAM_KEY)

def send_dm(receiver, message, system):
    """
    Send the provided message to the provided receiver
    """
    if system == 'twitter':
        data = {
            'event': {
                'type': 'message_create', 'message_create': {
                    'target': {
                        'recipient_id': '{}'.format(receiver)
                    }, 'message_data': {
                        'text': '{}'.format(message)
                    }
                }
            }
        }

        r = twitterAPI.request('direct_messages/events/new', json.dumps(data))

        if r.status_code != 200:
            logging.info('Send DM - Twitter ERROR: {} : {}'.format(r.status_code, r.text))

    elif system == 'telegram':
        try:
            telegram_bot.sendMessage(chat_id=receiver, text=message)
        except Exception as e:
            logging.info("{}: Send DM - Telegram ERROR: {}".format(datetime.now(), e))
            pass


def receive_pending(sender_account):
    """
    Check to see if the account has any pending blocks and process them
    """
    try:
        logging.info("{}: in receive pending".format(datetime.now()))
        pending_blocks = rpc.pending(account='{}'.format(sender_account))
        logging.info("pending blocks: {}".format(pending_blocks))
        if len(pending_blocks) > 0:
            for block in pending_blocks:
                work = get_pow(sender_account)
                if work == '':
                    logging.info("{}: processing without pow".format(datetime.now()))
                    receive_data = {'action': "receive", 'wallet': WALLET, 'account': sender_account, 'block': block}
                else:
                    logging.info("{}: processing with pow".format(datetime.now()))
                    receive_data = {'action': "receive", 'wallet': WALLET, 'account': sender_account,
                                    'block': block, 'work': work}
                receive_json = json.dumps(receive_data)
                requests.post('{}'.format(NODE_IP), data=receive_json)
                logging.info("{}: block {} received".format(datetime.now(), block))

        else:
            logging.info('{}: No blocks to receive.'.format(datetime.now()))

    except Exception as e:
        logging.info("Receive Pending Error: {}".format(e))
        raise e

    return


def get_pow(sender_account):
    """
    Retrieves the frontier (hash of previous transaction) of the provided account and generates work for the next block.
    """
    logging.info("{}: in get_pow".format(datetime.now()))
    try:
        account_frontiers = rpc.accounts_frontiers(accounts=["{}".format(sender_account)])
        hash = account_frontiers[sender_account]
    except Exception as e:
        logging.info("{}: Error checking frontier: {}".format(datetime.now(), e))
        return ''
    logging.info("account_frontiers: {}".format(account_frontiers))

    work = ''
    logging.info("{}: hash: {}".format(datetime.now(), hash))
    while work == '':
        try:
            work_data = {'hash': hash, 'key': WORK_KEY}
            json_request = json.dumps(work_data)
            r = requests.post('{}'.format(WORK_SERVER), data=json_request)
            rx = r.json()
            work = rx['work']
            logging.info("{}: Work generated: {}".format(datetime.now(), work))
        except Exception as e:
            logging.info("{}: ERROR GENERATING WORK: {}".format(datetime.now(), e))
            pass

    return work


def send_tip(message, users_to_tip, tip_index):
    """
    Process tip for specified user
    """
    logging.info("{}: sending tip to {}".format(datetime.now(), users_to_tip[tip_index]['receiver_screen_name']))
    if str(users_to_tip[tip_index]['receiver_id']) == str(message['sender_id']):
        self_tip_text = "Self tipping is not allowed.  Please use this bot to spread the $NANO to other Twitter users!"
        send_reply(message, self_tip_text)

        logging.info("{}: User tried to tip themself").format(datetime.now())
        return

    # Check if the receiver has an account
    receiver_account_get = ("SELECT account FROM users where user_id = {} and system = '{}'"
                            .format(int(users_to_tip[tip_index]['receiver_id']), message['system']))
    receiver_account_data = get_db_data(receiver_account_get)

    # If they don't, create an account for them
    if not receiver_account_data:
        users_to_tip[tip_index]['receiver_account'] = rpc.account_create(wallet="{}".format(WALLET), work=True)
        create_receiver_account = ("INSERT INTO users (user_id, system, user_name, account, register) "
                                   "VALUES(%s, %s, %s, %s, 0)")
        create_receiver_account_values = [users_to_tip[tip_index]['receiver_id'], message['system'],
                                           users_to_tip[tip_index]['receiver_screen_name'],
                                           users_to_tip[tip_index]['receiver_account']]
        err = set_db_data(create_receiver_account, create_receiver_account_values)
        logging.info("{}: Sender sent to a new receiving account.  Created  account {}"
                     .format(datetime.now(), users_to_tip[tip_index]['receiver_account']))

    else:
        users_to_tip[tip_index]['receiver_account'] = receiver_account_data[0][0]

    # Send the tip
    message['tip_id'] = "{}{}".format(message['id'], tip_index)

    work = get_pow(message['sender_account'])
    logging.info("Sending Tip:")
    logging.info("From: {}".format(message['sender_account']))
    logging.info("To: {}".format(users_to_tip[tip_index]['receiver_account']))
    logging.info("amount: {:f}".format(message['tip_amount_raw']))
    logging.info("id: {}".format(message['tip_id']))
    logging.info("work: {}".format(work))
    if work == '':
        logging.info("{}: processed without work".format(datetime.now()))
        message['send_hash'] = rpc.send(wallet="{}".format(WALLET), source="{}".format(message['sender_account']),
                                        destination="{}".format(users_to_tip[tip_index]['receiver_account']),
                                        amount="{}".format(int(message['tip_amount_raw'])),
                                        id="tip-{}".format(message['tip_id']))
    else:
        logging.info("{}: processed with work: {}".format(datetime.now(), work))
        message['send_hash'] = rpc.send(wallet="{}".format(WALLET), source="{}".format(message['sender_account']),
                                        destination="{}".format(users_to_tip[tip_index]['receiver_account']),
                                        amount="{}".format(int(message['tip_amount_raw'])),
                                        work=work,
                                        id="tip-{}".format(message['tip_id']))
    # Update the DB
    message['text'] = strip_emoji(message['text'])
    set_db_data_tip(message, users_to_tip, tip_index)

    # Get receiver's new balance
    try:
        logging.info("{}: Checking to receive new tip")
        receive_pending(users_to_tip[tip_index]['receiver_account'])
        balance_return = rpc.account_balance(account="{}".format(users_to_tip[tip_index]['receiver_account']))
        users_to_tip[tip_index]['balance'] = balance_return['balance'] / 1000000000000000000000000000000

        # create a string to remove scientific notation from small decimal tips
        if str(users_to_tip[tip_index]['balance'])[0] == ".":
            users_to_tip[tip_index]['balance'] = "0{}".format(str(users_to_tip[tip_index]['balance']))
        else:
            users_to_tip[tip_index]['balance'] = str(users_to_tip[tip_index]['balance'])

        # Send a DM to the receiver
        receiver_tip_text = (
            "@{} just sent you a {} NANO tip! Reply to this DM with !balance to see your new balance.  If you have not "
            "registered an account, send a reply with !register to get started, or !help to see a list of "
            "commands!  Learn more about NANO at https://nano.org/".format(message['sender_screen_name'],
                                                                           message['tip_amount_text'],
                                                                           users_to_tip[tip_index]['balance']))
        send_dm(users_to_tip[tip_index]['receiver_id'], receiver_tip_text, message['system'])

    except Exception as e:
        logging.info("{}: ERROR IN RECEIVING NEW TIP - POSSIBLE NEW ACCOUNT NOT REGISTERED WITH DPOW: {}"
                     .format(datetime.now(), e))

    logging.info(
        "{}: tip sent to {} via hash {}".format(datetime.now(), users_to_tip[tip_index]['receiver_screen_name'],
                                                message['send_hash']))


def get_energy(nano_energy):
    """
    Calculate the total energy used by Nano at time of loading the webpage.
    """
    block_count_get = rpc.block_count()
    checked_blocks = block_count_get['count']

    total_energy = checked_blocks * nano_energy

    return total_energy, checked_blocks


def strip_emoji(text):
    """
    Remove Emojis from tweet text to prevent issues with logging
    """
    logging.info('{}: removing emojis'.format(datetime.now()))
    text = str(text)
    return RE_EMOJI.sub(r'', text)
