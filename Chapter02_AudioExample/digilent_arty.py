#!/usr/bin/env python3

#
# Copyright (c) 2023 Alberto Fahrenkrog

# Build/Use:
# ./digilent_arty.py --build --load
# ./digilent_arty.py --build --flash

import argparse
import subprocess
import numpy as np
from migen import *
from litex.soc.cores.clock import *
from litex_boards.platforms import digilent_arty

i2s_if_layout = [
            ('l_data', 32, DIR_M_TO_S), 
            ('r_data', 32, DIR_M_TO_S),
            ('latch_data', 1, DIR_S_TO_M)
        ]


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


        # Light Led2 when reset button is pushed
        self.comb += platform.request("user_led", 2).eq(ResetSignal())

class I2S_Tx(Module):

    def __init__(self, platform, cd_i2s):

        # Generate the clock signals from a 12.288 MHz source
        # MCLK: 12.288 MHz
        # SCLK: 3.072 MHz
        # LRCK: 48 KHz
        i2s_tx = Signal(1, reset=0)
        i2s_sclk = Signal(1, reset=0)
        i2s_mclk = Signal(1, reset=0)
        i2s_lrck = Signal(1, reset=0)
        i2s_clk_div = Signal(max=255, reset=0)

        i2s_tx_pins = platform.request('i2s_tx', 0)

        # I2S Interface
        # Left data word, right data word, ready left, ready right
        self.i2s_if = Record(i2s_if_layout)

        # They say it's not good practice, but we'll do it anyway here, we'll downcount
        # the I2S signals from the 12.288 MHz MCLK 
        self.sync.i2s += [
            i2s_clk_div.eq(i2s_clk_div + 1),
        ]

        self.comb += [
            platform.request('i2s_tx_mclk', 0).eq(cd_i2s.clk),
            i2s_tx_pins.clk.eq(i2s_clk_div[1]),
            i2s_tx_pins.sync.eq(i2s_clk_div[7]),
            i2s_tx_pins.tx.eq(i2s_tx),
            i2s_mclk.eq(cd_i2s.clk),
            i2s_sclk.eq(i2s_clk_div[1]),
            i2s_lrck.eq(i2s_clk_div[7]),
        ]

        # But at least we'll add them as constraints
        platform.add_period_constraint(i2s_mclk, 1e9/12.288e6)
        platform.add_period_constraint(i2s_sclk, 1e9/(12.288e6 / 4))
        platform.add_period_constraint(i2s_lrck, 1e9/48000)

        # From here on we'll work on the 100MHz domain checking for I2S pulses
        sclk_delay = Signal(1)
        sclk_fe = Signal(1) # Falling edge
        lrck_delay = Signal(1)
        lrck_re = Signal(1) # Rising edge
        lrck_fe = Signal(1) # Falling edge

        self.sync += [
            sclk_delay.eq(i2s_sclk),
            lrck_delay.eq(i2s_lrck),

            If((i2s_sclk == 0) & (sclk_delay == 1),
                sclk_fe.eq(1)
            ).Else(
                sclk_fe.eq(0)
            ),
            If((i2s_lrck == 1) & (lrck_delay == 0),
                lrck_re.eq(1)
            ).Else(
                lrck_re.eq(0)
            ),
            If((i2s_lrck == 0) & (lrck_delay == 1),
                lrck_fe.eq(1)
            ).Else(
                lrck_fe.eq(0)
            ),
        ]

        l_data = Signal(32, reset=0)
        r_data = Signal(32, reset=0)

        self.sync += [
            If((sclk_fe == 1) & (i2s_lrck == 0),
               i2s_tx.eq(l_data[31]),
               l_data[1:32].eq(l_data[0:31])
            ),
            If((sclk_fe == 1) & (i2s_lrck == 1),
               i2s_tx.eq(r_data[31]),
               r_data[1:32].eq(r_data[0:31])
            ),
            If((lrck_re == 1) & (sclk_fe == 1),
               r_data.eq(self.i2s_if.r_data),
               i2s_tx.eq(0),
            ),
            If((lrck_fe == 1) & (sclk_fe == 1),
               l_data.eq(self.i2s_if.l_data),
               i2s_tx.eq(0),
            )
        ]

        self.sync += [
            If(lrck_fe == 1,
               self.i2s_if.latch_data.eq(1)
            )
        ]

class Controller(Module): 

    def __init__(self, i2s_tx :I2S_Tx):

        ## Generate 24bit 1 KHz Integer samples @ 48 KHz
        FS = 48000
        freq = 1000
        k = np.linspace(0, 47, num=48)

        samples = np.sin(2 * np.pi * freq * k / FS)
        samples_int = np.int32(2**24 * samples) << 8

        mem = Memory(32, len(samples_int), init=samples_int)

        self.rport = mem.get_port(write_capable=False, async_read=False, has_re=True, clock_domain='sys')
        self.specials += mem, self.rport
        self.addr = Signal(max=48, reset=0)
        self.r_data = Signal(32)
        self.l_data = Signal(32)

        
        self.i2s_tx_if = Record(i2s_if_layout)

        self.comb += self.i2s_tx_if.connect(i2s_tx.i2s_if)

        self.comb += [
            self.rport.re.eq(self.i2s_tx_if.latch_data),
            self.rport.adr.eq(self.addr)
        ]

        self.sync += [

            If(self.i2s_tx_if.latch_data,
               self.addr.eq(self.addr + 1),
               If(self.addr == 47,
                  self.addr.eq(0))
               ),
               self.i2s_tx_if.r_data.eq(self.rport.dat_r),
               self.i2s_tx_if.l_data.eq(self.rport.dat_r)
        ]


# Top Module
class Top(Module):
    
    def __init__(self, platform):

        # CRG 
        self.crg = _CRG(platform)

        # Blinky
        self.blinky = Blinky(platform)

        # I2S Tx
        self.i2s_tx = I2S_Tx(platform, self.crg.cd_i2s)

        # Controller Module
        self.controller = Controller(self.i2s_tx)

        # Add the submodule or it won't compile
        self.submodules += self.crg
        self.submodules += self.blinky
        self.submodules += self.i2s_tx
        self.submodules += self.controller


# Build --------------------------------------------------------------------------------------------

def main():

    parser = argparse.ArgumentParser(description="LiteX Audio Example.")
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--load", action="store_true")
    parser.add_argument("--flash", action="store_true")
    args = parser.parse_args()

    # The other variant is "a7-35"
    platform = digilent_arty.Platform(variant='a7-100')
    platform.add_extension(digilent_arty.i2s_pmod_io('pmodd'))

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
