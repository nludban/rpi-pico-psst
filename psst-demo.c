//#include <boards/adafruit_itsybitsy_rp2040.h>

#include "psst.pio.h"

#include <stdio.h>

#include <hardware/gpio.h>

#include <hardware/pio.h>
#include <hardware/clocks.h>

#include <pico/stdlib.h>

static inline void put_pixel(uint32_t pixel_grb) {
   pio_sm_put_blocking(pio0, /*sm=*/1, pixel_grb << 8u);
}


int n_txrx[32];
int i_txrx;

int
main()
{
   setup_default_uart();
   //stdio_init_all();

   PIO pio = pio0;

   // All pins are free to move independently.
   // Pins for watchdog and transmit:
   int data_in_pin = 9;		// GP9  -> 12 (UART1 RX)
   int data_out_pin = 8;	// GP8  -> 11 (UART1 TX)
   int clock_pin = 6;		// GP6  ->  9 (SPI0 SCK)
   int nerror_pin = 7;		// GP7  -> 10 (SPI0 TX)
   int pulse_pin = 10;		// GP10 -> 14 (SPI1 SCK)
   // Pins for receive:
   int rx_clock_pin = 14;
   int rx_pulse_pin = 15;

   int xmit_sm = 1;
   int wdog_sm = 0;
   int recv_sm = 2;

   // Transmit must be enabled first so it stays ahead of
   // frame start IRQs.
   uint xmit_offset = pio_add_program(pio, &psst_xmit_program);
   psst_xmit_program_init(pio, xmit_sm, xmit_offset,
			  data_out_pin,
			  pulse_pin);

   uint wdog_offset = pio_add_program(pio, &psst_wdog_program);
   psst_wdog_program_init(pio, wdog_sm, wdog_offset,
			  clock_pin,
			  nerror_pin);

   uint recv_offset = pio_add_program(pio, &psst_recv_program);
   psst_recv_program_init(pio, recv_sm, recv_offset,
			  data_in_pin,
			  rx_pulse_pin,
			  rx_clock_pin);

   pio_gpio_init(pio, rx_pulse_pin);
   pio_gpio_init(pio, rx_clock_pin);

   n_txrx[3] = 123;
   i_txrx = 3;
   pio_sm_put_blocking(pio, xmit_sm, -1);
   psst_wdog_pet(pio, wdog_sm, 1);

   for (;;) {
      int n = pio_sm_get_blocking(pio, recv_sm);
      i_txrx = (i_txrx + 1) % 32;
      n_txrx[i_txrx] = n + 1;
      psst_wdog_pet(pio, wdog_sm, 1);
      pio_sm_put_blocking(pio, xmit_sm, n_txrx[i_txrx]);
   }

}

/**/
