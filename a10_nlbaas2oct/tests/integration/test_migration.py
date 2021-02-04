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

import copy
import sys
import unittest
from unittest import mock
from unittest.mock import patch

from oslo_db.sqlalchemy import enginefacade
from neutron_lbaas.db.loadbalancer import loadbalancer_dbv2 as lb_v2
from neutron_lbaas.services.loadbalancer import data_models

from a10_nlbaas2oct import driver
from a10_nlbaas2oct.tests.integration import constants

class MockContext(object):

    def __init__(self, session):
        self.session = session

class TestA10Migration(object):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_migrate_no_lb_one_thunder(self):
        pass

    def test_migrate_multi_lb_one_thunder(self):
        pass

class TestLBaaSAttributeMigration(object):
    """
        This integration test class is designed to check that various slb graphs are capable of being migrated.
        Each phase tests a different level of the full SLB object tree seen below:

                                      port
                                        |
                                       vip
                                        |
                                    loadbalancer
                                        |
                                    listeners
                                        |
                      ---------------------------------
                      |                 |             |
                     pools             SNIs        l7policies
                      |                               |
            -----------------------                 l7rules
            |         |           |
            hm      members    sess_pers

    Attribute sests are named as follows:

        test_migrate_<child_object>_<attribute>

    Example:

        test_migrate_member_weight

    This test would then assert that the member has the optional weight attribute.
    """
    pass

class TestLBaaSHierarchicalMigration(object):
    """
        This integration test class is designed to check that various slb graphs are capable of being migrated.
        Each phase tests a different level of the full SLB object tree seen below:

                                      port
                                        |
                                       vip
                                        |
                                    loadbalancer
                                        |
                                    listeners
                                        |
                      ---------------------------------
                      |                 |             |
                     pools             SNIs        l7policies
                      |                               |
            -----------------------                 l7rules
            |         |           |
            hm      members    sess_pers

    Hierarchical tests are named as follows:

        test_migrate_<parent_object>_<child_object>

    Example:

        test_migrate_pool_member

    This test would then assert that the pool is associated with the member and vice versa
    """

    def setUp(self):
        # TODO: Replace mock the load_config func with noop mock function. Ensure that it has a return val of 0
        # TODO: Load the oslo config in setUp so db sessions can be created
        # TODO: Create neutron and octavia context managers in setup
        # TODO: Mock the aten2oct migrate_thunder function
        # TODO: Mock the a10_config get_device function
        # TODO: Mock the aten2oct get_device_by_tenant function

        # test_args = [None, "--config-file", "~/a10-nlbaas2oct/a10_nlbaas2oct/a10_nlbaas2oct.conf", "--all"]
        # self.patched_sysargv = patch.object(sys, 'argv', test_args)

        # # Load the driver oslo config
        # driver.load_config(test_args)

        # # Mock out the A10 modules
        # driver.aten2oct = mock.Mock()
        # driver.a10_config = mock.Mock()

        # # Use driver oslo config to setup db sessions for tests
        # neutron_context_manager = enginefacade.transaction_context()
        # neutron_context_manager.configure(
        #     connection=driver.CONF.migration.neutron_db_connection)
        # self.n_session_maker = neutron_context_manager.writer.get_sessionmaker()

        # octavia_context_manager = enginefacade.transaction_context()
        # octavia_context_manager.configure(
        #     connection=driver.CONF.migration.octavia_db_connection)
        # self.o_session_maker = octavia_context_manager.writer.get_sessionmaker()
        pass

    def tearDown(self):
        # TODO: Use pre-existing cascade delete function for neutron db cleanup
        # TODO: Create a cascade delete function for octavia db cleanup
        pass

    def test_migrate_lb_and_vip(self):
        #from nose.tools import set_trace; set_trace()
        # TODO: Use constant to create LB (if custom vals are needed for more integration tests then create deep copy of constant and modify it)
        #lb = data_models.LoadBalancer.from_dict(copy.deepcopy(constants.LOADBALANCER))
        #n_session = self.n_session_maker(autocommit=False)
        #mock_ctx = MockContext(n_session)

        # TODO: Pass lb data model to create_loadbalancer_graph func. Let the create_lb func handle VIP allocation
        # https://github.com/openstack/neutron-lbaas/blob/stable/stein/neutron_lbaas/db/loadbalancer/loadbalancer_dbv2.py#L274
        # lb_v2.create_loadbalancer_graph(mock_ctx, lb)
        #lb_v2.LoadBalancerPluginDbv2().create_loadbalancer_graph(mock_ctx, copy.deepcopy(constants.LOADBALANCER))

        # TODO: Use the patched sys args as the context to call the main driver func
        # with self.patched_sysargv:
        #    driver.main()

        # TODO: Modify the lb data model to match the expected output for Octavia DB

        # TODO: Fetch the loadbalancer from the Octavia DB and check that it equals the lb data model
        pass

    # def test_migrate_listener(self):
    #     pass

    # def test_migrate_listener_sni(self):
    #     pass

    # def test_migrate_listener_l7policy(self):
    #     pass

    # def test_migrate_l7policy_l7rule(self):
    #     pass

    # def test_migrate_listener_pool(self):
    #     pass

    # def test_migrate_pool_hm(self):
    #     pass

    # def test_migrate_pool_sp(self):
    #     pass

    # def test_migrate_pool_member(self):
    #     pass
