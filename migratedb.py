import configparser
import os
import nano

import modules.currency
import modules.db as db

# Read config and parse constants
config = configparser.ConfigParser()
config.read('/root/bananowebhooks/webhookconfig.ini'.format(os.getcwd()))

CURRENCY = 'banano'
NODE_IP = config.get(CURRENCY, 'node_ip')
WALLET = config.get(CURRENCY, 'wallet')
BB_WALLET = 'EB99BD535700A33F85E65D9F10A17E7A068AB370D58DFA0C7F3BDC93954B4213'
CONVERT_MULTIPLIER = {
    'nano': 1000000000000000000000000000000,
    'banano': 100000000000000000000000000000
}

rpc = nano.rpc.Client(NODE_IP)


def move_accounts(send_account, receive_account):
    print("moving accounts from {} to {}".format(send_account, receive_account))
    modules.currency.receive_pending(send_account)
    balance = rpc.account_balance(account=send_account)
    if balance['balance'] > 0:
        work = modules.currency.get_pow(send_account)
        block = rpc.send(wallet=BB_WALLET, source=send_account, destination=receive_account, amount=balance['balance'], work=work)

        return block

    return ''


# get all user IDs, usernames accounts and registration status from bbedward
bbedward_users = db.get_db_data("SELECT user_id, user_name, account, register FROM bbedward.users;")

# get all user IDs from bananotipbot
new_users = db.get_db_data("SELECT user_id, system, account FROM banano_tip_bot.users WHERE system = 'telegram';")
user_ids = []

for user in new_users:
    user_ids.append(user[0])

# for each record from bbedward, check if it exists in bananotipbot
for user in bbedward_users:
    if user[0] not in user_ids:
        print("user: {}".format(user))
        print("generating a new account")
        account = rpc.account_create(wallet=WALLET, work=False)
        set_db_call = "INSERT INTO banano_tip_bot.users (user_id, system, user_name, account, register) VALUES (%s, 'telegram', %s, %s, %s);"
        set_db_values = [user[0], user[1], account, user[3]]
        modules.db.set_db_data(set_db_call, set_db_values)
        try:
            block = move_accounts(user[2], account)
        except Exception as e:
            raise e

        mark_migrated = "UPDATE bbedward.users SET migrated = 2 WHERE user_id = %s AND user_name = %s"
        mark_migrated_values = [user[0], user[1]]
        if block == '':
            print()
            print("old tip bot account {} had no balance".format(user[2]))
        else:
            print("account {} balance moved to new account {}".format(user[2], account))


bbedward_users_existing = db.get_db_data("SELECT user_id, user_name, account, register FROM bbedward.users WHERE migrated = 0;")

for user in bbedward_users_existing:
    print("user: {}".format(user))
    migrate_account_call = "SELECT account FROM banano_tip_bot.users WHERE user_id = {} AND system = 'telegram'".format(user[0])
    print(migrate_account_call)
    migrate_account_list = modules.db.get_db_data(migrate_account_call)
    migrate_account = migrate_account_list[0][0]
    block = move_accounts(user[2], migrate_account)
    mark_migrated = "UPDATE bbedward.users SET migrated = 2 WHERE user_id = %s AND user_name = '%s'"
    mark_migrated_values = [user[0], user[1]]
    if block == '':
        print("old tip bot account {} had no balance".format(user[2]))
    else:
        print("account {} balance moved to new account {}".format(user[2], migrate_account))

