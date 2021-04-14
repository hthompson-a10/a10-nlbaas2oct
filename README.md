# A10 nlbaas2oct
This tool has been designed to migration A10 devices and their associated neutron lbaas objects from the Neutron database to Octavia.

## Installation

### Install from PyPi
```
pip install a10-nlbaas2oct
```

### Install from Source
```bash
git clone git@github.com:a10networks/a10-nlbaas2oct.git
cd a10-nlbaas2oct
pip install -e .
```

**Note: This tool must be installed on the host running neutron-lbaas**

## Usage

## Step 1: Copy the sample config file from the project to another directory

### Installed from PyPi
```
pip show a10-nlbaas2oct | grep "Location" | cp $(awk '{print $2}')/a10_nlbaas2oct/a10_nlbaas2oct.conf /path/to/another/directory
```

### Installed from source
```
cp /path/to/a10-nlbaas2oct/a10_nlbaas2oct/a10_nlbaas2oct.conf /path/to/another/directory
```

### Sample Config File Contents
```
[DEFAULT]

debug = True

[migration]

# Run without making changes
# trial_run = False

# Delete the load balancer records from neutron-lbaas after migration
# delete_after_migration = False

# Octavia service account ID or username (ex: admin)
octavia_account_id =

# Example db connection string:
# connection = mysql+pymysql://root:password@127.0.0.1:3306/octavia
# Replace 127.0.0.1 above with the IP address of the database used by the
# main octavia server. (Leave it as is if the database runs on this host.)

# Connection string for the neutron database
neutron_db_connection =

# Connection string for the octavia database
octavia_db_connection =

# Connection string for the A10 database used in neutron lbaas env
# a10_nlbaas_db_connection =

# Connection string for the A10 database used in the octavia env
# a10_oct_connection =

# Path to config file. Default is /etc/a10
a10_config_path = /etc/a10
```

## Step 2: Modify the config file

#### Database connection string locations

The `neutron_db_connection` can be found in the `/etc/neutron/neutron.conf` file under the `database` group.

```
[database]
connection = mysql+pymysql://user:password@127.0.0.1/neutron?charset=utf8
```

The `octavia_db_connection` can be found be found in the `/etc/octavia/octavia.conf`file under the `database` group.

```
[database]
connection = mysql+pymysql://root:password@127.0.0.1:3306/octavia
```

### Config for migrating from Neutron LBaaS to Octavia on the same host

```
# Octavia service account ID or username (ex: admin)
octavia_account_id = admin

# Connection string for the neutron database
neutron_db_connection = mysql+pymysql://user:password@127.0.0.1/neutron?charset=utf8

# Connection string for the octavia database
octavia_db_connection = mysql+pymysql://root:password@127.0.0.1:3306/octavia

# Path to config file. Default is /etc/a10
a10_config_path = /etc/a10
```

### Config for migrating from Neutron LBaaS to Octavia across hosts
<pre>
# Octavia service account ID or username (ex: admin)
octavia_account_id = admin

# Connection string for the neutron database
neutron_db_connection = mysql+pymysql://user:password@127.0.0.1/neutron?charset=utf8

# Connection string for the octavia database
octavia_db_connection = mysql+pymysql://root:password@<b>ip_address_of_remote_host</b>:3306/octavia

# Path to config file. Default is /etc/a10
a10_config_path = /etc/a10
</pre>

### Performing cross host migration when A10 database is seperate from Neutron DB and Octavia DB 

<pre>
# Octavia service account ID or username (ex: admin)
octavia_account_id = admin

# Connection string for the neutron database
neutron_db_connection = mysql+pymysql://user:password@127.0.0.1/neutron?charset=utf8

# Connection string for the octavia database
octavia_db_connection = mysql+pymysql://root:password@<b>ip_address_of_remote_host</b>:3306/octavia

# Path to config file. Default is /etc/a10
a10_config_path = /etc/a10

# Connection string for the A10 database used in neutron lbaas env
a10_nlbaas_db_connection = mysql+pymysql://user:password@127.0.0.1/a10_db

# Connection string for the A10 database used in the octavia env
a10_oct_connection = mysql+pymysql://user:password@<b>ip_address_of_remote_host</b>/a10_db
</pre>

## Step 3: Perform the migration

### Migrate a single loadbalancer and its child objects
```
a10_nlbaas2oct --config-file /path/to/a10_nlbaas2oct.conf --lb-id <loadbalancer_id>
```

*Note: This takes in the UUID of the loadbalancer **not** the name*

### Migrate all lbaas objects in a project
```
a10_nlbaas2oct --config-file /path/to/a10_nlbaas2oct.conf --project-id <project_id>
```

*Note: This takes in the UUID of the project **not** the name*

### Migrate all lbaas objects
```
a10_nlbaas2oct --config-file /path/to/a10_nlbaas2oct.conf --all
```

### Note to Reader

The vast majority of this tooling was copied and modified from openstack's neutron-lbaas repo for ease of use purposes. The 
original can be found here https://github.com/openstack/neutron-lbaas/tree/stable/stein/tools/nlbaas2octavia
