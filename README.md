# Victron Venus OS: Prioritize AC load over battery charge
Victron Venus OS addon: Prioritize AC load over over LiFePO4 charge for ESS Status Reason Code #1.

The script is used in an [ESS mode 1](https://www.victronenergy.com/live/ess:ess_mode_2_and_3) environment where the PV power is mainly used for the AC loads (=household) and to charge the battery. The battery delivers the power for the AC loads during the night.

On cloudy days with almost no sun, all PV power is directly needed by the AC loads.

## Default behaviour of Venus OS
When the battery SOC is <= *Minimum SOC (unless Grid fails)*, discharging is stopped and ESS status #1 is active.

![grafik](https://user-images.githubusercontent.com/95424140/153350133-3eb52bd4-718a-4ce0-a0ea-916810f8edb7.png)

When the battery is re-charged to minimum-soc + 3, ESS status #1 is deasserted and discharging is re-enabled.

In case PV power is lees than AC load power, the battery will be discharged immediately again (with up to maximum inverter power). This results in continuous charge-discharge cycles of around 3%.

In addition to the charge-discharge losses, the battery is unnecessarily loaded and the discharge capacity is not limited.

## Script behaviour
The script controls the *Maximum inverter power* setting over DBus: **com.victronenergy.settings, /Settings/CGwacs/MaxDischargePower**, see [Victron DBus](https://github.com/victronenergy/venus/wiki/dbus).
1. When the battery SOC is < *Minimum SOC (unless Grid fails)*, the inverter power is set to 0, what effectively stopps the discharge (ESS status #7).
2. When the battery SOC is in the range from *Minimum SOC* to *Minimum SOC* + 5, then the inverter power is set to ~80% of the PV power (when PV power > 100W, otherwise 0%). The value 80% is used so that the battery is not discharged despite conversion losses.
3. When the battery SOC is in the range from *Minimum SOC* + 5 to *Minimum SOC* + 10, then the inverter power is set 
 - A) in charge phase to ~80% of the PV power (when PV power > 100W, otherwise 0%),
 - B) in discharge phase to 50% of the maximum power.
4. When the battery SOC is above *Minimum SOC*+10, the inverter power will be slowly increased to the maximum.


# User settings
1. The VenusOS setting *Maximum inverter power* is controlled by the script and can't be used/set anymore in the GUI.
2. *Minimum SOC (unless Grid fails)* shoud be set to 5% below the desired limit
3. The maximum inverter power should be set in the Python script `self._max_discharge_power` (approx. line 33)


# Venus OS daemon service
The script is running as a daemon service. 
See [howto add a driver to Venus](https://github.com/victronenergy/venus/wiki/howto-add-a-driver-to-Venus#3-installing-a-driver) + [daemontools](https://cr.yp.to/daemontools.html)
