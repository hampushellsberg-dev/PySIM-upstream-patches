# SIMtrace2 firmware: a USB message of several full packets ends without a ZLP

Target: osmocom simtrace2 firmware, `firmware/libcommon/source/host_communication.c`.
The code dates from commit `5b13602` (2019-12-15, "host_communication: Send
zero-length-packet on wMaxPacketSize") and is unchanged in tags `0.9.0` and
`0.9.1` and on master; the patch applies to master `0.9.1-24-g9467005`
(2026-10-23).

## Bug

```c
if (((msgb_length(msg) % ep_size) == 0) && (transferred == ep_size)) {
        /* terminate with ZLP; ... */
        USBD_Write(bep->ep, 0, 0, (TransferCallback) &usb_write_cb, msg);
        return;
}
```

The SAM3S USB HAL (`libchip_sam3s/source/USBD_HAL.c`, `UDP_IsTransferFinished`)
ends a bulk IN transfer once all its data is written ("Other endpoints only
need to transfer all the data") and reports the whole message in
`transferred`. The test above therefore holds for a message of exactly one
packet and for no other. A message of 128, 192 or 256 bytes leaves the board
as full packets with no short packet behind it. A host that reads into a
larger buffer sees no end of transfer and gets the message only when the
board sends its next one. osmo-remsim-client-st2 1.2.0 submits 4096-byte bulk
IN transfers (`src/client/user_simtrace2.c`, `allocate_and_submit_in`).

## Which messages

Card emulation forwards a modem command's data in one RX-DATA message: the
8-byte `simtrace_msg_hdr`, the 6-byte `cardemu_usb_msg_rx_data`, then the Lc
data bytes (`USB_ALLOC_SIZE` is 280, so any Lc fits). Lc `72`, `B2` and `F2`
(114, 178 and 242 bytes) make 128-, 192- and 256-byte messages. Lc `32` makes
a 64-byte message, which the existing branch does terminate.

In a HIL session the command that hits it is the TERMINAL RESPONSE to RECEIVE
DATA: 18 bytes of TLVs (17 below 128 bytes of data) around the channel data
the terminal hands back, so a read of 97, 160 or 224 bytes.

## Harm (observed)

HIL rig, 2026-10-23 12:39:31-12:41:35 CEST: SIMtrace2 in card emulation,
osmo-remsim-client-st2 1.2.0, the YggdraSIM bridge as bankd, a Quectel EC25
modem logging its own side over DIAG.

1. The card asked for the last 160 bytes of a server response (RECEIVE DATA).
   The modem sent the TERMINAL RESPONSE, all 178 data bytes; the board took
   them, queued a 192-byte message and waited for the host's answer.
2. The host never saw the message. The board kept the modem waiting with NULL
   procedure bytes, 5993 of them, for 120 s; the modem then gave up and reset
   the UICC.
3. The board's PTS message after the reset ended the stuck transfer. The
   client hands one message per completed transfer to `process_usb_msg`, so
   it forwarded the held TERMINAL RESPONSE and dropped the PTS message.
4. The bankd sent the held command to the freshly reset card (answer `6F00`).
   The client hands the card's next answer to whatever command the modem is
   on, so `6F00` became the answer to the modem's first SELECT, and every
   answer after it was one command late until the modem reset again.

## Why it looks sudden

Whether a card hits it is set by the byte count of what the server sends.
The card in this rig drains a response in reads of up to 237 bytes, so the
last read is the response length modulo 237, and the same response splits
the same way every time. `repro_zlp_stall.py` over the rig's journal from
2026-08-10 to 2026-10-23: 14,272 drained responses, 14 of them ending in a
read of 160 or 224 bytes, and all 14 held for 120 s. An 871-byte response
failed eight times in a row on 2026-10-07, a 1409-byte one on 2026-09-08 and
again on 2026-10-07, a 397-byte one twice on 2026-10-23. A card that has
worked for weeks fails on every attempt once the server's answer lands on
one of those lengths, and works again when the length changes.

## Fix

`simtrace2-cardem-zlp.patch` sends the ZLP after any message that is a whole
number of packets: the test becomes `transferred == msgb_length(msg)`. The
callback after the ZLP sees `transferred == 0` and frees the buffer as
before, and the added `msgb_length(msg)` test keeps an empty message from
looping. Build and flash as in `guides/SIMTRACE2_CARDEM_GUIDE.md` sections 3
to 5; the image is `firmware/bin/simtrace-cardem-dfu.bin`.

## Hardware repro

In a HIL session through the YggdraSIM bridge, send two malformed ENVELOPEs
from the modem. The bridge answers both itself with `6F00` (its ENVELOPE
check rejects the over-long `D1 81 FF` TLV), so the card never sees either,
and the only difference between them is the USB message length.

```bash
python3 -c 'print("AT+CSIM=364,\"80C20000B1D181FF" + "00" * 174 + "\"")'
python3 -c 'print("AT+CSIM=366,\"80C20000B2D181FF" + "00" * 175 + "\"")'
```

On the unpatched firmware the first answers at once (`+CSIM: 4,"6F00"`) and
the second hangs until the modem resets the UICC. With the patch both answer
at once. A modem that refuses an ENVELOPE over `AT+CSIM` can use any other
command with Lc `B2` against `B1`.

## Files

- `simtrace2-cardem-zlp.patch` -- the fix, against
  `firmware/libcommon/source/host_communication.c`.
- `repro_zlp_stall.py` -- reads the HIL bridge journal on stdin and reports
  held TPDUs by USB message length, and how server responses split into
  RECEIVE DATA reads. Standalone, no YggdraSIM imports.
- `validation.txt` -- its output over the rig's journal, before the patch.

## Stress-test checklist

- [ ] The `AT+CSIM` pair above answers at once for Lc `B1`, `B2`, `72` and
      `F2` on the patched board.
- [ ] Lc `32` (a 64-byte message, the old branch) still answers at once.
- [ ] A HIL session with BIP traffic of several hours: `repro_zlp_stall.py`
      reports no held TPDU, and some RECEIVE DATA bursts end in 160 or 224
      bytes (draw them with a server response of 397 or 871 bytes if none
      occur).
- [ ] The sniffer app built from the same tree still captures (it shares
      `host_communication.c`).
- [ ] usbmon shows one zero-length packet after a 192-byte message and none
      after a 191- or 193-byte one.

## Host side (not patched here)

osmo-remsim-client-st2 1.2.0 `usb_in_xfer_cb` passes each completed transfer
to `process_usb_msg` as one message, which reads one header and drops
whatever follows it. That is how the PTS message in step 3 vanished. With the
firmware fixed every message ends its own transfer, so nothing follows; a
client that walked the buffer by `msg_len` would also survive an unpatched
board, though it would still see the held message late.

## YggdraSIM-side compensation

The bridge never answers a TPDU the modem has abandoned
(`Tools/HilBridge/router.py`): each modem TPDU records its card session (one
per modem reset of the UICC) and a sequence number, the card's answer to any
but the latest TPDU of the current session stays off the modem, a queued
TPDU that a newer one has superseded never reaches the card, and a FETCH,
TERMINAL RESPONSE or GET RESPONSE arriving as the first TPDU after a reset is
dropped unanswered, since none of them can open a card session. That turns
step 4 into one clean reset instead of a run of them; the 120 s hold itself
only the firmware can remove. The drop's warning names the USB message size
when the held command matches this bug (`_simtrace2_unterminated_message_size`),
so on fixed firmware it stops naming one. The guard itself stays: a TERMINAL
RESPONSE the modem still owed has also reached the bridge after resets with
other causes (journal: 2026-08-29, 2026-08-30, 2026-10-19, 2026-10-22), and
answering an abandoned command is wrong whatever held it. Tests: `tests/test_hil_bridge_abandoned_tpdus.py`.
