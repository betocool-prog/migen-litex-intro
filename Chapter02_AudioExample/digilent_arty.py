#!/usr/bin/env python3

#
# Copyright (c) 2023 Alberto Fahrenkrog

# Build/Use:
# ./digilent_arty.py --build --load
# ./digilent_arty.py --build --flash

import argparse
import subprocess
from migen import *
from litex.soc.cores.clock import *
from litex_boards.platforms import digilent_arty


# CRG ----------------------------------------------------------------------------------------------

class _CRG(Module):
    def __init__(self, platform):
        self.rst    = ResetSignal()
        self.clock_domains.cd_sys = ClockDomain()
        self.clock_domains.cd_i2s = ClockDomain()
        # # #

        # Clk / Rst
        self.comb +=[
            self.cd_sys.clk.eq(platform.request("clk100", 0)),
            self.rst.eq(~platform.request("cpu_reset", 0)),
        ]

        # PLL for 12.288 MHz Clock
        # This is taken from Litex digilent_arty.py example
        self.pll = S7PLL(speedgrade=-1)
        self.comb += self.pll.reset.eq(self.rst)
        self.pll.register_clkin(self.cd_sys.clk, 100e6)
        self.pll.reset.eq(self.rst)
        self.pll.create_clkout(self.cd_i2s, freq=12.288e6)

        platform.add_period_constraint(self.cd_i2s.clk, 1e9/12.288e6)

        self.submodules += self.pll

# Blinky ------------------------------------------------------------------------------------------

class Blinky(Module):
    def __init__(self, platform):

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

        # To test the I2S clock domain, we'll blink LED1 with 5 Hz
        period = int(12.288e6 / 5 / 2)
        count = Signal(max=period, reset=period)
        self.led_1 = Signal()

        self.sync.i2s +=[
            count.eq(count - 1),
            If(count == 0,
               self.led_1.eq(~self.led_1),
               count.eq(period)
            )
        ]
        self.comb += platform.request("user_led", 1).eq(self.led_1)


        # Light Led1 when reset button is pushed
        self.comb += platform.request("user_led", 2).eq(ResetSignal())

# Top Module
class Top(Module):
    
    def __init__(self, platform):

        # CRG 
        self.crg = _CRG(platform)

        # Blinky
        self.blinky = Blinky(platform)

        # Add the submodule or it won't compile
        self.submodules += self.crg
        self.submodules += self.blinky


# Build --------------------------------------------------------------------------------------------

def main():

    parser = argparse.ArgumentParser(description="LiteX Audio Example.")
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--load", action="store_true")
    parser.add_argument("--flash", action="store_true")
    args = parser.parse_args()

    # The other variant is "a7-35"
    platform = digilent_arty.Platform(variant='a7-100')

    top = Top(platform)

    platform.build(top, run=args.build)

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