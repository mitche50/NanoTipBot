import requests
import json
import modules.currency as currency

balance_data = {
    'action': 'wallet_balances',
    'wallet': 'EB99BD535700A33F85E65D9F10A17E7A068AB370D58DFA0C7F3BDC93954B4213',
    'threshold': '1'
}

json_request = json.dumps(balance_data)
r = requests.post('http://159.65.228.200:7072', data=json_request)
rx = r.json()
print(rx['balances']['ban_1qbooxtr4ek1fbgqjiu1nwtezi6jrf1r8nixqm5i3z5r6kagazjat9y1bh4h']['balance'])

for account in rx['balances']:
    work = currency.get_pow(account)
    send_data = {
        'action': 'send',
        'wallet': 'EB99BD535700A33F85E65D9F10A17E7A068AB370D58DFA0C7F3BDC93954B4213',
        'source': account,
        'destination': 'ban_1drrg4wqgm4tj3y7zw4xjd9psh8gxqk1smuerabjd84gg515ajpshuqc7ss8',
        'amount': rx['balances'][account]['balance'],
        'work': work
    }
    send_json = json.dumps(send_data)
    s_r = requests.post('http://159.65.228.200:7072', data=send_json)
    s_rx = s_r.json()
    if 'block' in s_rx:
        print(s_rx['block'])
    else:
        print(s_rx)
    

# send_data = {
#                 'action': 'send',
#                 'wallet': WALLET,
#                 'source': message['sender_account'],
#                 'destination': users_to_tip[tip_index]['receiver_account'],
#                 'amount': int(message['tip_amount_raw']),
#                 'id': 'tip-{}'.format(message['tip_id']),
#                 'work': work
#             }
#             json_request = json.dumps(send_data)
#             r = requests.post('{}'.format(NODE_IP), data=json_request)
#             rx = r.json()
#             logging.info("{}: {} - send return: {}".format(datetime.now(), message['tip_id'], rx))
#             if 'block' in rx:
#                 message['send_hash'] = rx['block']
#             else:
#                 modules.social.send_reply(message, 'There was an error processing one of your tips.  '
#                                                    'Please reach out to the admin with this code: {}'
#                                           .format(message['tip_id']))
#                 return