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
        self.heater_default_dry_time = self.mmu.config.getfloat('heater_default_time', 60, above=0.)
        self.heater_default_humidity = self.mmu.config.getfloat('heater_default_humidity', 45, above=0.)
        self.heater_max_wattage      = self.mmu.config.getint('heater_max_wattage', -1, minval=-1)

        # Listen of important mmu events
        self.mmu.printer.register_event_handler("mmu:enabled", self._handle_mmu_enabled)
        self.mmu.printer.register_event_handler("mmu:disabled", self._handle_mmu_disabled)

        # Register GCODE commands ---------------------------------------------------------------------------
        self.mmu.gcode.register_command('MMU_HEATER', self.cmd_MMU_HEATER, desc=self.cmd_MMU_HEATER_help)

        self._periodic_timer = self.mmu.reactor.register_timer(self._check_mmu_environment)


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

    def is_active(self):
        """
        Returns whether the MMU heater is currently active (drying filament)
        """
        return self.active


    def get_mmu_heater_string(self, state=None, detail=False):
        # TODO
        return "drying @ 65 degree max"


    def activate_heater(self, eventtime):
        if not self.active:
            self.active = True
            self.mmu.log_info("MMU Heater is activated")


    def deactivate_heater(self, eventtime):
        if self.active:
            self.active = False
            self.mmu.log_info("MMU Heater deactivated")


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
        + "DRY = [1|0] enable/disable filament heater for filament drying cycle\n"
        + "TEMP = \n"
        + "TIME = \n"
        + "HUMIDITY = \n"
        + "OFF = 1 \n"
        + "[GATES = x,y] Gate to dry if MMU has individual spool heaters/dryers\n"
        + "(no parameters for status report)"
    )
    def cmd_MMU_HEATER(self, gcmd):
        self.mmu.log_to_file(gcmd.get_commandline())
        if self.mmu.check_if_disabled(): return

        if gcmd.get_int('HELP', 0, minval=0, maxval=1):
            self.mmu.log_always(self.mmu.format_help(self.cmd_MMU_HEATER_param_help), color=True)
            return

        dry = gcmd.get_int('DRY', None, minval=0, maxval=1)
        timer = gcmd.get_int('TIMER', 60, above=0)

        # Just report status
        if self.active:
            msg = "MMU Heater is dring ... TODO"
            self.mmu.log_always(msg)
        else:
            self.mmu.log_always("MMU Heater is not active")

# MMU_HEATER .. status
# MMU_HEATER TEMP=xx
# MMU_HEATER OFF=1
# MMU_HEATER DRY=1 TIME=60 HUMIDITY=xx
# MMU_HEATER DRY=1 TIME=60 HUMIDITY=xx TEMP=xx
# MMU_HEATER [GATES=4,5,6]
# SET_HEATER_TEMPERATURE HEATER=<heater_name> [TARGET=<target_temperature>]


    def get_status(self, eventtime=None):
        return {
            'heater': self.active
        }


    #
    # Internal implementation --------------------------------------------------
    #

    def _handle_mmu_enabled(self, eventtime=None):
        """
        Event indicating that the MMU unit was enabled
        """
        if self.mmu.is_enabled: return
        if eventtime is None: eventtime = self.mmu.reactor.monotonic()

        # PAUL TODO setup heater monitor
        self.mmu.log_warning("PAUL mmu_environment_manager: _handle_mmu_enabled()")

        self.mmu.reactor.update_timer(self._periodic_timer, self.mmu.reactor.NOW)


    def _handle_mmu_disabled(self, eventtime=None):
        """
        Event indicating that the MMU unit was disabled
        """
        if not self.mmu.is_enabled: return
        if eventtime is None: eventtime = self.mmu.reactor.monotonic()

        # PAUL TODO kill heater monitor
        self.mmu.log_warning("PAUL mmu_environment_manager: _handle_mmu_disabled()")

        self.mmu.reactor.update_timer(self._periodic_timer, self.mmu.reactor.NEVER)

    def _check_mmu_environment(self, eventtime):
        """
        Reaator callback periodically called to check drying status and to
        rationalize state
        """
        self.mmu.log_warning("PAUL mmu_environment_manager: _check_mmu_environment()")

        # Reschedule
        return eventtime + self.CHECK_INTERVAL
