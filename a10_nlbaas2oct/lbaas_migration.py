# Copyright 2018 Rackspace, US Inc.
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

import datetime
import sys

from oslo_db.sqlalchemy import enginefacade
import oslo_i18n as i18n
from oslo_log import log as logging

from a10_nlbaas2oct import db_utils


def migrate_vip_ports(n_session, oct_accnt_id, lb_id, n_lb):

    # Migrate the port and security groups to Octavia
    vip_port = n_session.execute(
        "SELECT a.device_owner, a.project_id, b.security_group_id "
        "FROM ports a JOIN securitygroupportbindings b ON "
        "a.id = b.port_id  where id = :id;",
        {'id': n_lb[7]}).fetchone()
    # neutron-lbaas does not support user VIP ports, so take
    # ownership of the port and security group
    if vip_port[0] == 'neutron:LOADBALANCERV2':
        result = n_session.execute(
            "UPDATE ports SET device_owner = 'Octavia', "
            "project_id = :proj_id WHERE "
            "id = :id;", {'id': n_lb[7],
                          'proj_id': oct_accnt_id})
        if result.rowcount != 1:
            raise Exception(_('Unable to update VIP port in the neutron '
                            'database.'))
        security_group = n_session.execute(
            "SELECT project_id FROM securitygroups WHERE id = :id",
            {'id': vip_port[2]}).fetchone()
        # Update security group project, only when its owner is not the
        # user project, which means that Octavia should own it
        if security_group[0] != n_lb[1]:
            result = n_session.execute(
                "UPDATE securitygroups SET project_id = :proj_id WHERE "
                "id = :id;", {'proj_id': oct_accnt_id,
                              'id': vip_port[2]})
            if result.rowcount != 1:
                raise Exception(_('Unable to update VIP security group in '
                                  'the neutron database.'))

def migrate_lb(o_session, lb_id, n_lb, fl_id):
    """ 
        Create the load balancer. Provider name is hardcoded.
        This tool is only meant for A10 LB migration. On nlbaas the provider is 'a10networks'
        but on octavia the provider is 'a10'
    """
    provider_name = "a10"

    result = o_session.execute(
        "INSERT INTO load_balancer (id, project_id, name, "
        "description, provisioning_status, operating_status, enabled, "
        "created_at, updated_at, flavor_id, provider) VALUES (:id, :project_id, "
        ":name, :description, :provisioning_status, "
        ":operating_status, :enabled, :created_at, :updated_at, "
        ":flavor_id, :provider);",
        {'id': lb_id, 'project_id': n_lb[1], 'name': n_lb[2],
         'description': n_lb[3], 'provisioning_status': 'ACTIVE',
         'operating_status': n_lb[5], 'enabled': n_lb[4],
         'created_at': datetime.datetime.utcnow(),
         'updated_at': datetime.datetime.utcnow(),
         'flavor_id': fl_id, 'provider': provider_name,})
    if result.rowcount != 1:
          raise Exception(_('Unable to create load balancer in the '
                          'Octavia database.'))


def migrate_vip(n_session, o_session, lb_id, n_lb):
    # Get the network ID for the VIP
    subnet = n_session.execute(
        "SELECT network_id FROM subnets WHERE id = :id;",
        {'id': n_lb[8]}).fetchone()
    # Create VIP record
    result = o_session.execute(
        "INSERT INTO vip (load_balancer_id, ip_address, port_id, "
        "subnet_id, network_id) VALUES (:lb_id, :ip_address, "
        ":port_id, :subnet_id, :network_id);",
        {'lb_id': lb_id, 'ip_address': n_lb[9], 'port_id': n_lb[7],
         'subnet_id': n_lb[8], 'network_id': subnet[0]})
    if result.rowcount != 1:
        raise Exception(_('Unable to create VIP in the Octavia '
                        'database.'))


def migrate_listener(n_session, o_session, lb_id, n_lb, listener, lb_stats):
    # Create listener
    result = o_session.execute(
        "INSERT INTO listener (id, project_id, name, description, "
        "protocol, protocol_port, connection_limit, "
        "load_balancer_id, tls_certificate_id, default_pool_id, "
        "provisioning_status, operating_status, enabled, "
        "created_at, updated_at) VALUES (:id, :project_id, :name, "
        ":description, :protocol, :protocol_port, "
        ":connection_limit, :load_balancer_id, "
        ":tls_certificate_id, :default_pool_id, "
        ":provisioning_status, :operating_status, :enabled, "
        ":created_at, :updated_at);",
        {'id': listener[0], 'project_id': n_lb[1],
         'name': listener[1], 'description': listener[2],
         'protocol': listener[3], 'protocol_port': listener[4],
         'connection_limit': listener[5],
         'load_balancer_id': lb_id,
         'tls_certificate_id': listener[10],
         'default_pool_id': listener[6],
         'provisioning_status': listener[8],
         'operating_status': listener[9], 'enabled': listener[7],
         'created_at': datetime.datetime.utcnow(),
         'updated_at': datetime.datetime.utcnow()})
    if result.rowcount != 1:
        raise Exception(_('Unable to create listener in the '
                        'Octavia database.'))
    # Convert load balancer stats to listener stats
    # This conversion may error on the low side due to
    # the division
    listeners, lb_stats = db_utils.get_listeners_and_stats_by_lb(n_session, lb_id)
    result = o_session.execute(
        "INSERT INTO listener_statistics (listener_id, bytes_in, "
        "bytes_out, active_connections, total_connections, "
        "amphora_id, request_errors) VALUES (:listener_id, "
        ":bytes_in, :bytes_out, :active_connections, "
        ":total_connections, :amphora_id, :request_errors);",
        {'listener_id': listener[0],
         'bytes_in': int(lb_stats[0] / len(listeners)),
         'bytes_out': int(lb_stats[1] / len(listeners)),
         'active_connections': int(lb_stats[2] / len(listeners)),
         'total_connections': int(lb_stats[3] / len(listeners)),
         'amphora_id': listener[0], 'request_errors': 0})
    if result.rowcount != 1:
        raise Exception(_('Unable to create listener statistics '
                        'in the Octavia database.'))


def migrate_SNI(o_session, listener_id, SNI):
    # Create SNI containers
    result = o_session.execute(
        "INSERT INTO sni (listener_id, tls_container_id, position) VALUES "
        "(:listener_id, :tls_container_id, :position);",
        {'listener_id': listener_id, 'tls_container_id': SNI[0],
            'position': SNI[1]})
    if result.rowcount != 1:
        raise Exception(_('Unable to create SNI record in the Octavia '
                        'database.'))


def migrate_l7policy(o_session, project_id, listener_id, l7policy):
        # Create L7 Policies
        L7p_op_status = 'ONLINE' if l7policy[9] else 'OFFLINE'
        result = o_session.execute(
            "INSERT INTO l7policy (id, name, description, listener_id, "
            "action, redirect_pool_id, redirect_url, position, enabled, "
            "provisioning_status, created_at, updated_at, project_id, "
            "operating_status) VALUES (:id, :name, :description, "
            ":listener_id, :action, :redirect_pool_id, :redirect_url, "
            ":position, :enabled, :provisioning_status, :created_at, "
            ":updated_at, :project_id, :operating_status);",
            {'id': l7policy[0], 'name': l7policy[1],
             'description': l7policy[2], 'listener_id': listener_id,
             'action': l7policy[4], 'redirect_pool_id': l7policy[5],
             'redirect_url': l7policy[6], 'position': l7policy[7],
             'enabled': l7policy[9], 'provisioning_status': l7policy[8],
             'created_at': datetime.datetime.utcnow(),
             'updated_at': datetime.datetime.utcnow(),
             'project_id': project_id, 'operating_status': L7p_op_status})
        if result.rowcount != 1:
            raise Exception(_('Unable to create L7 policy in the Octavia '
                            'database.'))


def migrate_l7rule(o_session, project_id, l7policy, l7rule):
    # Create L7rule
    L7r_op_status = 'ONLINE' if l7rule[7] else 'OFFLINE'
    result = o_session.execute(
        "INSERT INTO l7rule (id, l7policy_id, type, compare_type, "
        "`key`, value, invert, provisioning_status, created_at, "
        "updated_at, project_id, enabled, operating_status) VALUES "
        "(:id, :l7policy_id, :type, :compare_type, :key, :value, "
        ":invert, :provisioning_status, :created_at, :updated_at, "
        ":project_id, :enabled, :operating_status);",
        {'id': l7rule[0], 'l7policy_id': l7policy[0],
         'type': l7rule[1], 'compare_type': l7rule[2],
         'key': l7rule[4], 'value': l7rule[5], 'invert': l7rule[3],
         'provisioning_status': l7rule[6],
         'created_at': datetime.datetime.utcnow(),
         'updated_at': datetime.datetime.utcnow(),
         'project_id': project_id, 'enabled': l7rule[7],
         'operating_status': L7r_op_status})
    if result.rowcount != 1:
        raise Exception(_('Unable to create L7 policy in the Octavia '
                        'database.'))

def migrate_pools(o_session, lb_id, n_lb, pool):
    # Create pools
    result = o_session.execute(
        "INSERT INTO pool (id, project_id, name, description, "
        "protocol, lb_algorithm, operating_status, enabled, "
        "load_balancer_id, created_at, updated_at, "
        "provisioning_status) VALUES (:id, :project_id, :name, "
        ":description, :protocol, :lb_algorithm, "
        ":operating_status, :enabled, :load_balancer_id,"
        ":created_at, :updated_at, :provisioning_status);",
        {'id': pool[0], 'project_id': n_lb[1], 'name': pool[1],
         'description': pool[2], 'protocol': pool[3],
         'lb_algorithm': pool[4], 'operating_status': pool[8],
         'enabled': pool[6], 'load_balancer_id': lb_id,
         'created_at': datetime.datetime.utcnow(),
         'updated_at': datetime.datetime.utcnow(),
         'provisioning_status': pool[7]})
    if result.rowcount != 1:
        raise Exception(_('Unable to create pool in the '
                        'Octavia database.'))


def migrate_health_monitor(o_session, project_id, pool_id, hm_id, hm):
    # Create health monitor

    hm_op_status = 'ONLINE' if hm[7] else 'OFFLINE'

    result = o_session.execute(
        "INSERT INTO health_monitor (id, project_id, pool_id, type, delay, "
        "timeout, fall_threshold, rise_threshold, http_method, url_path, "
        "expected_codes, enabled, provisioning_status, name, created_at, "
        "updated_at, operating_status) VALUES (:id, :project_id, :pool_id, "
        ":type, :delay, :timeout, :fall_threshold, :rise_threshold, "
        ":http_method, :url_path, :expected_codes, :enabled, "
        ":provisioning_status, :name, :created_at, :updated_at, "
        ":operating_status);",
        {'id': hm_id, 'project_id': project_id, 'pool_id': pool_id,
         'type': hm[0], 'delay': hm[1], 'timeout': hm[2],
         'fall_threshold': hm[10], 'rise_threshold': hm[3],
         'http_method': hm[4], 'url_path': hm[5], 'expected_codes': hm[6],
         'enabled': hm[7], 'provisioning_status': hm[8], 'name': hm[9],
         'operating_status': hm_op_status,
         'created_at': datetime.datetime.utcnow(),
         'updated_at': datetime.datetime.utcnow()})
    if result.rowcount != 1:
        raise Exception(_('Unable to create health monitor in the Octavia '
                        'database.'))


def migrate_session_persistence(o_session, pool_id, sp):
    # Setup session persistence if it is configured
    result = o_session.execute(
        "INSERT INTO session_persistence (pool_id, type, cookie_name) "
        "VALUES (:pool_id, :type, :cookie_name);",
        {'pool_id': pool_id, 'type': sp[0], 'cookie_name': sp[1]})
    if result.rowcount != 1:
        raise Exception(_('Unable to create session persistence in the '
                        'Octavia database.'))


def migrate_member(o_session, project_id, pool_id, member):
    # Create member
    result = o_session.execute(
        "INSERT INTO member (id, pool_id, project_id, subnet_id, "
        "ip_address, protocol_port, weight, operating_status, enabled, "
        "created_at, updated_at, provisioning_status, name, backup) "
        "VALUES (:id, :pool_id, :project_id, :subnet_id, :ip_address, "
        ":protocol_port, :weight, :operating_status, :enabled, "
        ":created_at, :updated_at, :provisioning_status, :name, :backup);",
        {'id': member[0], 'pool_id': pool_id, 'project_id': project_id,
         'subnet_id': member[1], 'ip_address': member[2],
         'protocol_port': member[3], 'weight': member[4],
         'operating_status': member[7], 'enabled': member[5],
         'created_at': datetime.datetime.utcnow(),
         'updated_at': datetime.datetime.utcnow(),
         'provisioning_status': member[6], 'name': member[8],
         'backup': False})
    if result.rowcount != 1:
        raise Exception(
            _('Unable to create member in the Octavia database.'))
