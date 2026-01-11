# -*- coding: utf-8 -*-
# Happy Hare MMU Software
#
# Copyright (C) 2022-2026  moggieuk#6538 (discord)
#                          moggieuk@hotmail.com
#
# Goal: Manager class to implement MMU heater control and basic filament drying functionality
#
# Implements commands:
#   MMU_HEATER
#
#
# (\_/)
# ( *,*)
# (")_(") Happy Hare Ready
#
# This file may be distributed under the terms of the GNU GPLv3 license.
#
import logging

# Happy Hare imports

# MMU subcomponent clases
from .mmu_shared           import *


class MmuEnvironmentManager:

    CHECK_INTERVAL = 60 # How often to check heater and environment sensors (seconds)
    
    def __init__(self, mmu):
        self.mmu = mmu
        self.mmu.managers.append(self)

        # Process config
        self.heater_default_dry_temp = self.mmu.config.getfloat('heater_default_dry_temp', 60, above=0.)
        self.heater_default_dry_time = self.mmu.config.getfloat('heater_default_dry_time', 60, above=0.)
        self.heater_default_humidity = self.mmu.config.getfloat('heater_default_humidity', 45, above=0.)
        self.heater_max_wattage      = self.mmu.config.getint('heater_max_wattage', -1, minval=-1)

        # Listen of important mmu events
        self.mmu.printer.register_event_handler("mmu:disabled", self._handle_mmu_disabled)

        # Register GCODE commands ---------------------------------------------------------------------------
        self.mmu.gcode.register_command('MMU_HEATER', self.cmd_MMU_HEATER, desc=self.cmd_MMU_HEATER_help)

        self._periodic_timer = self.mmu.reactor.register_timer(self._check_mmu_environment)
        self._drying = False
        self._drying_temp = None
        self._drying_humidty_target = None
        self._drying_start_time = self._drying_end_time = None


    #
    # Standard mmu manager hooks...
    #

    def reinit(self):
        logging.info("PAUL: mmu_environment_manager: reinit()")
        # TODO


    def handle_connect(self):
        logging.info("PAUL: mmu_environment_manager: _handle_connect()")


    def handle_disconnect(self):
        logging.info("PAUL: mmu_environment_manager: _handle_disconnect()")


    def handle_ready(self):
        self.mmu.reactor.update_timer(self._periodic_timer, self.mmu.reactor.NOW)
        logging.info("PAUL: mmu_environment_manager: _handle_ready()")


    def set_test_config(self, gcmd):
        if self.has_heater():
            self.heater_default_dry_temp = gcmd.get_float('HEATER_DEFAULT_DRY_TEMP', self.heater_default_dry_temp, above=0.)
            self.heater_default_dry_time = gcmd.get_float('HEATER_DEFAULT_DRY_TIME', self.heater_default_dry_time, above=0.)
            self.heater_default_humidity = gcmd.get_float('HEATER_DEFAULT_HUMIDITY', self.heater_default_humidity, above=0.)
            self.heater_max_wattage      = gcmd.get_int('HEATER_MAX_WATTAGE', self.heater_max_wattage, minval=-1)


    def get_test_config(self):
        msg  = ""
        if self.has_heater():
            msg += "\nheater_default_dry_temp = %.1f" % self.heater_default_dry_temp
            msg += "\nheater_default_dry_time = %.1f" % self.heater_default_dry_time
            msg += "\nheater_default_humidity = %.1f" % self.heater_default_humidity
            msg += "\nheater_max_wattage= %d" % self.heater_max_wattage

        return msg


    def check_test_config(self, param):
        return vars(self).get(param) is None

    #
    # Mmu Heater manager public access...
    #

    def is_drying(self):
        """
        Returns whether the MMU heater is currently in drying cycle
        """
        return self._drying


    def has_heater(self):
        return True # TODO (move to mmu.py?)


    def has_env_sensor(self):
        return True # TODO (move to mmu.py?)


    #
    # GCODE Commands -----------------------------------------------------------
    #

    cmd_MMU_HEATER_help = "Enable/disable MMU heater (filament dryer)"
    cmd_MMU_HEATER_param_help = (
        "MMU_HEATER: %s\n" % cmd_MMU_HEATER_help
        + "OFF = 1 \n"
        + "DRY = [1|0] enable/disable filament heater for filament drying cycle\n"
        + "TIME = \n"
        + "TEMP = \n"
        + "HUMIDITY = \n"
        + "[GATES = x,y] Gate to dry if MMU has individual spool heaters/dryers\n"
        + "(no parameters for status report)"
    )
    def cmd_MMU_HEATER(self, gcmd):
        self.mmu.log_to_file(gcmd.get_commandline())
        if self.mmu.check_if_disabled(): return

        if gcmd.get_int('HELP', 0, minval=0, maxval=1):
            self.mmu.log_always(self.mmu.format_help(self.cmd_MMU_HEATER_param_help), color=True)
            return

        off = gcmd.get_int('OFF', None, minval=0, maxval=1)
        dry = gcmd.get_int('DRY', None, minval=0, maxval=1)
        time = gcmd.get_int('TIME', self.heater_default_dry_time, minval=0)
        temp = gcmd.get_float('TEMP', None, minval=0., maxval=100.)
        humidity = gcmd.get_int('HUMIDTY', self.heater_default_humidity, minval=0)
        gates = gcmd.get('GATES', "!")
        if gates != "!":
            gatelist = []
            # Supplied list of gates
            try:
                for gate in gates.split(','):
                    gate = int(gate)
                    if 0 <= gate < self.num_gates:
                        gatelist.append(gate)
            except ValueError:
                raise gcmd.error("Invalid GATES parameter: %s" % gates)
        else:
            # Default to non empty gates
            gates = [
                i for i, status in enumerate(self.mmu.gate_status)
                if status != self.mmu.GATE_EMPTY
            ]


        if off or temp == 0:
            self._stop_drying_cycle()
            self._heater_off()
            return

        if not dry and temp is not None:
            self._heater_on()
            if self._drying:
                self._drying_temp = temp
            return

        def _format_minutes(minutes):
            hours, mins = divmod(minutes, 60)
            parts = []
            if hours:
                parts.append("%d hour%s" % (hours, "" if hours == 1 else "s"))
            if mins or hours:
                parts.append("%d minute%s" % (mins, "" if mins == 1 else "s"))
            return " ".join(parts)


        if dry:
            temp = self.heater_default_dry_temp
            # Reduce heat to lowest filament temp in "gates" and log that fact

            # Initiate dryer, record current time, record time, humidity and temp
            self._drying_time = time
            self._drying_temp = temp
            self._drying_humidity_target = humidity
            self._drying_start_time = self.mmu.reactor.monotonic()
            self._drying_end_time = self._drying_start_time + self._drying_time * 60

            self._start_drying_cycle()

            msg = "MMU filament drying cycle started:"

        elif self._drying:
            msg = "MMU is in filament drying cycle:"
        else:
            msg = "TODO Not drying cycle but heater is ... OR off"

        if self._drying:
            remaining_mins = _format_minutes((self._drying_end_time - self.mmu.reactor.monotonic()) // 60)
            msg += "\nCycle time: %s (reamining: %s)" % (_format_minutes(self._drying_time), remaining_mins)
            msg += "\nTarget humidy: %.1f%%" % self._drying_humidity_target
            msg += "\nDrying temp: %.1f°C" % self._drying_temp

        # Report status
        self.mmu.log_always(msg)


    def get_status(self, eventtime=None):
        return {
            'drying_filament': self._drying
        }


    #
    # Internal implementation --------------------------------------------------
    #

    def _handle_mmu_disabled(self, eventtime=None):
        """
        Event indicating that the MMU unit was disabled
        """
        if not self.mmu.is_enabled: return
        if eventtime is None: eventtime = self.mmu.reactor.monotonic()

        self.mmu.log_warning("PAUL mmu_environment_manager: _handle_mmu_disabled()")
        self._stop_drying_cycle()
        self._heater_off()

    def _check_mmu_environment(self, eventtime):
        """
        Reaator callback periodically called to check drying status and to
        rationalize state
        """
        self.mmu.log_warning("PAUL mmu_environment_manager: _check_mmu_environment()")

        # Reschedule
        return eventtime + self.CHECK_INTERVAL

    def _start_drying_cycle(self):
        if not self._drying:
            self.mmu.log_info("MmuEnvironemntManager: Filament drying started")
            self._heater_on(self._drying_temp)
            self.mmu.reactor.update_timer(self._periodic_timer, self.mmu.reactor.NOW)
            self._drying = True

    def _stop_drying_cycle(self):
        if self._drying:
            self.mmu.log_info("MmuEnvironemntManager: Filament drying stopped")
            self.mmu.reactor.update_timer(self._periodic_timer, self.mmu.reactor.NEVER)
            self._heater_off()
            self._drying = False

    def _heater_on(self, temp):
        self.mmu.log_warning("PAUL HEATER ON, TEMP=%s" % temp)

    def _heater_off(self):
        self.mmu.log_warning("PAUL HEATER OFF")
