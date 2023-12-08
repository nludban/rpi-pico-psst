#!micropython
#
# psst.py
#
#	PIO Synchronous Serial Transport
#	for Raspberry Pi pico
#
# https://github.com/nludban/rpi-pico-psst
#
#---------------------------------------------------------------------#

from micropython import const
from array import array

RX_START_IRQ = const(5)	# 5 or 7, relative to SM=0 or 2
TX_START_IRQ = const(4)	# Also 5 or 7, relative to SM=1 or 3

import machine
import rp2

Pin = machine.Pin

#--------------------------------------------------#

@rp2.asm_pio(
    set_init=(
        rp2.PIO.OUT_LOW,	# /pulse out (open-drain)
    ),
    sideset_init=(
        rp2.PIO.OUT_LOW,	# clock out
    ),
    fifo_join=rp2.PIO.JOIN_TX,
)
def watchdog_prog(
    RX_START_IRQ=RX_START_IRQ,
    TX_START_IRQ=TX_START_IRQ,
):
    # .side_set 1
    # Side set value for clock phases and failure.
    WDOG_A = 0 #const(0)
    WDOG_B = const(1)
    WDOG_F = const(0)

    # 20 cycles per loop x 2(!) clocks out per loop.
    wrap_target()
    irq(RX_START_IRQ).side(WDOG_B) [3]  # set/nowait
    # Get new count (bits inverted), or copy %x (-1)
    pull(noblock).side(WDOG_B)

    # Flip bits to get count (or 0)
    mov(x, invert(osr)).side(WDOG_A)
    # Fail if reused %x is detected
    jmp(not_x, 'barking').side(WDOG_A) [3]

    label('napping')
    irq(RX_START_IRQ).side(WDOG_B) [4]  # set/nowait

    jmp(x_dec, 'napping').side(WDOG_A) [4]
    wrap()

    label('barking')
    set(pindirs, 1).side(WDOG_F)	# assert /error
    jmp('barking').side(WDOG_F)


@rp2.asm_pio(
    sideset_init=( rp2.PIO.OUT_LOW, )
)
def watchdog_init_prog():
    # .side_set 1
    #WDOG_A = const(0)  # SyntaxError: can't assign to expression
    WDOG_A = 0

    set(pindirs, 0).side(WDOG_A)  # clear /error
    set(pins, 0).side(WDOG_A)


class Watchdog:

    def __init__(self, i_sm, clock_pin=None, nerror_pin=None):
        assert i_sm in (0, 2, 4, 6)
        kwargs = { }
        if clock_pin is not None:
            kwargs['sideset_base'] = clock_pin
        if nerror_pin is not None:
            kwargs['set_base'] = nerror_pin
        self._sm = rp2.StateMachine(
            i_sm,
            freq=(machine.freq() // 4),
            prog=watchdog_prog,
            **kwargs
        )
        for opcode in watchdog_init_prog[0]:
            self._sm.exec(opcode)
        self.pet_blocking(5000)  # 5 second rule.
        self._sm.active(True)
        return

    def pet_blocking(self, timeout_ms):
        # 3.125 MHz => 3125 ticks/millisecond.
        if (timeout_ms < 0):
            # A maximum "over 20 minutes" - the (joined) FIFO can be
            # preloaded to effectively disable the watchdog for over
            # 2 hours.
            timeout_ms = 21 * 60 * 1000
        self._sm.put(~(3125 * timeout_ms))
        return

    def pet(self, level, timeout_ms):
        # Add watchdog timeouts to the queue up to level, return number
        # of times added.  Note the returned count can be used to
        # monitor if the caller is falling behind.
        n = self._sm.tx_fifo()
        if (n >= level):
            return 0
        for i in range(n, level):
            self._sm.put(~(3125 * timeout_ms))
        return (level - n)

#--------------------------------------------------#

@rp2.asm_pio(
    sideset_init=(
        rp2.PIO.OUT_LOW,	# clock
    ),
    out_init=(
        rp2.PIO.OUT_LOW,	# /pulse (open-drain)
    ),
    fifo_join=rp2.PIO.JOIN_RX,
)
def receiver_prog(
    RX_START_IRQ=RX_START_IRQ,
):
    # .side_set 1
    wrap_target()
    label('start')
    ## t=4 (+/-1)
    wait(1, pin, 0).side(1)		# synch to 0->1 input edge
    ## t=8 (CLK => 0)
    nop().side(0) [11]
    ## t=20 (center of pulse bit)
    mov(osr, invert(pins)).side(0)	# when pulse bit is 0
    out(pindirs, 1).side(0) [5]	# drive output /pulse low
    ## t=27
    irq(rel(RX_START_IRQ)).side(0)	# trigger TX half
    ## t=28 (CLK => 1)
    jmp(pin, 'rx_valid').side(1) [7] # test valid bit
    label('rx_discard')
    ## t=36
    mov(isr, null).side(1)		# discard any partial input
    jmp('start').side(1) [6]	# again.
    label('rx_valid')
    ## t=36
    in_(pins, 1).side(1)		# read data
    push(iffull | noblock).side(1) [6] # to rx fifo when complete
    wrap()

#--------------------------------------------------#

@rp2.asm_pio(
    sideset_init=(
        rp2.PIO.OUT_LOW,		# clock
    ),
    out_init=(
        rp2.PIO.OUT_LOW,		# /pulse (open-drain)
    ),
)
def receiver_init_prog():
    # .side_set 1
    set(pindirs, 0).side(0)		# clear /pulse
    set(pins, 0).side(0)
    wait(0, pin, 0).side(0)	# avoid some cases of misalignment

#--------------------------------------------------#

class Receiver:

    def __init__(self, i_sm, data_in_pin, npulse_pin, clock_pin):
        assert i_sm in (0, 2, 4, 6)
        self._sm = rp2.StateMachine(
            i_sm,
            freq=machine.freq(),
            prog=receiver_prog,
            in_shiftdir=rp2.PIO.SHIFT_LEFT,
            push_thresh=30,
            # %osr is used to copy pulse value from pins to pindirs
            pull_thresh=1,
            out_shiftdir=rp2.PIO.SHIFT_RIGHT,
            in_base=data_in_pin,
            out_base=npulse_pin,
            set_base=npulse_pin,
            sideset_base=clock_pin,
            jmp_pin=data_in_pin,
        )
        for opcode in receiver_init_prog[0]:
            self._sm.exec(opcode)
        self._sm.active(True)
        return

    def read(self):
        # Detect errors, eg clock stopped?
        return self._sm.get() if self._sm.rx_fifo() > 0 else None

    def read_array(self, buf):
        for i in range(len(buf)):
            if self._sm.rx_fifo() == 0:
                return i
            buf[i] = self._sm.get()
        return len(buf)

    def read_blocking(self):
        return self._sm.get()

    def read_array_blocking(self, buf):
        for i in range(len(buf)):
            buf[i] = self._sm.get()
        return len(buf)

#---------------------------------------------------------------------#

@rp2.asm_pio(
    fifo_join=rp2.PIO.JOIN_TX,
    out_init=(
        rp2.PIO.OUT_LOW,	# data-out
    ),
    set_init=(
        rp2.PIO.OUT_LOW,	# data-out (again)
    ),
)
def transmitter_prog(
    TX_START_IRQ=TX_START_IRQ,
):
    wrap_target()
    label('start')
    ## t=0 (+/-1)
    set(pins, 0)			# data-out=0 (stop)
    wait(1, irq, rel(TX_START_IRQ))	# synch to clock, clearing irq
    ## t=8
    set(pins, 1) [6]			# data-out=1 (start)
    ## Note TX is 20 clocks behind RX, so pulse will be stable.
    ## T=15
    mov(y, pins)			# copy pulse input pin
    ## t=16
    mov(pins, y)			# data-out=pulse
    jmp(not_osre, 'tx_busy') [6]
    label('tx_idle')
    ## t=24
    set(pins, 0)			# data-out=valid (0)
    ## Try to refill %osr
    mov(x, invert(status))		# x=0 => tx fifo is empty
    jmp(not_x, 'tx_skip')
    label('tx_load')
    pull()				# reload %osr
    label('tx_skip')
    ## t=27 (empty) or 28 (refilled)
    out(null, 2)			# left-justify 30 bits
    jmp('start') [10]			# note clean delay on refill

    label('tx_busy')
    ## t=24
    set(pins, 1) [7]			# data-out=valid (1)
    ## t=32
    out(pins, 1) [7]			# data-out=data
    wrap()



# src/rp2_common/hardware_pio/include/hardware/pio.h
# sm_config_set_mov_status(...) {
#
# status_sel << PIO_SM0_EXECCTRL_STATUS_SEL_LSB	// 0 << 4.
# PIO_SM0_EXECCTRL_STATUS_SEL_BITS		// 0x00000010.
# status_n << PIO_SM0_EXECCTRL_STATUS_N_LSB	// 1 << 0.
# PIO_SM0_EXECCTRL_STATUS_N_BITS		// 0x0000000f
#
# rp2._PROG_EXECCTRL = const(3)
transmitter_prog[3] |= 1

class Transmitter:

    def __init__(self, i_sm, data_out_pin, npulse_pin):
        assert i_sm in (1, 3, 5, 7)
        self._sm = rp2.StateMachine(
            i_sm,
            freq=machine.freq(),
            prog=transmitter_prog,
            out_shiftdir=rp2.PIO.SHIFT_LEFT,
            pull_thresh=32,
            in_base=npulse_pin,
            out_base=data_out_pin,
            set_base=data_out_pin,
        )
        # Wait for RX or WDOG to be enabled.
        #pio_interrupt_clear(pio, TX_START_IRQ + sm)
        self._sm.active(True)

    def write(self, data):
        # Detect errors, eg clock stopped?
        if self._sm.tx_fifo() == 8:
            return 0
        self._sm.put(data)
        return 1

    def write_array(self, buf):
        for i in range(len(buf)):
            if self._sm.tx_fifo() == 8:
                return i
            self._sm.put(buf[i])
        return len(buf)

    def write_blocking(self, data):
        self._sm.put(data)
        return 1

    def write_array_blocking(self, buf):
        for i in range(len(buf)):
            self._sm.put(buf[i])
        return len(buf)

#--#
