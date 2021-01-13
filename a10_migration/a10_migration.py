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

from oslo_config import cfg
from oslo_db.sqlalchemy import enginefacade
import oslo_i18n as i18n
from oslo_log import log as logging

_translators = i18n.TranslatorFactory(domain='a10_migration')

# The primary translation function using the well-known name "_"
_ = _translators.primary

CONF = cfg.CONF

cli_opts = [
    cfg.BoolOpt('all', default=False,
                help='Migrate all Thunders'),
    cfg.StrOpt('device_name',
               help='Migrate the Thunder with this name'),
    cfg.StrOpt('project_id',
               help='Migrate the Thunder bound to this tenant/project'),
]

migration_opts = [
    cfg.BoolOpt('delete_after_migration', default=True,
                help='Delete the load balancer records from neutron-lbaas'
                     ' after migration'),
    cfg.BoolOpt('trial_run', default=False,
                help='Run without making changes.'),
    cfg.StrOpt('octavia_account_id', required=True,
               help='The keystone account ID Octavia is running under.'),
    cfg.StrOpt('a10_nlbaas_db_connection',
               required=True,
               help='The a10 nlbaas database connection string'),
    cfg.StrOpt('a10_oct_connection',
               required=True,
               help='The a10 octavia database connection string'),
]

cfg.CONF.register_cli_opts(cli_opts)
cfg.CONF.register_opts(migration_opts, group='migration')


def main():
    if len(sys.argv) < 2:
        print("Error: Config files must be specified.")
        print("a10_migration --config-file <filename> --a10-config-file <filename>")
    logging.register_options(cfg.CONF)
    cfg.CONF(args=sys.argv[2:]
             project='a10_migration',
             version='a10_migration 1.0')
    logging.set_defaults()
    logging.setup(cfg.CONF, 'a10_migration')
    LOG = logging.getLogger('a10_migration')
    CONF.log_opt_values(LOG, logging.DEBUG)

    if not CONF.all and not CONF.device_name and not CONF.project_id:
        print('Error: One of --all, --lb_id, or --project_id must be specified.')
        return 1

    if ((CONF.all and (CONF.device_name or CONF.project_id)) or
            (CONF.device_name and CONF.project_id)):
        print('Error: Only one of --all, --device_name, or --project_id allowed.')
        return 1
    
    nblaas_ctx_manager = enginefacade.transaction_context()
    nlbaas_ctx_manager.configure(connection=CONF.migration.a10_nlbaas_db_connection)
    nlbaas_session_maker = nlbaas_ctx_manager.writer.get_sessionmaker()

    octavia_context_manager = enginefacade.transaction_context()
    octavia_context_manager.configure(
        connection=CONF.migration.octavia_db_connection)
    o_session_maker = octavia_context_manager.writer.get_sessionmaker()

    LOG.info('Starting migration.')

    nlbaas_session = nlbaas_session_maker(autocommit=True)
    device_info_map = {}

    if CONF.device_name:
        tenant_id = nlbaas_session.execute(
            "SELECT tenant_id FROM a10_tenant_bindings WHERE "
            "tenant_id = '{0}';".format(project_id))

    elif CONF.project_id:
        device_name = nlbaas_session.execute(
            "SELECT tenant_id FROM a10_tenant_bindings WHERE "
            "tenant_id = '{0}';".format(project_id))

if __name__ == "__main__":
    main()