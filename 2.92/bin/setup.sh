#!/bin/sh
#BASE=/data/drivers/dbus-acload-prioritize
BASE=$(dirname $(dirname $(realpath "$0")))

echo "Set up device service to autorun on restart"
chmod +x $BASE/dbus_acload_prioritize.py
# Use awk to inject correct BASE path into the run script
awk -v base=$BASE '{gsub(/\$\{BASE\}/,base);}1' $BASE/bin/service/run.tmpl >$BASE/bin/service/run
chmod -R a+rwx $BASE/bin/service
rm -f /service/dbus-acload-prioritize
ln -s $BASE/bin/service /service/dbus-acload-prioritize

CMD="ln -s $BASE/bin/service /service/dbus-acload-prioritize &"
if ! grep -q "$CMD" /data/rc.local; then
    echo "$CMD" >> /data/rc.local
fi
chmod +x /data/rc.local
echo "Setup dbus-acload-prioritize complete"
