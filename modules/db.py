import configparser
import logging
import os
from datetime import datetime
from decimal import *
from logging.handlers import TimedRotatingFileHandler

import modules.currency

import MySQLdb

# Set logging info
logger = logging.getLogger("db_log")
logger.setLevel(logging.INFO)
handler = TimedRotatingFileHandler('{}/logs/{:%Y-%m-%d}-db.log'.format(os.getcwd(), datetime.now()),
                                   when="d",
                                   interval=1,
                                   backupCount=5)
logger.addHandler(handler)

# Read config and parse constants
config = configparser.ConfigParser()
config.read('{}/webhookconfig.ini'.format(os.getcwd()))

# Check the currency of the bot
CURRENCY = config.get('main', 'currency')

# DB connection settings
DB_HOST = config.get('main', 'host')
DB_USER = config.get('main', 'user')
DB_PW = config.get('main', 'password')
DB_SCHEMA = config.get(CURRENCY, 'schema')


def db_init():
    if not check_db_exist():
        logger.info("db didn't exist: {}".format(DB_SCHEMA))
        create_db()
    logger.info("db did exist: {}".format(DB_SCHEMA))
    create_tables()
    create_triggers()


def check_db_exist():
    db = MySQLdb.connect(host=DB_HOST, port=3306, user=DB_USER, passwd=DB_PW, use_unicode=True,
                         charset="utf8mb4")
    logger.info("Checking if schema exists: {}".format(DB_SCHEMA))
    sql = "SHOW DATABASES LIKE '{}'".format(DB_SCHEMA)
    db_cursor = db.cursor()
    exists = db_cursor.execute(sql)
    db_cursor.close()
    db.close()

    return exists == 1


def create_db():
    db = MySQLdb.connect(host=DB_HOST, port=3306, user=DB_USER, passwd=DB_PW, use_unicode=True,
                         charset="utf8mb4")
    db_cursor = db.cursor()
    sql = 'CREATE DATABASE IF NOT EXISTS {}'.format(DB_SCHEMA)
    db_cursor.execute(sql)
    db.commit()
    db_cursor.close()
    db.close()
    logger.info('Created database')


def check_table_exists(table_name):
    db = MySQLdb.connect(host=DB_HOST, port=3306, user=DB_USER, passwd=DB_PW, db=DB_SCHEMA, use_unicode=True,
                         charset="utf8mb4")
    db_cursor = db.cursor()
    sql = "SHOW TABLES LIKE '{}'".format(table_name)
    db_cursor.execute(sql)
    result = db_cursor.fetchall()
    return result


def create_triggers():
    db = MySQLdb.connect(host=DB_HOST, port=3306, user=DB_USER, passwd=DB_PW, db=DB_SCHEMA, use_unicode=True,
                         charset="utf8mb4")
    db_cursor = db.cursor()
    db_cursor.execute("DROP TRIGGER IF EXISTS users_AFTER_INSERT;")
    db_cursor.execute("DROP TRIGGER IF EXISTS tip_list_AFTER_INSERT;")
    db_cursor.execute("DROP TRIGGER IF EXISTS dm_list_AFTER_INSERT;")
    user_trigger = """
                   CREATE TRIGGER `users_AFTER_INSERT` AFTER INSERT ON `users` FOR EACH ROW 
                   BEGIN 
                       INSERT INTO `languages` (`user_id`, `system`) 
                       VALUES (NEW.`user_id`, NEW.`system`);
                       INSERT INTO `return_address` (`user_id`, `system`, `last_action`) 
                       VALUES (NEW.`user_id`, NEW.`system`, now());
                       INSERT INTO `donation_info` (`user_id`, `system`)
                       VALUES (NEW.`user_id`, NEW.`system`);
                   END
                   """
    tip_list_trigger = """
                       CREATE DEFINER = CURRENT_USER TRIGGER `tip_list_AFTER_INSERT` AFTER INSERT ON `tip_list` FOR EACH ROW 
                       BEGIN 
                           UPDATE `return_address` SET `last_action` = now() 
                           WHERE `user_id` = new.`sender_id` 
                           AND `system` = new.`system`;
                       END
                       """
    dm_list_trigger = """
                      CREATE TRIGGER `dm_list_AFTER_INSERT` AFTER INSERT ON `dm_list` FOR EACH ROW 
                      BEGIN 
                          UPDATE `return_address` SET `last_action` = now() 
                          WHERE `user_id` = new.`sender_id` 
                          AND `system` = new.`system`;
                      END;
                      """

    db_cursor.execute(user_trigger)
    db_cursor.execute(tip_list_trigger)
    db_cursor.execute(dm_list_trigger)
    logger.info("Triggers set.")


def create_tables():
    db = MySQLdb.connect(host=DB_HOST, port=3306, user=DB_USER, passwd=DB_PW, db=DB_SCHEMA, use_unicode=True,
                         charset="utf8mb4")
    db_cursor = db.cursor()
    try:
        check_exists = check_table_exists('users')
        if not check_exists:
            # create users table
            sql = """
            CREATE TABLE IF NOT EXISTS `users` (
              `user_id` bigint(255) NOT NULL,
              `system` varchar(45) DEFAULT NULL,
              `user_name` varchar(100) DEFAULT NULL,
              `account` varchar(100) NOT NULL,
              `register` tinyint(1) NOT NULL DEFAULT '0',
              `created_ts` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
              `mute` tinyint(1) NOT NULL DEFAULT '0',
              PRIMARY KEY (`user_id`),
              UNIQUE KEY `user_id_UNIQUE` (`user_id`),
              UNIQUE KEY `account_UNIQUE` (`account`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """

            db_cursor.execute(sql)
            logger.info("Checking if users table was created: {}".format(
                check_table_exists('users')))

        check_exists = check_table_exists('telegram_chat_members')
        if not check_exists:
            # create telegram_chat_members table
            sql = """
            CREATE TABLE IF NOT EXISTS `telegram_chat_members` (
              `chat_id` bigint(100) NOT NULL,
              `chat_name` varchar(100) CHARACTER SET utf8mb4 NOT NULL,
              `member_id` bigint(100) NOT NULL,
              `member_name` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL,
              PRIMARY KEY (`chat_id`,`member_id`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """

            db_cursor.execute(sql)
            logger.info("Checking if telegram_chat_members table was created: {}".format(
                check_table_exists('telegram_chat_members')))

        check_exists = check_table_exists('tip_list')
        if not check_exists:
            # create tip_list table
            sql = """
            CREATE TABLE IF NOT EXISTS `tip_list` (
              `dm_id` bigint(255) NOT NULL,
              `tx_id` varchar(255) DEFAULT NULL,
              `processed` tinyint(1) DEFAULT NULL,
              `sender_id` bigint(255) NOT NULL,
              `receiver_id` bigint(255) NOT NULL,
              `system` varchar(45) DEFAULT NULL,
              `dm_text` text DEFAULT NULL,
              `amount` decimal(10,5) DEFAULT NULL,
              `timestamp` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
              PRIMARY KEY (`dm_id`,`sender_id`,`receiver_id`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """

            db_cursor.execute(sql)
            logger.info("Checking if tip_list table was created: {}".format(
                check_table_exists('tip_list')))

        check_exists = check_table_exists('dm_list')
        if not check_exists:
            # create dm_list table
            sql = """
            CREATE TABLE IF NOT EXISTS `dm_list` (
             `dm_id` bigint(255) NOT NULL,
             `tx_id` varchar(100) GENERATED ALWAYS AS (concat('tip-',`dm_id`)) STORED,
             `processed` tinyint(1) NOT NULL,
             `sender_id` bigint(255) NOT NULL,
             `receiver_id` bigint(255) DEFAULT NULL,
             `dm_text` text DEFAULT NULL,
             `amount` decimal(10,5) DEFAULT NULL,
             `dm_response` text DEFAULT NULL,
             `first_attempt` tinyint(1) DEFAULT '0',
             `timestamp` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
             PRIMARY KEY (`dm_id`),
             UNIQUE KEY `tx_id_UNIQUE` (`tx_id`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """
            db_cursor.execute(sql)
            logger.info("Checking if tip_list table was created: {}".format(
                check_table_exists('tip_list')))

        check_exists = check_table_exists('languages')
        if not check_exists:
            # create languages table
            sql = """
                   CREATE TABLE IF NOT EXISTS `languages` (
                     `user_id` bigint(255) NOT NULL,
                     `language_code` varchar(2) CHARACTER SET utf8mb4 NOT NULL DEFAULT 'en',
                     `system` varchar(45) CHARACTER SET utf8mb4 NOT NULL,
                     PRIMARY KEY (`user_id`),
                     UNIQUE KEY `user_id_UNIQUE` (`user_id`),
                     CONSTRAINT `user_key` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE NO ACTION ON UPDATE NO ACTION
                   ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                   """
            db_cursor.execute(sql)
            logger.info("Checking if languages table was created: {}".format(
                check_table_exists('languages')))

        check_exists = check_table_exists('return_address')
        if not check_exists:
            # create return_address table
            sql = """
                  CREATE TABLE IF NOT EXISTS `return_address` (
                    `user_id` bigint(255) NOT NULL,
                    `system` varchar(45) NOT NULL,
                    `account` varchar(100) DEFAULT NULL,
                    `last_action` datetime DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (`user_id`,`system`)
                  ) ENGINE=InnoDB DEFAULT CHARSET=latin1;
                   """
            db_cursor.execute(sql)
            logger.info("Checking if return_address table was created: {}".format(
                check_table_exists('return_address')))

        check_exists = check_table_exists('spare_accounts')
        if not check_exists:
            # create spare_accounts table
            sql= """
            CREATE TABLE IF NOT EXISTS `spare_accounts` (
             `account` varchar(100) NOT NULL,
             PRIMARY KEY (`account`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
            db_cursor.execute(sql)
            logger.info("Checking if spare_accounts table was created: {}".format(
                check_table_exists('spare_accounts')))

        db.commit()
        db_cursor.close()
        db.close()
    except Exception as e:
        logger.info("Error creating tables for DB: {}".format(e))


def get_db_data(db_call):
    """
    Retrieve data from DB
    """
    db = MySQLdb.connect(host=DB_HOST, port=3306, user=DB_USER, passwd=DB_PW, db=DB_SCHEMA, use_unicode=True,
                         charset="utf8mb4")
    db_cursor = db.cursor()
    db_cursor.execute(db_call)
    db_data = db_cursor.fetchall()
    db_cursor.close()
    db.close()
    return db_data


def get_db_data_new(db_call, values):
    """
    Retrieve data from DB
    """
    db = MySQLdb.connect(host=DB_HOST, port=3306, user=DB_USER, passwd=DB_PW, db=DB_SCHEMA, use_unicode=True,
                         charset="utf8mb4")
    db_cursor = db.cursor()
    db_cursor.execute(db_call, values)
    db_data = db_cursor.fetchall()
    db_cursor.close()
    db.close()
    return db_data


def set_db_data(db_call, values):
    """
    Enter data into DB
    """
    db = MySQLdb.connect(host=DB_HOST, port=3306, user=DB_USER, passwd=DB_PW, db=DB_SCHEMA, use_unicode=True,
                         charset="utf8mb4")
    try:
        db_cursor = db.cursor()
        db_cursor.execute(db_call, values)
        db.commit()
        db_cursor.close()
        db.close()
        logger.info("{}: record inserted into DB".format(datetime.now()))
        return None
    except MySQLdb.ProgrammingError as e:
        logger.info("{}: Exception entering data into database".format(datetime.now()))
        logger.info("{}: {}".format(datetime.now(), e))
        return e


def set_db_data_tip(message, users_to_tip, t_index):
    """
    Special case to update DB information to include tip data
    """
    logger.info("{}: inserting tip into DB.".format(datetime.now()))
    db = MySQLdb.connect(host=DB_HOST, port=3306, user=DB_USER, passwd=DB_PW, db=DB_SCHEMA, use_unicode=True,
                         charset="utf8mb4")
    try:
        db_cursor = db.cursor()
        db_cursor.execute(
            "INSERT INTO tip_list (dm_id, tx_id, processed, sender_id, receiver_id, system, dm_text, amount)"
            " VALUES (%s, %s, 2, %s, %s, %s, %s, %s)",
            (message['id'], message['tip_id'], message['sender_id'],
             users_to_tip[t_index]['receiver_id'], message['system'], message['text'],
             Decimal(message['tip_amount'])))
        db.commit()
        db_cursor.close()
        db.close()
    except Exception as e:
        logger.info("{}: Exception in set_db_data_tip".format(datetime.now()))
        logger.info("{}: {}".format(datetime.now(), e))
        raise e


def set_spare_accounts(accounts):
    """
    Set DB with spare accounts.
    """
    insert_accounts_call = "INSERT INTO {}.spare_accounts (account) VALUES ".format(DB_SCHEMA)

    try:
        for index, account in enumerate(accounts):
            if index == 0:
                insert_accounts_call += "(%s)"
            else:
                insert_accounts_call += ", (%s)"
        insert_accounts_call += ';'
        logger.info("insert accounts call: {}".format(insert_accounts_call))
        set_db_data(insert_accounts_call, accounts)

    except Exception as e:
        logger.info("Error inserting spare accounts: {}".format(e))

    logger.info("New accounts set in DB.")


def get_spare_account():
    """
    Retrieve an account from the database.
    """
    check_accounts_call = "SELECT count(account) FROM {}.spare_accounts;".format(DB_SCHEMA)
    check_accounts_return = get_db_data(check_accounts_call)
    if int(check_accounts_return[0][0]) <= 5:
        accounts = modules.currency.generate_accounts()
        set_spare_accounts(accounts)

    get_account_call = "SELECT account FROM {}.spare_accounts LIMIT 1;".format(DB_SCHEMA)
    spare_account_return = get_db_data(get_account_call)

    remove_account_call = "DELETE FROM {}.spare_accounts WHERE account = %s".format(DB_SCHEMA)
    set_db_data(remove_account_call, spare_account_return[0])

    return spare_account_return[0][0]
