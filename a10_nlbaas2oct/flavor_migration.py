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
from oslo_utils import uuidutils


def _create_flavor_expr(expr_data):
    name_exprs = {'name-expressions': []}
    for k, v in expr_data.items():
        v['description'] = k
        name_exprs['name-expressions'].append(v)
    return name_exprs


def create_flavor_data(a10_config):
    flavor_data = {}

    vs_expr = a10_config.get_virtual_server_expressions()
    if vs_expr:
        flavor_data['virtual-server'] =  _create_flavor_expr(vs_expr)

    vport_expr = a10_config.get_vport_expressions()
    if vport_expr:
        flavor_data['virtual-port'] = _create_flavor_expr(vport_expr)

    hm_expr = a10_config.get_monitor_expressions()
    if hm_expr:
        flavor_data['health-monitor'] = _create_flavor_expr(hm_expr)


    sg_expr = a10_config.get_service_group_expressions()
    if sg_expr:
        flavor_data['service-group'] = _create_flavor_expr(sg_expr)

    mem_expr = a10_config.get_member_expressions()
    if mem_expr:
        flavor_data['server'] = _create_flavor_expr(mem_expr)

    return flavor_data


def create_flavorprofile(o_session, flavor_data):
    flavorprofile_id = uuidutils.generate_uuid()
    flavorprofile_name = flavorprofile_id[:10]
    provider_name = 'a10'

    flavor_data = str(flavor_data).replace('\'', '\"')
    result = o_session.execute(
        "INSERT INTO flavor_profile (id, name, provider_name, "
        "flavor_data) VALUES (:id, :name, :provider_name, :flavor_data);",
        {'id': flavorprofile_id, 'name': flavorprofile_name,
         'provider_name': provider_name, 'flavor_data': flavor_data})
    if result.rowcount != 1:
        raise Exception(_('Unable to create flavorprofile in the '
                        'Octavia database.'))
    return flavorprofile_id


def create_flavor(o_session, flavorprofile_id):
    flavor_id = uuidutils.generate_uuid()
    flavor_name = flavor_id[:10]

    result = o_session.execute(
        "INSERT INTO flavor (id, name, enabled, flavor_profile_id) "
        "VALUES (:id, :name, :enabled, :flavor_profile_id);",
        {'id': flavor_id, 'name': flavor_name, 'enabled': 1,
         'flavor_profile_id': flavorprofile_id})
    if result.rowcount != 1:
        raise Exception(_('Unable to create flavor in the '
                        'Octavia database.'))
    return flavor_id
