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

def lock_loadbalancer(n_session, lb_id):
    # Lock the load balancer in neutron DB
    result = n_session.execute(
        "UPDATE lbaas_loadbalancers SET "
        "provisioning_status = 'PENDING_UPDATE' WHERE id = :id AND "
        "provisioning_status = 'ACTIVE';", {'id': lb_id})
    if result.rowcount != 1:
        raise Exception(_('Load balancer is not provisioning_status '
                        'ACTIVE'))

def unlock_loadbalancer(n_session, lb_id):
    # Unlock the load balancer in neutron DB
    result = n_session.execute(
        "UPDATE lbaas_loadbalancers SET "
        "provisioning_status = 'ACTIVE' WHERE id = :id AND "
        "provisioning_status = 'PENDING_UPDATE';", {'id': lb_id})

def get_loadbalancer_ids(n_session, conf_lb_id=None, conf_project_id=None):
    lb_id_list = []
    if conf_lb_id:
        lb_id = n_session.execute(
            "SELECT id FROM neutron.lbaas_loadbalancers WHERE "
            "id = :id AND provisioning_status = 'ACTIVE';",
            {'id': conf_lb_id}).fetchall()
        if not lb_id:
            error_msg = ('Loadbalancer with ID {} could not be found. '
                         'Please ensure you are using the UUID '
                         'instead of the name.').format(conf_lb_id)
            raise Exception(_(error_msg))
        lb_id_list = lb_id
    elif conf_project_id:
        lb_id_list = n_session.execute(
            "SELECT id FROM neutron.lbaas_loadbalancers WHERE "
            "project_id = :id AND provisioning_status = 'ACTIVE';",
            {'id': conf_project_id}).fetchall()
    else:  # CONF.ALL
        lb_id_list = n_session.execute(
            "SELECT id FROM neutron.lbaas_loadbalancers WHERE "
            "provisioning_status = 'ACTIVE';").fetchall()
    return lb_id_list

def get_loadbalancer_entry(n_session, lb_id):
    # Get the load balancer record from neutron
    n_lb = n_session.execute(
        "SELECT b.provider_name, a.project_id, a.name, a.description, "
        "a.admin_state_up, a.operating_status, a.flavor_id, "
        "a.vip_port_id, a.vip_subnet_id, a.vip_address "
        "FROM lbaas_loadbalancers a JOIN providerresourceassociations b "
        "ON a.id = b.resource_id WHERE ID = :id;",
        {'id': lb_id}).fetchone()
    return n_lb

def get_listeners_and_stats_by_lb(n_session, lb_id):
    lb_stats = n_session.execute(
        "SELECT bytes_in, bytes_out, active_connections, "
        "total_connections FROM lbaas_loadbalancer_statistics WHERE "
        "loadbalancer_id = :lb_id;", {'lb_id': lb_id}).fetchone()

    listeners = n_session.execute(
        "SELECT id, name, description, protocol, protocol_port, "
        "connection_limit, default_pool_id, admin_state_up, "
        "provisioning_status, operating_status, "
        "default_tls_container_id FROM lbaas_listeners WHERE "
        "loadbalancer_id = :lb_id;", {'lb_id': lb_id}).fetchall()
    return listeners, lb_stats

def get_SNIs_by_listener(n_session, listener_id):
    SNIs = n_session.execute(
        "SELECT tls_container_id, position FROM lbaas_sni WHERE "
        "listener_id = :listener_id;", {'listener_id': listener_id}).fetchall()
    return SNIs

def get_l7policies_by_listener(n_session, listener_id):
    l7policies = n_session.execute(
        "SELECT id, name, description, listener_id, action, "
        "redirect_pool_id, redirect_url, position, "
        "provisioning_status, admin_state_up FROM "
        "lbaas_l7policies WHERE listener_id = :listener_id AND "
        "provisioning_status = 'ACTIVE';",
        {'listener_id': listener_id}).fetchall()
    return l7policies

def get_l7rules_by_l7policy(n_session, l7policy_id):
    l7rules = n_session.execute(
        "SELECT id, type, compare_type, invert, `key`, value, "
        "provisioning_status, admin_state_up FROM lbaas_l7rules WHERE "
        "l7policy_id = :l7policy_id AND provisioning_status = 'ACTIVE';",
        {'l7policy_id': l7policy_id}).fetchall()
    return l7rules

def get_pool_entries_by_lb(n_session, lb_id):
    pools = n_session.execute(
        "SELECT id, name, description, protocol, lb_algorithm, "
        "healthmonitor_id, admin_state_up, provisioning_status, "
        "operating_status FROM lbaas_pools WHERE loadbalancer_id "
        " = :lb_id;",
        {'lb_id': lb_id}).fetchall()
    return pools

def get_sess_pers_by_pool(n_session, pool_id):
    sp = n_session.execute(
        "SELECT type, cookie_name FROM lbaas_sessionpersistences "
        "WHERE pool_id = :pool_id;", {'pool_id': pool_id}).fetchone()
    return sp

def get_members_by_pool(n_session, pool_id):
    members = n_session.execute(
        "SELECT id, subnet_id, address, protocol_port, weight, "
        "admin_state_up, provisioning_status, operating_status, name FROM "
        "lbaas_members WHERE pool_id = :pool_id;",
        {'pool_id': pool_id}).fetchall()
    return members

def get_healthmonitor(n_session, hm_id):
    hm = n_session.execute(
        "SELECT type, delay, timeout, max_retries, http_method, url_path, "
        "expected_codes, admin_state_up, provisioning_status, name, "
        "max_retries_down FROM lbaas_healthmonitors WHERE id = :hm_id AND "
        "provisioning_status = 'ACTIVE';", {'hm_id': hm_id}).fetchone()

    if hm is None:
        raise Exception(_('Health monitor %s has invalid '
                        'provisioning_status.'), hm_id)
    return hm

def cascade_delete_neutron_lb(n_session, lb_id):
    listeners = n_session.execute(
        "SELECT id FROM lbaas_listeners WHERE loadbalancer_id = :lb_id;",
        {'lb_id': lb_id})
    for listener in listeners:
        l7policies = n_session.execute(
            "SELECT id FROM lbaas_l7policies WHERE listener_id = :list_id;",
            {'list_id': listener[0]})
        for l7policy in l7policies:
            # Delete l7rules
            n_session.execute(
                "DELETE FROM lbaas_l7rules WHERE l7policy_id = :l7p_id;",
                {'l7p_id': l7policy[0]})
        # Delete l7policies
        n_session.execute(
            "DELETE FROM lbaas_l7policies WHERE listener_id = :list_id;",
            {'list_id': listener[0]})
        # Delete SNI records
        n_session.execute(
            "DELETE FROM lbaas_sni WHERE listener_id = :list_id;",
            {'list_id': listener[0]})

    # Delete the listeners
    n_session.execute(
        "DELETE FROM lbaas_listeners WHERE loadbalancer_id = :lb_id;",
        {'lb_id': lb_id})

    pools = n_session.execute(
        "SELECT id, healthmonitor_id FROM lbaas_pools "
        "WHERE loadbalancer_id = :lb_id;", {'lb_id': lb_id}).fetchall()
    for pool in pools:
        # Delete the members
        n_session.execute(
            "DELETE FROM lbaas_members WHERE pool_id = :pool_id;",
            {'pool_id': pool[0]})
        # Delete the session persistence records
        n_session.execute(
            "DELETE FROM lbaas_sessionpersistences WHERE pool_id = :pool_id;",
            {'pool_id': pool[0]})

        # Delete the pools
        n_session.execute(
            "DELETE FROM lbaas_pools WHERE id = :pool_id;",
            {'pool_id': pool[0]})

        # Delete the health monitor
        if pool[1]:
            result = n_session.execute("DELETE FROM lbaas_healthmonitors "
                                       "WHERE id = :id", {'id': pool[1]})
            if result.rowcount != 1:
                raise Exception(_('Failed to delete health monitor: '
                                '%s') % pool[1])
    # Delete the lb stats
    n_session.execute(
        "DELETE FROM lbaas_loadbalancer_statistics WHERE "
        "loadbalancer_id = :lb_id;", {'lb_id': lb_id})

    # Delete provider record
    n_session.execute(
        "DELETE FROM providerresourceassociations WHERE "
        "resource_id = :lb_id;", {'lb_id': lb_id})

    # Delete the load balanacer
    n_session.execute(
        "DELETE FROM lbaas_loadbalancers WHERE id = :lb_id;", {'lb_id': lb_id})
