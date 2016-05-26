#!/bin/bash

# Verify running as root:
if [ "$(id -u)" != "0" ]; then
    if [ $# -ne 0 ]; then
        echo "Failed running with sudo. Exiting." 1>&2
        exit 1
    fi
    echo "This script must be run as root. Trying to run with sudo."
    sudo bash "$0" --with-sudo
    exit 0
fi

#apt-get update
#apt-get dist-upgrade
#apt-get install -y python-pip python-dev nginx curl build-essential pwgen
#pip install -U setuptools

pip install -r requirements.txt
pip install -r requirements_all_ds.txt
echo "给系统添加用户 redash ..."
adduser --system --no-create-home --disabled-login --gecos "" redash

# Create database / tables
pg_user_exists=0
sudo -u postgres psql postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='redash'" | grep -q 1 || pg_user_exists=$?
if [ $pg_user_exists -ne 0 ]; then
    echo "创建数据库新用户 redash ..."
    sudo -u postgres createuser redash --no-superuser --no-createdb --no-createrole
    echo "请输入数据库新用户 redash 的密码："
    sudo -u postgres psql postgres -tAc "\password redash"
    echo "创建数据库..."
    sudo -u postgres createdb redash --owner=redash

    #cd /opt/redash/current
    echo "生成表结构..."
    sudo -u redash bin/run ./manage.py database create_tables
    echo "授予权限，需要多次输入密码..."
    sudo -u postgres psql -c "grant ALL PRIVILEGES ON data_sources to redash;" redash
    sudo -u postgres psql -c "grant ALL PRIVILEGES ON users,organizations,groups,data_source_groups to redash;" redash
    sudo -u postgres psql -c "grant ALL PRIVILEGES on events, queries, dashboards, widgets, visualizations, query_results to redash;" redash
fi

# Create default admin user
#cd /opt/redash/current
# TODO: make sure user created only once
# TODO: generate temp password and print to screen
echo "创建超级用户 admin ..."
sudo -u redash bin/run ./manage.py users create --admin --password admin "admin" "admin"

# BigQuery dependencies:
apt-get install -y libffi-dev libssl-dev

# MySQL dependencies:
apt-get install -y libmysqlclient-dev

# Microsoft SQL Server dependencies:
apt-get install -y freetds-dev
echo "完成，请注意修改 settings.py 中的 DATABASE_CONFIG 变量"

