# Basic Blinky and Led Chaser

## Intro

This Blinky and Led Chaser example should give us a decent enough starting point on some Migen and Litex concepts.

Everyone knows the blinky. This one should blink at 3 Hz on a DE0 Nano board (CycloneIV) using Led 0, but you should be able to adapt it fairly simply for any other supported platform

The Led Chaser is a Litex Core module, which produces a nice looking Knight Rider style LED sequence from Leds 2 to 8.

Led 1 will light up if the reset button is pushed. The reset button will be assigned to Key 0.

## Components

All in all, this project contains three major components:
- A CRG (Clock and Reset Generator) module
- A Blinky module:
    - Simple Led 0 blinky
    - Led Chaser Leds 2 to 8

### CRG

```python
class _CRG(Module):
    def __init__(self, platform):
        self.rst    = ResetSignal()
        self.clock_domains.cd_sys = ClockDomain()
        # # #

        # Clk / Rst
        self.comb +=[
            self.cd_sys.clk.eq(platform.request("clk50", 0)),
            self.rst.eq(~platform.request("key", 0))
        ]
```

Here we explicitly define a reset signal `ResetSignal()` and a clock domain with `ClockDomain()`. In the combinatorial section we assign `clk50` to be the clock `cd_sys.clk`, and we assign the inverted `key 0` to be our reset signal.

If we do not assign a clock domain, the system will use the default clock domain defined in the platform file for the De0 Nano board. If we do not assign an input to the reset signal, the example will simply not reset.

### Blinky

```python
class Blinky(Module):
    def __init__(self, platform):

        # CRG --------------------------------------------------------------------------------------
        self.crg = _CRG(platform)

        # Own blinky on Led0
        # Blinking frequency should be 3 Hz
        period = int(50e6 / 3 / 2)
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
        for idx in range(2, 8):
            pads.append(platform.request("user_led", idx))

        pads = Cat(pads)

        self.leds = LedChaser(pads, sys_clk_freq=50e6)
        self.submodules += self.crg
        self.submodules += self.leds
```

Things get a bit more complex here. The Blinky module contains the CRG module as well as a Led Chaser module.

The first part of the code is a downcounter, whenever the value zero is reached the Led 0 output gets inverted and the counter period gets reset. Not that we have a `self.sync` statement followed by a `self.comb` statement. The first statement contains all synchronous logic, the second assigns the value of Led 0 to the actual output.

You could re-write the combinational statemets as:
```python
        self.comb += [
            platform.request("user_led", 0).eq(self.led),
            # Light Led1 when reset button is pushed
            platform.request("user_led", 1).eq(ResetSignal())
        ]
```

The Led Chaser is an existing module from Litex. It receives a `Cat()` object as an argument. In several SoC examples from Litex, the LedChaser is initialised with:
```python
platform  = platform = terasic_de0nano.Platform()
sys_clk_freq = 50e6
pads = platform.request_all("user_led")
self.chaser = LedChaser(pads, sys_clk_freq)
```

The `request_all(name)` method requests all `user_led` pins on a board and returns them as a `Cat()` object.

