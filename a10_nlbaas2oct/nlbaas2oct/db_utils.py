def lock_loadbalancer(n_session, lb_id):
    # Lock the load balancer in neutron DB
    result = n_session.execute(
        "UPDATE lbaas_loadbalancers SET "
        "provisioning_status = 'PENDING_UPDATE' WHERE id = :id AND "
        "provisioning_status = 'ACTIVE';", {'id': lb_id})
    if result.rowcount != 1:
        raise Exception(_('Load balancer is not provisioning_status '
                        'ACTIVE'))

def get_loadbalancery_entry(n_session, lb_id):
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

def get_SNIs_by_listener(listener_id):
    SNIs = n_session.execute(
        "SELECT tls_container_id, position FROM lbaas_sni WHERE "
        "listener_id = :listener_id;", {'listener_id': listener_id}).fetchall()
    return SNIs

def get_l7policies_by_listner(listener_id):
    l7policies = n_session.execute(
        "SELECT id, name, description, listener_id, action, "
        "redirect_pool_id, redirect_url, position, "
        "provisioning_status, admin_state_up FROM "
        "lbaas_l7policies WHERE listener_id = :listener_id AND "
        "provisioning_status = 'ACTIVE';",
        {'listener_id': listener_id}).fetchall()
    return l7polcies

def get_l7rules_by_l7policy(l7policy_id):
    l7rules = n_session.execute(
        "SELECT id, type, compare_type, invert, `key`, value, "
        "provisioning_status, admin_state_up FROM lbaas_l7rules WHERE "
        "l7policy_id = :l7policy_id AND provisioning_status = 'ACTIVE';",
        {'l7policy_id': l7policy_id}).fetchall()
    return l7rules

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