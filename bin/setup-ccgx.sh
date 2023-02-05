#!/bin/sh
BASE=$(dirname $(dirname $(realpath "$0")))

cd $BASE

echo "Set up device service to autorun on restart"
chmod +x $BASE/acload_prioritize_dbus_service.py
# Use awk to inject correct BASE path into the run script
awk -v base=$BASE '{gsub(/\$\{BASE\}/,base);}1' $BASE/bin/service/run.tmpl >$BASE/bin/service/run
chmod -R a+rwx $BASE/bin/service
rm -f /service/acload_prioritize_dbus_service
ln -s $BASE/bin/service /service/acload_prioritize_dbus_service

CMD="ln -s $BASE/bin/service /service/acload_prioritize_dbus_service"
if ! grep -q "$CMD" /data/rc.local; then
    echo "$CMD" >> /data/rc.local
fi
chmod +x /data/rc.local
echo "Setup acload_prioritize_dbus_service complete"
