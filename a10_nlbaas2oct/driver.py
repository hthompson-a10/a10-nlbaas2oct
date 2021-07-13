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

import sys

from oslo_config import cfg
from oslo_db.sqlalchemy import enginefacade
import oslo_i18n as i18n
from oslo_log import log as logging
from six.moves import input

import acos_client
from a10_nlbaas2oct import a10_config as a10_cfg
from a10_nlbaas2oct import a10_migration as aten2oct
from a10_nlbaas2oct import db_utils
from a10_nlbaas2oct import flavor_migration as nexpr2fl
from a10_nlbaas2oct import lbaas_migration as lb2oct

_translators = i18n.TranslatorFactory(domain='a10_nlbaas2oct')

# The primary translation function using the well-known name "_"
_ = _translators.primary

CONF = cfg.CONF

cli_opts = [
    cfg.BoolOpt('all', default=False,
                help='Migrate all load balancers'),
    cfg.StrOpt('lb-id',
               help='Load balancer ID to migrate'),
    cfg.StrOpt('project-id',
               help='Migrate all load balancers owned by this project'),
    cfg.BoolOpt('cleanup', default=False,
               help='Delete Neutron LBaaS db entries'),
]

migration_opts = [
    cfg.BoolOpt('delete_after_migration', default=False,
                help='Delete the load balancer records from neutron-lbaas'
                     ' after migration'),
    cfg.ListOpt('lb_id_list',
                help='List of loadbalancer id\'s to migrate'),
    cfg.BoolOpt('trial_run', default=False,
                help='Run without making changes.'),
    cfg.StrOpt('octavia_account_id', required=True,
               help='The keystone account ID Octavia is running under.'),
    cfg.StrOpt('neutron_db_connection',
               required=True,
               help='The neutron database connection string'),
    cfg.StrOpt('octavia_db_connection',
               required=True,
               help='The octavia database connection string'),
    cfg.StrOpt('keystone_db_connection',
               required=False,
               help='The keystone database connection string'),
    cfg.StrOpt('a10_nlbaas_db_connection',
               required=False,
               help='The a10 nlbaas database connection string'),
    cfg.StrOpt('a10_oct_db_connection',
               required=False,
               help='The a10 octavia database connection string'),
    cfg.StrOpt('a10_config_path',
               required=True,
               help='Path to config.py file used by the A10 networks lbaas driver'),
    cfg.StrOpt('provider_name', default='a10networks',
                required=True,
                help='Name of LBaaS service provider')
]

cfg.CONF.register_cli_opts(cli_opts)
cfg.CONF.register_opts(migration_opts, group='migration')


def _migrate_flavor(LOG, a10_config, o_session, device_name):
    # Translate the name expressions into an Octavia flavor
    LOG.info('Migrating name expressions to flavors')
    fl_id = None
    try:
        flavor_data = nexpr2fl.create_flavor_data(a10_config, device_name)
        if flavor_data:
            fp_id = nexpr2fl.create_flavorprofile(o_session, flavor_data)
            fl_id = nexpr2fl.create_flavor(o_session, fp_id)
    except Exception as e:
        LOG.exception("Skipping flavor migration due to: %s.", str(e))
        raise Exception
    return fl_id


def _migrate_device(LOG, a10_config, db_sessions, lb_id, tenant_id):
    if a10_config.get('use_database'):
        entry_name = aten2oct.get_device_name_by_tenant(db_sessions['a10_nlbaas_session'], tenant_id)
    else:
        devices = a10_config.get('devices')
        entry_name = acos_client.Hash(list(devices)).get_server(tenant_id)
    
    device_info = a10_config.get_device(entry_name)
    device_name = device_info.get('name')
    LOG.info('Migrating Thunder config entry %s with name %s',
             entry_name, device_name)
    use_parent = a10_config.get('use_parent_project')

    try:
        k_session = db_sessions.get('k_session')
        aten2oct.migrate_thunder(db_sessions['a10_oct_session'], lb_id, tenant_id, device_info, use_parent, k_session)
    except aten2oct.UnsupportedAXAPIVersionException as e:
        LOG.warning('Skipping loadbalancer %s for config entry %s with AXAPI version %s. '
                    'Only AXAPI version 3.0 is supported.',
                    lb_id, entry_name, e.axapi_version)
        return
    return device_info


def _migrate_slb(LOG, axapi_client, n_session, o_session, lb_id, fl_id, tenant_id, n_lb):

    LOG.info('Migrating VIP port for load balancer: %s', lb_id)
    lb2oct.migrate_vip_ports(n_session, CONF.migration.octavia_account_id, lb_id, n_lb)

    LOG.info('Migrating load balancer: %s', lb_id)
    lb2oct.migrate_lb(o_session, lb_id, n_lb, fl_id)

    LOG.info('Migrating VIP for load balancer: %s', lb_id)
    lb2oct.migrate_vip(n_session, o_session, lb_id, n_lb)

    pool_listener = {}

    # Start pool migration
    pools = db_utils.get_pool_entries_by_lb(n_session, lb_id)
    for pool in pools:
        pool_id = pool[0]
        pool_state = pool[7]
        LOG.debug('Migrating pool: %s', pool_id)
        if pool_state == 'DELETED':
            continue
        elif pool_state != 'ACTIVE':
            raise Exception(_('Pool is invalid state of %s.'), pool_state)
        lb2oct.migrate_pools(o_session, lb_id, n_lb, pool)

        hm_id = pool[5]
        if hm_id is not None:
            LOG.debug('Migrating health manager: %s', hm_id)
            hm = db_utils.get_healthmonitor(n_session, hm_id)
            lb2oct.migrate_health_monitor(o_session, tenant_id, pool_id, hm_id, hm)

        # Handle the session persistence records
        sp = db_utils.get_sess_pers_by_pool(n_session, pool_id)
        if sp:
            LOG.debug('Migrating session persistence for pool: %s', pool_id)
            lb2oct.migrate_session_persistence(o_session, pool_id, sp)

        # Handle the pool members
        members = db_utils.get_members_by_pool(n_session, pool_id)
        for member in members:
            member_id = member[0]
            member_state = member[6]
            LOG.debug('Migrating member: %s', member_id)
            if member_state == 'DELETED':
                continue
            elif member_state != 'ACTIVE':
                raise Exception(_('Member %s for pool %s is invalid state of %s.'),
                                member_id,
                                pool_id,
                                member_state)
            lb2oct.migrate_member(o_session, tenant_id, pool_id, member)

    # Start listener migration. Must come after pool due to l7policy fk
    listeners, lb_stats = db_utils.get_listeners_and_stats_by_lb(n_session, lb_id)
    for listener in listeners:
        listener_id = listener[0]
        axapi_listener = axapi_client.slb.virtual_port.get(lb_id, listener_id,
                                                           listener[3], listener[4])
        pool_id = axapi_listener.get('service-group')
        listener_state = listener[8]
        LOG.debug('Migrating listener: %s', listener_id)
        if listener_state == 'DELETED':
            continue
        elif listener_state != 'ACTIVE':
            raise Exception(_('Listener is invalid state of %s.'),
                             listener_state)
        lb2oct.migrate_listener(n_session, o_session, lb_id, n_lb, listener, pool_id, lb_stats)

        # Handle SNI certs
        SNIs = db_utils.get_SNIs_by_listener(n_session, listener_id)
        for SNI in SNIs:
            sni_id = SNI[0]
            LOG.debug('Migrating SNI: %s', sni_id)
            lb2oct.migrate_SNI(o_session, listener_id, SNI)

        # Handle L7 policy records
        l7policies = db_utils.get_l7policies_by_listener(n_session, listener_id)
        for l7policy in l7policies:
            l7policy_id = l7policy[0]
            l7policy_state = l7policy[8]
            LOG.debug('Migrating L7 policy: %s', l7policy_id)
            if l7policy_state == 'DELETED':
                continue
            elif l7policy_state != 'ACTIVE':
                raise Exception(_('L7 policy is invalid state of %s.'),
                                l7policy_state)                    
            lb2oct.migrate_l7policy(o_session, tenant_id, listener_id, l7policy)
            
            # Handle L7 rule records
            l7rules = db_utils.get_l7rules_by_l7policy(n_session, l7policy_id)
            for l7rule in l7rules:
                l7rule_id = l7rule[0]
                l7rule_state = l7rule[6]
                LOG.debug('Migrating L7 rule: %s', l7rule_id)
                if l7rule_state == 'DELETED':
                    continue
                elif l7rule_state != 'ACTIVE':
                    raise Exception(_('L7 rule is invalid state of %s.'),
                                    l7rule_state)
                lb2oct.migrate_l7rule(o_session, tenant_id, l7policy, l7rule)


def _cleanup_slb(LOG, n_session, lb_id, cleanup=False):
    # Delete the old neutron-lbaas records
    if not CONF.migration.delete_after_migration and not cleanup:
        return

    LOG.info('Performing cascading delete on loadbalancer %s.', lb_id)
    db_utils.cascade_delete_neutron_lb(n_session, lb_id)
    LOG.info('Successful cascading delete of loadbalancer %s.', lb_id)


def _cleanup_tenant_bindings(LOG, a10_nlbaas_session, a10_config, tenant_bindings, cleanup=False):
    failure_count = 0
    if not CONF.migration.delete_after_migration and not cleanup:
        return failure_count

    try:
        # We can't be sure when no more loadbalancers with a given tenant exist
        # in the DB. So we have to delete them here.
        if a10_config.get('use_database'):
            for tenant_binding in tenant_bindings:
                LOG.info('Deleting A10 tenant biding for tenant: %s', tenant_binding)
                aten2oct.delete_binding_by_tenant(a10_nlbaas_session, tenant_binding)
            if CONF.migration.trial_run:
                a10_nlbaas_session.rollback()
                LOG.info('Simulated deletion of A10 tenant bindings successful.')
            elif len(tenant_bindings) > 0:
                a10_nlbaas_session.commit()
                LOG.info('Deletion of A10 tenant bindings successful')
    except Exception as e:
        a10_nlbaas_session.rollback()
        LOG.exception("Skipping A10 tenant binding deletion due to: %s.", str(e))
        failure_count += 1

    return failure_count


def _setup_db_sessions():
    neutron_context_manager = enginefacade.transaction_context()
    neutron_context_manager.configure(
        connection=CONF.migration.neutron_db_connection)
    n_session_maker = neutron_context_manager.writer.get_sessionmaker()
    n_session = n_session_maker(autocommit=False)

    octavia_context_manager = enginefacade.transaction_context()
    octavia_context_manager.configure(
        connection=CONF.migration.octavia_db_connection)
    o_session_maker = octavia_context_manager.writer.get_sessionmaker()
    o_session = o_session_maker(autocommit=False)

    db_sessions = {'n_session': n_session, 'o_session': o_session}

    if CONF.migration.keystone_db_connection:
        keystone_context_manager = enginefacade.transaction_context()
        keystone_context_manager.configure(
            connection=CONF.migration.keystone_db_connection)
        k_session_maker = keystone_context_manager.writer.get_sessionmaker()
        k_session = k_session_maker(autocommit=False)
        db_sessions['k_session'] = k_session

    if CONF.migration.a10_nlbaas_db_connection:
        a10_nlbaas_context_manager = enginefacade.transaction_context()
        a10_nlbaas_context_manager.configure(
            connection=CONF.migration.a10_nlbaas_db_connection)
        a10_nlbaas_session_maker = a10_nlbaas_context_manager.writer.get_sessionmaker()
        a10_nlbaas_session = a10_nlbaas_session_maker(autocommit=False)
    else:
        a10_nlbaas_session = n_session
    db_sessions['a10_nlbaas_session'] = a10_nlbaas_session

    if CONF.migration.a10_oct_db_connection:
        a10_oct_context_manager = enginefacade.transaction_context()
        a10_oct_context_manager.configure(
            connection=CONF.migration.a10_oct_db_connection)
        a10_oct_session_maker = a10_oct_context_manager.writer.get_sessionmaker()
        a10_oct_session = a10_oct_session_maker(autocommit=False)
    else:
        a10_oct_session = o_session
    db_sessions['a10_oct_session'] = a10_oct_session

    return db_sessions


def _create_axapi_client(device_info):
    host = device_info.get('host')
    username = device_info.get('username')
    password = device_info.get('password')
    port = device_info.get('port', 443)
    protocol = device_info.get('protocol', 'https')
    axapi_client = acos_client.Client(host, acos_client.AXAPI_30,
                                      username, password, port=port,
                                      protocol=protocol)
    return axapi_client


def _cleanup_confirmation(LOG):
    print("\nWARNING: Executing with --cleanup is a destructive action. Specified loadbalancers and child objects will be permanently deleted.")
    full_success_msg = None
    lb_success_msg = None

    resp = None
    while resp != "no" and resp != "yes":
        resp = input("Are you sure you want to delete them? [yes/no]: ")
        resp = resp.lower()
        if resp == "no":
            return None, None
        elif resp == "yes":
            LOG.info('=== Starting cleanup ===')
            full_success_msg = '\n\nCleanup completed successfully'
            lb_success_msg = 'cleanup of loadbalancer %s'
        else:
            print("Please enter 'yes' or 'no'")
    return full_success_msg, lb_success_msg


def main():
    if len(sys.argv) == 1:
        print('Error: Config file must be specified.')
        print('a10_nlbaas2oct --config-file <filename>')
        return 1
    logging.register_options(cfg.CONF)
    cfg.CONF(args=sys.argv[1:],
             project='a10_nlbaas2oct',
             version='a10_nlbaas2oct 1.0')
    logging.set_defaults()
    logging.setup(cfg.CONF, 'a10_nlbaas2oct')
    LOG = logging.getLogger('a10_nlbaas2oct')
    CONF.log_opt_values(LOG, logging.DEBUG)

    XOR_CLI_COMMANDS = (CONF.all, CONF.lb_id, CONF.project_id)

    if not any(XOR_CLI_COMMANDS) and not CONF.migration.lb_id_list:
        print('Error: One of --all, --lb_id, --project_id must be '
              'specified or lb_id_list must be set in the config file.')
        return 1        

    check_multi = lambda x: bool(x)
    commands = list(filter(check_multi, XOR_CLI_COMMANDS))
    if len(commands) > 1:
        print('Error: Only one of --all, --lb-id, --project-id allowed.')
        return 1
    elif len(commands) == 1:
        if CONF.migration.lb_id_list and not (CONF.lb_id or CONF.cleanup):
            print('Error: Only --lb-id and --cleanup are allowed with lb_id_list set in the config file.')
            return

    CLEANUP_ONLY = False
    if CONF.cleanup:
        full_success_msg, lb_success_msg = _cleanup_confirmation(LOG)
        if full_success_msg and lb_success_msg:
            CLEANUP_ONLY = True
        else:
            print('Exiting...')
            return
    else:
        LOG.info('=== Starting migration ===')
        full_success_msg = '\n\nMigration completed successfully'
        lb_success_msg = 'migration of loadbalancer %s'

    db_sessions = _setup_db_sessions()
    n_session = db_sessions['n_session']
    o_session = db_sessions['o_session']
    
    a10_config = a10_cfg.A10Config(config_path=CONF.migration.a10_config_path,
                                   provider=CONF.migration.provider_name)

    conf_lb_id_list = CONF.migration.lb_id_list
    if not conf_lb_id_list:
        conf_lb_id_list = []

    if CONF.lb_id:
        conf_lb_id_list.append(CONF.lb_id)
    
    lb_id_list = db_utils.get_loadbalancer_ids(n_session, conf_lb_id_list=conf_lb_id_list,
                                               conf_project_id=CONF.project_id,
                                               conf_all=CONF.all)
    fl_id = None
    failure_count = 0
    tenant_bindings = []
    curr_device_name = None
    for lb_id in lb_id_list:
        lb_id = lb_id[0]
        try:
            LOG.info('Locking Neutron LBaaS load balancer: %s', lb_id)
            db_utils.lock_loadbalancer(n_session, lb_id)
            n_lb = db_utils.get_loadbalancer_entry(n_session, lb_id)
            provider = n_lb[0]
            tenant_id = n_lb[1]
            if provider != CONF.migration.provider_name:
                LOG.info('Skipping loadbalancer with provider %s. '
                         'Does not match specified provider %s.',
                         provider, CONF.migration.provider_name)
                continue
            tenant_bindings.append(tenant_id)

            if not CLEANUP_ONLY:
                device_info = _migrate_device(LOG, a10_config, db_sessions, lb_id, tenant_id)
                if not device_info:
                    continue
                device_name = device_info['name']
                if device_name != curr_device_name:
                    fl_id = _migrate_flavor(LOG, a10_config, o_session, device_name)
                    curr_device_name = device_name
                axapi_client = _create_axapi_client(device_info)
                _migrate_slb(LOG, axapi_client, n_session, o_session, lb_id, fl_id, tenant_id, n_lb)
            _cleanup_slb(LOG, n_session, lb_id, CLEANUP_ONLY)

            # Rollback everything if we are in a trial run otherwise commit
            if CONF.migration.trial_run:
                o_session.rollback()
                n_session.rollback()
                LOG.info('Simulated ' + lb_success_msg + ' successful', lb_id)
            else:
                o_session.commit()
                n_session.commit()
                LOG.info('Successful ' + lb_success_msg, lb_id)
        except Exception as e:
            n_session.rollback()
            o_session.rollback()
            LOG.exception("Skipping load balancer %s due to: %s.", lb_id, str(e))
            failure_count += 1
        finally:
            # Attempt to unlock the loadbalancer even if an error occured or it was deleted.
            # This ensures we don't get stuck in pending states
            LOG.info('Unlocking Neutron LBaaS load balancer: %s', lb_id)
            db_utils.unlock_loadbalancer(n_session, lb_id)
            n_session.commit()

    failure_count += _cleanup_tenant_bindings(LOG, db_sessions['a10_nlbaas_session'],
                                              a10_config, tenant_bindings, CLEANUP_ONLY)

    if failure_count:
        LOG.warning("%d failures were detected", failure_count)
        sys.exit(1)
    
    print(full_success_msg)

if __name__ == "__main__":
    main()
