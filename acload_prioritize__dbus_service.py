#!/usr/bin/env python3

"""
Victron Venus OS addon: Prioritize AC load over battery charge in ESS mode 1 when the batteries are empty.
https://github.com/t0bias-r/venusos_acload_prioritize
"""
## @package conversions
# takes data from the dbus, does calculations with it, and puts it back on
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
import dbus
import dbus.service
import inspect
import platform
from threading import Timer
import argparse
import logging
import sys, traceback
import os
import socket
import threading
from os import _exit as os_exit
from contextlib import closing
from datetime import datetime, timedelta

# our own packages
sys.path.insert(1, os.path.join(os.path.dirname(__file__), './velib_python'))
from vedbus import VeDbusService, VeDbusItemImport
from settingsdevice import SettingsDevice




class PeridocTask:
    def __init__(self):
        try:
            self.dbusConn = dbus.SessionBus() if 'DBUS_SESSION_BUS_ADDRESS' in os.environ else dbus.SystemBus()
            
            self._max_discharge_power = 3000
            self._soc_distance        = 5
            self._soc_distance_full   = 10
            
            self._setting_max_discharge_power   = VeDbusItemImport(self.dbusConn, 'com.victronenergy.settings', '/Settings/CGwacs/MaxDischargePower')
            self._setting_minimum_soc_limit     = VeDbusItemImport(self.dbusConn, 'com.victronenergy.settings', '/Settings/CGwacs/BatteryLife/MinimumSocLimit')
            self._state_dc_pv_power             = VeDbusItemImport(self.dbusConn, 'com.victronenergy.system',   '/Dc/Pv/Power')
            self._state_dc_bat_soc              = VeDbusItemImport(self.dbusConn, 'com.victronenergy.system',   '/Dc/Battery/Soc')
            
            # list of PV power values to calcuate average
            self._l_pvpwr = []
            self._l_pvpwr.extend([self._state_dc_pv_power.get_value() for i in range(15)])
            
            logging.info("MaxDischargePower {}".format(self._setting_max_discharge_power.get_value()))
            logging.info("MinimumSocLimit   {}".format(self._setting_minimum_soc_limit.get_value()))
            logging.info("DC bat soc        {}".format(self._state_dc_bat_soc.get_value()))
            logging.info("PV power          {}".format(self._state_dc_pv_power.get_value()))
            
            if self._state_dc_bat_soc.get_value() >= (self._setting_minimum_soc_limit.get_value() + self._soc_distance_full):
                logging.info("initial bat state 'full'")
                self._acload_prio = False
                self._this_discharge_power = self._max_discharge_power
            else:
                logging.info("initial bat state 'empty'")
                self._acload_prio = True
                self._this_discharge_power = 0
            
            
            GLib.timeout_add(1000, self.timeout)
            
        except Exception:
            print("-"*60)
            traceback.print_exc(file=sys.stdout)
            print("-"*60)
            # sys.exit() is not used, since that throws an exception, which does not lead to a program
            # halt when used in a dbus callback, see connection.py in the Python/Dbus libraries, line 230.
            os_exit(1)


    def timeout(self):
        try:
            discharge_setting = self._setting_max_discharge_power.get_value()
            minimum_soc = self._setting_minimum_soc_limit.get_value()
            current_soc = self._state_dc_bat_soc.get_value()
            pv_power = self._state_dc_pv_power.get_value()
            
            old_acload_prio = self._acload_prio
            
            logging.debug("MaxDischargePower {}".format(discharge_setting))
            logging.debug("MinimumSocLimit   {}".format(minimum_soc))
            logging.debug("DC bat soc        {}".format(current_soc))
            logging.debug("PV power          {}".format(pv_power))
            
            self._l_pvpwr.insert(0, pv_power)
            self._l_pvpwr.pop()
            pv_power = sum(self._l_pvpwr) / len(self._l_pvpwr)
            logging.debug("PV power(avg)     {}".format(pv_power))
            
            
            if current_soc >= (minimum_soc + self._soc_distance_full):
                # Bat full, normal discharge up to max
                self._acload_prio = False
                
                if current_soc > 90:
                    new_discharge_power = min(self._max_discharge_power, pv_power * 2)
                elif current_soc >= (minimum_soc + self._soc_distance_full + 3):
                    new_discharge_power = min(self._max_discharge_power, pv_power * 1.5)
                else:
                    new_discharge_power = min(self._max_discharge_power, pv_power)
                
                # discharge power can only raise in that state
                if new_discharge_power > self._this_discharge_power:
                    logging.debug("new discharge power {} -> {}".format(self._this_discharge_power, new_discharge_power))
                    self._this_discharge_power = new_discharge_power
            
            
            elif current_soc >= minimum_soc:
                # In AC load priority mode, discharge is effectively disabled,
                # because the discharge power is limited to the PV power, so
                # no current is drawn from the battery.
                # --> lowest SOC = minimum_soc + self._soc_distance
                if current_soc <= (minimum_soc + self._soc_distance):
                    self._acload_prio = True
                
                if (pv_power > 300):
                    new_discharge_power = int(round(((0.8 * pv_power) - 5) / 10) * 10)
                elif (pv_power > 100) or (self._this_discharge_power > 0 and pv_power > 90):
                    new_discharge_power = int(round(((0.7 * pv_power) - 5) / 10) * 10) - 10
                else:
                    new_discharge_power = 0
                
                if self._acload_prio:
                    # Prioritize AC loads
                    self._this_discharge_power = new_discharge_power
                else:
                    # Limit discharge current to 50% of max, but allow more if more PV power is available
                    self._this_discharge_power = max(int(self._max_discharge_power / 2), new_discharge_power)
            
            
            else:
                # Disable discharge as below minimum soc
                self._acload_prio = True
                if self._this_discharge_power != 0:
                    self._this_discharge_power = 0
                    logging.info("disable discharge: soc {}".format(current_soc))
            
            
            
            if old_acload_prio != self._acload_prio:
                logging.info("acload prio changed {} -> {}".format(old_acload_prio, self._acload_prio))
            
            if self._this_discharge_power != discharge_setting:
                # Limit to self._max_discharge_power
                self._this_discharge_power = min(self._this_discharge_power, self._max_discharge_power)
                # Write new value to DBus
                logging.debug("set discharge limit to {}".format(self._this_discharge_power))
                self._setting_max_discharge_power.set_value(self._this_discharge_power)
            
            return True

        except Exception:
            print("-"*60)
            traceback.print_exc(file=sys.stdout)
            print("-"*60)
            # sys.exit() is not used, since that throws an exception, which does not lead to a program
            # halt when used in a dbus callback, see connection.py in the Python/Dbus libraries, line 230.
            os_exit(1)



def main():
    logging.basicConfig(level=logging.INFO)
    
    try:
        # Have a mainloop, so we can send/receive asynchronous calls to and from dbus
        DBusGMainLoop(set_as_default=True)
        
        logging.info('Starting Peridoc task')
        PeridocTask()
        
        logging.info('Connected to dbus, and switching over to GLib.MainLoop() (= event based)')
        mainloop = GLib.MainLoop()
        mainloop.run()
        
    except (KeyboardInterrupt, SystemExit):
        mainloop.quit()
        # sys.exit() is not used, since that throws an exception, which does not lead to a program
        # halt when used in a dbus callback, see connection.py in the Python/Dbus libraries, line 230.
        os_exit(0)

    except Exception:
        print("-"*60)
        traceback.print_exc(file=sys.stdout)
        print("-"*60)
        # sys.exit() is not used, since that throws an exception, which does not lead to a program
        # halt when used in a dbus callback, see connection.py in the Python/Dbus libraries, line 230.
        os_exit(0)


if __name__ == "__main__":
    main()
