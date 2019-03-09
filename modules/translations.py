BULLET = u'\u2022'

maintenance_text = {
    'en': 'The tip bot is in maintenance.  Check @NanoTipBot on Twitter for more information.',
    'es': '',
    'ja': '',
    'cn': '',
    'fr': '',
    'ge': '',
    'ru': 'Совет бот находится в обслуживании. Проверьте @NanoTipBot на Twitter для получения дополнительной '
          'информации.',
    'sv': ''
}
redirect_tip_text = {
    'en': 'Tips are processed through public messages now.  Please send in the format @NanoTipBot !tip 1 @user1.',
    'es': '',
    'ja': '',
    'cn': '',
    'fr': '',
    'ge': '',
    'ru': 'Советы теперь обрабатываются через публичные сообщения. Пожалуйста, отправьте в формате @NanoTipBot '
          '!tip 1 @имя пользователя1.',
    'sv': ''
}

self_tip_text = {
    'en': 'Self tipping is not allowed.  Please use this bot to spread the $NANO to other Twitter users!',
    'es': '',
    'ja': '',
    'cn': '',
    'fr': '',
    'ge': '',
    'ru': 'Самостоятельные чаевые не допускаются. Пожалуйста, используйте этот бот, чтобы распространять '
          '$NANO другим пользователям Twitter!',
    'sv': ''
}

receiver_tip_text = {
    'en': '@{} just sent you a {} NANO tip! Reply to this DM with !balance to see your new balance.  '
          'If you have not registered an account, send a reply with !register to get started, or '
          '!help to see a list of commands!  Learn more about NANO at https://nano.org/',
    'es': '',
    'ja': '',
    'cn': '',
    'fr': '',
    'ge': '',
    'ru': '@{} только что отправил вам {} NANO чаевые! Ответьте на этот DM с помощью  !balance , чтобы увидеть '
          'ваш новый баланс. Если вы еще не зарегистрировали учетную запись, отправьте ответ с помощью  !register '
          'для начала или  !help, чтобы увидеть список команд! Узнайте больше о NANO на https://nano.org/',
    'sv': ''
}

private_tip_text = {
    'en': 'Private Tip is under maintenance.  To send your tip, use the !tip function in a tweet or reply!',
    'es': '',
    'ja': '',
    'cn': '',
    'fr': '',
    'ge': '',
    'ru': 'Частный совет находится на обслуживании. Чтобы отправить свой совет, используйте функцию '
          '!tip в твите или ответе!',
    'sv': ''
}

wrong_format_text = {
    'en': 'The command or syntax you sent is not recognized.  Please send !help for a list of '
          'commands and what they do.',
    'es': '',
    'ja': '',
    'cn': '',
    'fr': '',
    'ge': '',
    'ru': 'Отправленная вами команда или синтаксис не распознаются. Пожалуйста, пришлите !help для получения '
          'списка команд и того, что они делают.',
    'sv': ''
}

no_users_text = {
    'en': "Looks like you didn't enter in anyone to tip, or you mistyped someone's handle.  You can try "
          "to tip again using the format !tip 1234 @username",
    'es': '',
    'ja': '',
    'cn': '',
    'fr': '',
    'ge': '',
    'ru': 'Похоже, ты не отметил никого, чтобы давать чаевые, или набрал неверно. Вы можете попробовать дать '
          'чаевые снова, используя формат !tip 1234 @имя пользователя',
    'sv': ''
}

multi_tip_success = {
    'en': 'You have successfully sent your {} $NANO tips.  '
          'Check your account at https://nanocrawler.cc/explorer/account/{}',
    'es': '',
    'ja': '',
    'cn': '',
    'fr': '',
    'ge': '',
    'ru': 'Вы успешно отправили свой совет {} $NANO. Проверьте эту транзакцию на '
          'https://nanocrawler.cc/explorer/block/{}',
    'sv': ''
}

tip_success = {
    'en': 'You have successfully sent your {} $NANO tip.  '
          'Check out this transaction at https://nanocrawler.cc/explorer/block/{}',
    'es': '',
    'ja': '',
    'cn': '',
    'fr': '',
    'ge': '',
    'ru': '',
    'sv': ''
}

not_a_number_text = {
    'en': 'Looks like the value you entered to tip was not a number.  You can try to tip '
          'again using the format !tip 1234 @username',
    'es': '',
    'ja': '',
    'cn': '',
    'fr': '',
    'ge': '',
    'ru': '',
    'sv': ''
}

min_tip_text = {
    'en': 'The minimum tip amount is {} NANO.  Please update your tip amount and try again.',
    'es': '',
    'ja': '',
    'cn': '',
    'fr': '',
    'ge': '',
    'ru': '',
    'sv': ''
}

missing_user_message = {
    'en': '{} not found in our records.  In order to tip them, they need to be a member of the channel.  If they are '
          'in the channel, please have them send a message in the chat so I can add them.',
    'es': '',
    'ja': '',
    'cn': '',
    'fr': '',
    'ge': '',
    'ru': '',
    'sv': ''
}

no_account_text = {
    'en': 'You do not have an account with the bot.  Please send a DM to me with !register to set up an account.',
    'es': '',
    'ja': '',
    'cn': '',
    'fr': '',
    'ge': '',
    'ru': '',
    'sv': ''
}

not_enough_text = {
    'en': 'You do not have enough NANO to cover this {} NANO tip.  '
          'Please check your balance by sending a DM to me with !balance and retry.',
    'es': '',
    'ja': '',
    'cn': '',
    'fr': '',
    'ge': '',
    'ru': '',
    'sv': ''
}

help_message = {
    'en': 'Thank you for using the Nano Tip Bot!  Below is a list of commands, and a description of what they do:\n\n'
          + BULLET + '!help: The tip bot will respond to your DM with a list of commands and their functions. If you'
                     ' forget something, use this to get a hint of how to do it!\n\n'
          + BULLET + ' !register: Registers your user ID for an account that is tied to it.  This is used to store'
                     ' your tips. Make sure to withdraw to a private wallet, as the tip bot is not meant to be a '
                     'long term storage device for Nano.\n\n'
          + BULLET + '!balance: This returns the balance of the account linked with your user ID.\n\n'
          + BULLET + '!tip: Tips are sent through public tweets or in Telegram groups.\n'
                     ' On Twitter: Tag @NanoTipBot in a tweet and mention !tip <amount> <@username>.  '
                     ' Example: @NanoTipBot !tip 1 @mitche50 would send a 1 Nano tip to user @mitche50.\n'
                     ' On Telegram send !tip <amount> <@username> to tip in the group.\n\n'
          + BULLET + ' !privatetip: Currently disabled.  This will send a tip to another user through DM.  If you '
                     'would like your tip amount to be private, use this function!  Proper usage is !privatetip '
                     '@username 1234\n\n'
          + BULLET + ' !account: Returns the account number that is tied to your user ID (currently unique to '
                     'platform).  You can use this to deposit more Nano to tip from your personal wallet.\n\n'
          + BULLET + ' !withdraw: Proper usage is !withdraw xrb_12345.  This will send the full balance of your tip '
                     'account to the provided Nano account.  Optional: You can include an amount to withdraw by '
                     'sending !withdraw <amount> <address>.  Example: !withdraw 1 xrb_iaoia83if221lodoepq would '
                     'withdraw 1 NANO to account xrb_iaoia83if221lodoepq.\n\n'
          + BULLET + ' !donate: Proper usage is !donate 1234.  This will send the requested donation to the Nano Tip '
                     'Bot donation account to help fund development efforts.',
    'es': '',
    'ja': '',
    'cn': '',
    'fr': '',
    'ge': '',
    'ru': '',
    'sv': ''
}

account_register_text = {
    'en': 'You have successfully registered for an account.  Your account number is:',
    'es': '',
    'ja': '',
    'cn': '',
    'fr': '',
    'ge': '',
    'ru': '',
    'sv': ''
}

account_already_registered = {
    'en': 'You already have registered your account.  Your account number is:',
    'es': '',
    'ja': '',
    'cn': '',
    'fr': '',
    'ge': '',
    'ru': '',
    'sv': ''
}

account_create_text = {
    'en': "You didn't have an account set up, so I set one up for you.  Your account number is:",
    'es': '',
    'ja': '',
    'cn': '',
    'fr': '',
    'ge': '',
    'ru': '',
    'sv': ''
}

account_text = {
    'en': 'Your account number is:',
    'es': '',
    'ja': '',
    'cn': '',
    'fr': '',
    'ge': '',
    'ru': '',
    'sv': ''
}

withdraw_no_account_text = {
    'en': 'You do not have an account.  Respond with !register to set one up.',
    'es': '',
    'ja': '',
    'cn': '',
    'fr': '',
    'ge': '',
    'ru': '',
    'sv': ''
}

invalid_account_text = {
    'en': 'The account number you provided is invalid.  Please double check and resend your request.',
    'es': '',
    'ja': '',
    'cn': '',
    'fr': '',
    'ge': '',
    'ru': '',
    'sv': ''
}


no_balance_text = {
    'en': 'You have 0 balance in your account.  Please deposit to your address {} to send more tips!',
    'es': '',
    'ja': '',
    'cn': '',
    'fr': '',
    'ge': '',
    'ru': '',
    'sv': ''
}

invalid_amount_text = {
    'en': 'You did not send a number to withdraw.  Please resend with the format !withdraw <account> or '
          '!withdraw <amount> <account>',
    'es': '',
    'ja': '',
    'cn': '',
    'fr': '',
    'ge': '',
    'ru': '',
    'sv': ''
}

not_enough_balance_text = {
    'en': 'You do not have that much NANO in your account.  To withdraw your full amount, send !withdraw <account>',
    'es': '',
    'ja': '',
    'cn': '',
    'fr': '',
    'ge': '',
    'ru': '',
    'sv': ''
}

withdraw_text = {
    'en': 'You have successfully withdrawn {} NANO!  You can check the transaction at '
          'https://nanocrawler.cc/explorer/block/{}',
    'es': '',
    'ja': '',
    'cn': '',
    'fr': '',
    'ge': '',
    'ru': '',
    'sv': ''
}

incorrect_withdraw_text = {
    'en': "I didn't understand your withdraw request.  Please resend with !withdraw <optional:amount> <account>.  "
          "Example, !withdraw 1 xrb_aigakjkfa343tm3h1kj would withdraw 1 NANO to account xrb_aigakjkfa343tm3h1kj.  "
          "Also, !withdraw xrb_aigakjkfa343tm3h1kj would withdraw your entire balance to account "
          "xrb_aigakjkfa343tm3h1kj.",
    'es': '',
    'ja': '',
    'cn': '',
    'fr': '',
    'ge': '',
    'ru': '',
    'sv': ''
}

wrong_donate_text = {
    'en': 'Only number amounts are accepted.  Please resend as !donate 1234',
    'es': '',
    'ja': '',
    'cn': '',
    'fr': '',
    'ge': '',
    'ru': '',
    'sv': ''
}

large_donate_text = {
    'en': 'Your balance is only {} NANO and you tried to send {}.  Please add more NANO to your account, or lower '
          'your donation amount.',
    'es': '',
    'ja': '',
    'cn': '',
    'fr': '',
    'ge': '',
    'ru': '',
    'sv': ''
}

small_donate_text = {
    'en': 'The minimum donation amount is {}.  Please update your donation amount and resend.',
    'es': '',
    'ja': '',
    'cn': '',
    'fr': '',
    'ge': '',
    'ru': '',
    'sv': ''
}

donate_text = {
    'en': 'Thank you for your generosity!  You have successfully donated {} NANO!  You can check the '
          'transaction at https://nanocrawler.cc/explorer/block/{}',
    'es': '',
    'ja': '',
    'cn': '',
    'fr': '',
    'ge': '',
    'ru': '',
    'sv': ''
}

incorrect_donate_text = {
    'en': 'Incorrect syntax.  Please use the format !donate 1234',
    'es': '',
    'ja': '',
    'cn': '',
    'fr': '',
    'ge': '',
    'ru': '',
    'sv': ''
}
