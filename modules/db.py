import configparser
import logging
import os
from datetime import datetime
from decimal import *

import MySQLdb

# Set Log File
logging.basicConfig(handlers=[logging.FileHandler('{}/webhooks.log'.format(os.getcwd()), 'a', 'utf-8')],
                    level=logging.INFO)

# Read config and parse constants
config = configparser.ConfigParser()
config.read('{}/webhookconfig.ini'.format(os.getcwd()))

# DB connection settings
DB_HOST = config.get('webhooks', 'host')
DB_USER = config.get('webhooks', 'user')
DB_PW = config.get('webhooks', 'password')
DB_SCHEMA = config.get('webhooks', 'schema')


def db_init():
    if not check_db_exist():
        create_db()
    create_tables()


def check_db_exist():
    db = MySQLdb.connect(host=DB_HOST, port=3306, user=DB_USER, passwd=DB_PW, use_unicode=True,
                         charset="utf8mb4")
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
    logging.info('Created database')


def check_table_exists(table_name):
    db = MySQLdb.connect(host=DB_HOST, port=3306, user=DB_USER, passwd=DB_PW, db=DB_SCHEMA, use_unicode=True,
                         charset="utf8mb4")
    db_cursor = db.cursor()
    sql = "SHOW TABLES LIKE '{}'".format(table_name)
    db_cursor.execute(sql)
    result = db_cursor.fetchall()
    return result


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
              PRIMARY KEY (`user_id`),
              UNIQUE KEY `user_id_UNIQUE` (`user_id`),
              UNIQUE KEY `account_UNIQUE` (`account`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """

            db_cursor.execute(sql)
            logging.info("Checking if users table was created: {}".format(
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
            logging.info("Checking if telegram_chat_members table was created: {}".format(
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
            logging.info("Checking if tip_list table was created: {}".format(
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
            logging.info("Checking if tip_list table was created: {}".format(
                check_table_exists('tip_list')))

        db.commit()
        db_cursor.close()
        db.close()
    except Exception as e:
            logging.info("Error creating tables for DB: {}".format(e))


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


def set_db_data(db_call, values):
    """
    Enter data into DB
    """
    db = MySQLdb.connect(host=DB_HOST, port=3306, user=DB_USER, passwd=DB_PW, db=DB_SCHEMA, use_unicode=True,
                         charset="utf8mb4")
    logging.info("db call: {}".format(db_call))
    logging.info("values: {}".format(values))
    try:
        db_cursor = db.cursor()
        db_cursor.execute(db_call, values)
        db.commit()
        db_cursor.close()
        db.close()
        logging.info("{}: record inserted into DB".format(datetime.now()))
        return None
    except MySQLdb.ProgrammingError as e:
        logging.info("{}: Exception entering data into database".format(datetime.now()))
        logging.info("{}: {}".format(datetime.now(), e))
        return e


def set_db_data_tip(message, users_to_tip, t_index):
    """
    Special case to update DB information to include tip data
    """
    logging.info("{}: inserting tip into DB.".format(datetime.now()))
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
        logging.info("{}: Exception in set_db_data_tip".format(datetime.now()))
        logging.info("{}: {}".format(datetime.now(), e))
        raise e
