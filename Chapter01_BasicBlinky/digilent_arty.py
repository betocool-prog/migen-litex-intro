#!/usr/bin/env python3

#
# Copyright (c) 2023 Alberto Fahrenkrog

# Build/Use:
# ./digilent_arty.py --build --load

import argparse
import subprocess
from migen import *
from litex_boards.platforms import digilent_arty
from litex.soc.cores.led import LedChaser

# CRG ----------------------------------------------------------------------------------------------

class _CRG(Module):
    def __init__(self, platform):
        self.rst    = ResetSignal()
        self.clock_domains.cd_sys = ClockDomain()
        # # #

        # Clk / Rst
        self.comb +=[
            self.cd_sys.clk.eq(platform.request("clk100", 0)),
            self.rst.eq(~platform.request("cpu_reset", 0))
        ]

# Blinky ------------------------------------------------------------------------------------------

class Blinky(Module):
    def __init__(self, platform):

        # CRG --------------------------------------------------------------------------------------
        self.crg = _CRG(platform)

        # Own blinky on Led0
        # Blinking frequency should be 3 Hz
        period = int(100e6 / 3 / 2)
        count = Signal(max=period, reset=period)
        self.led = Signal()

        self.sync +=[
            count.eq(count - 1),
            If(count == 0,
               self.led.eq(~self.led),
               count.eq(period)
            )
        ]
        self.comb += platform.request("user_led", 0).eq(self.led)

        # Light Led1 when reset button is pushed
        self.comb += platform.request("user_led", 1).eq(ResetSignal())
        
        # Litex LED Chaser
        pads = []
        rgb_led_pins = []
        
        for idx in range(0, 4):
            rgb_led_pins.append(platform.request("rgb_led", idx))

        for idx in range(0, 4):
            pads.append(rgb_led_pins[idx].r)

        for idx in range(0, 4):
            pads.append(rgb_led_pins[idx].g)

        for idx in range(0, 4):
            pads.append(rgb_led_pins[idx].b)

        pads = Cat(pads)

        self.leds = LedChaser(pads, sys_clk_freq=100e6)
        self.submodules += self.crg
        self.submodules += self.leds

# Build --------------------------------------------------------------------------------------------

def main():

    parser = argparse.ArgumentParser(description="LiteX Blinky Example.")
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--load", action="store_true")
    parser.add_argument("--flash", action="store_true")
    args = parser.parse_args()

    # The other variant is "a7-35"
    platform = digilent_arty.Platform(variant='a7-100')
    blinky = Blinky(platform)

    platform.build(blinky, run=args.build)

    if args.load:
        # prog = platform.create_programmer()
        # prog.load_bitstream("./build/top.bit")

        # Another alternative is to use openFPGALoader
        command = "openFPGALoader -b arty_a7_100t ./build/top.bit"
        subprocess.call(command.split(' '))

    if args.flash:
        # prog = platform.create_programmer()
        # prog.flash(0, "./build/top.bit")
        
        # Another alternative is to use openFPGALoader
        command = "openFPGALoader -b arty_a7_100t -f ./build/top.bit"
        subprocess.call(command.split(' '))

if __name__ == "__main__":
    main()
