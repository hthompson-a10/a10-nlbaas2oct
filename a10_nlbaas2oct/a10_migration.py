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
import functools32

import oslo_i18n as i18n
from oslo_utils import uuidutils

_translators = i18n.TranslatorFactory(domain='a10_nlbaas2oct')

# The primary translation function using the well-known name "_"
_ = _translators.primary


class IncorrectPartitionTypeException(Exception):

    def __init__(self, v_method):
        self.message = ("v_method of type {} was specified, "
                       "but only \"LSI\" or \"ADP\" are supported")
        self.message = _(self.message.format(v_method)) # Apply translator
        super(IncorrectPartitionTypeException, self).__init__(self.message)


class UnsupportedAXAPIVersionException(Exception):

    def __init__(self, axapi_version):
        self.axapi_version = axapi_version
        super(IncorrectPartitionTypeException, self).__init__(self.message)


def get_device_name_by_tenant(a10_nlbaas_session, tenant_id):

    # The db session will change each time so we need this internal function instead
    @functools32.lru_cache(maxsize=None)
    def preform_db_select(db_tenant_id):
        # To avoid side effects, pass the tenant_id to the internal function
        # instead of using external definition
        device_name = a10_nlbaas_session.execute(
            "SELECT device_name FROM neutron.a10_tenant_bindings WHERE "
            "tenant_id = :tenant_id ;", {"tenant_id": db_tenant_id}).fetchone()
        return device_name[0]
    
    return preform_db_select(tenant_id)


def delete_binding_by_tenant(a10_nlbaas_session, tenant_id):
    # Delete the bindings
    a10_nlbaas_session.execute(
        "DELETE FROM neutron.a10_tenant_bindings WHERE tenant_id = :tenant_id;",
        {'tenant_id': tenant_id})


def migrate_thunder(a10_oct_session, loadbalancer_id, tenant_id, device_info):
    # Create thunder entry

    vthunder_id = uuidutils.generate_uuid()

    if device_info['v_method'] == "LSI":
        hierarchical_multitenancy = "disable"
        partition_name = device_info['shared_partition']
    elif device_info['v_method'] == "ADP":
        hierarchical_multitenancy = "enable"
        partition_name = tenant_id[0:13]
    else:
        raise IncorrectPartitionTypeException(device_info['v_method'])

    axapi_version = 30
    if device_info['api_version'] not in ['3.0', 30]:
        raise UnsupportedAXAPIVersionException(device_info['api_version'])

    result = a10_oct_session.execute(
        "INSERT INTO vthunders (vthunder_id, device_name, ip_address, username, "
        "password, axapi_version, undercloud, loadbalancer_id, project_id, "
        "topology, role, last_udp_update, status, created_at, updated_at, "
        "partition_name, hierarchical_multitenancy) "
        "VALUES (:vthunder_id, :device_name, :ip_address, :username, :password, "
        ":axapi_version, :undercloud, :loadbalancer_id, :project_id, :topology, "
        ":role, :last_udp_update, :status, :created_at, :updated_at, :partition_name, "
        ":hierarchical_multitenancy);",
        {'vthunder_id': vthunder_id,
         'device_name': device_info['name'],
         'ip_address': device_info['host'],
         'username': device_info['username'],
         'password': device_info['password'],
         'axapi_version': axapi_version,
         'undercloud': 1,
         'loadbalancer_id': loadbalancer_id,
         'project_id': tenant_id,
         'topology': "STANDALONE",
         'role': "MASTER",
         'status': "ACTIVE",
         'last_udp_update': datetime.datetime.utcnow(),
         'created_at': datetime.datetime.utcnow(),
         'updated_at': datetime.datetime.utcnow(),
         'partition_name': partition_name,
         'hierarchical_multitenancy': hierarchical_multitenancy}
        )
    if result.rowcount != 1:
        raise Exception(_('Unable to create Thunder in the A10 Octavia database.'))
