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
   // Note:
   // wdog generates clock output
   // tx drives data_out
   int data_out_pin = 8;	// GP8  -> 11 (UART1 TX) [out]
   int clock_pin = 6;		// GP6  ->  9 (SPI0 SCK) [out]
   int nerror_pin = 7;		// GP7  -> 10 (SPI0 TX) [in+out, od]
   int npulse_pin = 10;		// GP10 -> 14 (SPI1 SCK) [in]
   // Pins for receive:
   // Connect data-out to data-in
   // RX outputs to clock and npulse
   int data_in_pin = 9;		// GP9  -> 12 (UART1 RX) [in]
   int rx_clock_pin = 14;	// GP14 -> 19 (GP14) [out]
   int rx_npulse_pin = 15;	// GP15 -> 20 (GP15) [in+out, od]

   int xmit_sm = 1;
   int wdog_sm = 0;
   int recv_sm = 2;

   // Configure the /pulse gpio that is input to TX
   gpio_init(npulse_pin);
   gpio_pull_up(npulse_pin);
   gpio_set_dir(npulse_pin, /*output=*/true);
   gpio_put(npulse_pin, 1);
   hw_set_bits(&(pio->input_sync_bypass), 1 << npulse_pin);

   // Transmit must be enabled first so it stays ahead of
   // frame start IRQs.
   uint xmit_offset = pio_add_program(pio, &psst_xmit_program);
   psst_xmit_program_init(pio, xmit_sm, xmit_offset,
			  data_out_pin,
			  npulse_pin);

   uint wdog_offset = pio_add_program(pio, &psst_wdog_program);
   psst_wdog_program_init(pio, wdog_sm, wdog_offset,
			  clock_pin,
			  nerror_pin);

   uint recv_offset = pio_add_program(pio, &psst_recv_program);
   psst_recv_program_init(pio, recv_sm, recv_offset,
			  data_in_pin,
			  rx_npulse_pin,
			  rx_clock_pin);

   n_txrx[3] = 123;
   i_txrx = 3;
   pio_sm_put_blocking(pio, xmit_sm, -1);
   psst_wdog_pet_blocking(pio, wdog_sm, 1);

   for (;;) {
      int n;
      (void) psst_read_blocking(pio, recv_sm, &n, 1);
      i_txrx = (i_txrx + 1) % 32;
      n_txrx[i_txrx] = n + 1;
#   if 1
      psst_wdog_pet_blocking(pio, wdog_sm, 1);
#   endif
      (void) psst_write_blocking(pio, xmit_sm, &(n_txrx[i_txrx]), 1);
      gpio_xor_mask(1 << npulse_pin);
   }

}

/**/
