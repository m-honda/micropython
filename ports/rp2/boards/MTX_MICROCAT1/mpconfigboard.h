/*
 * Copyright (c) 2025 MechaTracks Co., Ltd.
 *
 * SPDX-License-Identifier: MIT
 */

// Board and hardware specific configuration
#define MICROPY_HW_BOARD_NAME                   "MechaTracks MicroCat.1"
#define MICROPY_HW_FLASH_STORAGE_BYTES          (PICO_FLASH_SIZE_BYTES - 1536 * 1024)

// Enable networking.
#define MICROPY_PY_NETWORK 1
#define MICROPY_PY_NETWORK_PPP_LWIP 1
#define MICROPY_PY_NETWORK_HOSTNAME_DEFAULT     "MTXMICROCAT1"

#define MEM_SIZE 8 * 1024
#define PBUF_POOL_SIZE 32
#define PBUF_POOL_BUFSIZE 256
#define TCP_MSS 216
#define PPP_MRU 256

// USB VID/PID
#define MICROPY_HW_USB_VID (0x388B)
#define MICROPY_HW_USB_PID (0xCA71)

// UART0
#define MICROPY_HW_UART0_TX  (0)
#define MICROPY_HW_UART0_RX  (1)
#define MICROPY_HW_UART0_CTS (2)
#define MICROPY_HW_UART0_RTS (3)

// UART1
#define MICROPY_HW_UART1_TX  (36)
#define MICROPY_HW_UART1_RX  (37)
#define MICROPY_HW_UART1_CTS (38)
#define MICROPY_HW_UART1_RTS (39)

// I2C0
#define MICROPY_HW_I2C0_SCL  (5)
#define MICROPY_HW_I2C0_SDA  (4)

// I2C1
#define MICROPY_HW_I2C1_SCL  (31)
#define MICROPY_HW_I2C1_SDA  (30)

// SPI0
#define MICROPY_HW_SPI0_SCK  (22)
#define MICROPY_HW_SPI0_MOSI (23)
#define MICROPY_HW_SPI0_MISO (20)

// SPI1
#define MICROPY_HW_SPI1_SCK  (10)
#define MICROPY_HW_SPI1_MOSI (11)
#define MICROPY_HW_SPI1_MISO (8)

// PSRAM
#define MICROPY_HW_PSRAM_CS_PIN (47)
#define MICROPY_HW_ENABLE_PSRAM (1)

// For debugging mbedtls - also set
// Debug level (0-4) 1=warning, 2=info, 3=debug, 4=verbose
// #define MODUSSL_MBEDTLS_DEBUG_LEVEL 1

