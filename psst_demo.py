#!micropython
#
# $ ampy -p /dev/cuaU1 put psst.py
# $ ampy -p /dev/cuaU1 put psst_demo.py
#
# >>> import psst_demo
# >>> psst_demo.demo()
# MHz=125.0
# Get: 0x3fffffff
# Put: 6
# Get: 0x2a5a0006
# Put: 7
# Get: 0x2a5a0007
# ...

from psst import Watchdog, Transmitter, Receiver

import array
import time

import machine

#---------------------------------------------------------------------#

def demo():
    # Note all SMs must be on the same PIO for pin sharing -
    # pad mux is exclusive PIO0 or PIO1.
    #PIO pio = pio0;

    xmit_sm = const(1)
    wdog_sm = const(0)
    recv_sm = const(2)

    # All pins are free to move independently.
    # Pins for watchdog and transmit:
    npulse_pin = 2		# GP2 ->  4 open-drain
    nerror_pin = 3		# GP3 ->  5 open-drain
    clock_pin = 4		# GP4 ->  6 output
    data_out_pin = 5		# GP5 ->  7 (to data-in)
    # Pins for receive:
    data_in_pin = 6		# GP6 ->  9 (from data-out)
    rx_clock_pin = 7		# GP7 -> 10 output
    rx_npulse_pin = 8		# GP8 -> 11 open-drain

    print(f'MHz={machine.freq()/1e6}')

    # Configure the /pulse gpio that is input to TX
    #gpio_init(npulse_pin)
    #gpio_pull_up(npulse_pin);
    #gpio_set_dir(npulse_pin, /*output=*/true);
    #gpio_put(npulse_pin, 1);
    #hw_set_bits(&(pio->input_sync_bypass), 1 << npulse_pin);

    # Transmit must be enabled first so it stays ahead of
    # frame start IRQs.
    xmit = Transmitter(xmit_sm, data_out_pin, npulse_pin)
    wdog = Watchdog(wdog_sm, clock_pin, nerror_pin)
    recv = Receiver(recv_sm, data_in_pin, rx_npulse_pin, rx_clock_pin)

    xmit.write_blocking(-1)
    wdog.pet_blocking(1)

    n = 5
    while True:
        if True:
            x = recv.read_blocking()
            print('Get:', hex(x))
        else:
            a = array.array('I', [0])
            recv.read_array_blocking(a)
            print('Get:', [hex(x) for x in a])
        n = n + 1
        wdog.pet(3, 100)
        xmit.write_blocking(0x2a5a_0000 + n)  # 30 bits
        print('Put:', n)
        time.sleep(0.100)
        #gpio_xor_mask(1 << npulse_pin);

#--#
