# Copyright 2020 A10 Networks, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

# import abc
# import mysql.connector
# from mysql.connector import errorcode
# from mock import patch
# import unittest
# import utils


# class MockDBBase(abc.ABCMeta):

#     # @abc.abstractmethod
#     # def _build_tables(self):
#     #     pass

#     def __init__(self, db, host, user, passwd, port):
#         self.db = db
#         self.host = host
#         self.user = user
#         self.passwd = passwd
#         self.port = port

#     def setUp(self):

#         cnx = mysql.connector.connect(
#             host=self.host,
#             user=self.user,
#             password=self.passwd,
#             port=self.port
#         )
#         cursor = cnx.cursor(dictionary=True)

#         try:
#             cursor.execute("DROP DATABASE {}".format(db))
#             cursor.close()
#             print("DB dropped")
#         except mysql.connector.Error as err:
#             print("{}{}".format(db, err))

#         cursor = cnx.cursor(dictionary=True)
#         try:
#             cursor.execute(
#                 "CREATE DATABASE {} DEFAULT CHARACTER SET 'utf8'".format(db))
#         except mysql.connector.Error as err:
#             print("Failed creating database: {}".format(err))
#             exit(1)

#         cursor.close()
#         cnx.close()

#     def tearDown(self):
#         cnx = mysql.connector.connect(
#             host=self.host,
#             user=self.user,
#             password=self.passwd,
#             port=self.port
#         )
#         cursor = cnx.cursor(dictionary=True)

#         try:
#             cursor.execute("DROP DATABASE {}".format(self.db))
#             cnx.commit()
#             cursor.close()
#         except mysql.connector.Error as err:
#             print("Database {} does not exists. Dropping db failed".format(self.db))
#         cnx.close()


# class MockNeutronDB(MockDBBase):

#     def _build_tables(self):

#         cnx = mysql.connector.connect(
#             host=self.host,
#             user=self.user,
#             password=self.passwd,
#             port=self.port
#         )
#         cursor = cnx.cursor(dictionary=True)

#         query = """CREATE TABLE `lbaas_loadbalancers` (
#                   `id` varchar(30) NOT NULL PRIMARY KEY ,
#                   `text` text NOT NULL,
#                   `int` int NOT NULL
#                 )"""
#         try:
#             cursor.execute(query)
#             cnx.commit()
#         except mysql.connector.Error as err:
#             if err.errno == errorcode.ER_TABLE_EXISTS_ERROR:
#                 print("test_table already exists.")
#             else:
#                 print(err.msg)
#         else:
#             print("OK")


# class MockOctaviaDB(MockDBBase):

#     def build_tables(self):
#         query = """CREATE TABLE `test_table` (
#                   `id` varchar(30) NOT NULL PRIMARY KEY ,
#                   `text` text NOT NULL,
#                   `int` int NOT NULL
#                 )"""
#         try:
#             cursor.execute(query)
#             cnx.commit()
#         except mysql.connector.Error as err:
#             if err.errno == errorcode.ER_TABLE_EXISTS_ERROR:
#                 print("test_table already exists.")
#             else:
#                 print(err.msg)
#         else:
#             print("OK")