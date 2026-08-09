"""Modbus TCP client for FoxESS EV Charger protocol 1.6."""
from __future__ import annotations

import logging
import socket
import threading

_LOGGER = logging.getLogger(__name__)

FC_READ_HOLDING = 0x03
FC_WRITE_SINGLE = 0x06
FC_WRITE_MULTIPLE = 0x10

WRITE_ONLY_REGISTERS = {0x4000, 0x4001, 0x4002, 0x4003}
READ_WRITE_REGISTERS = {
    0x3000, 0x3001, 0x3002, 0x3003, 0x3004, 0x3005,
    0x3006, 0x3007, 0x3008, 0x300A, 0x300B,
}


class FoxESSModbusClient:
    """Small synchronous Modbus TCP client using raw sockets."""

    def __init__(self, host: str, port: int, slave_id: int) -> None:
        self._host = host
        self._port = port
        self._slave_id = slave_id
        self._tid = 0
        self._lock = threading.Lock()

    def _next_tid(self) -> int:
        self._tid = (self._tid + 1) & 0xFFFF
        if self._tid == 0:
            self._tid = 1
        return self._tid

    @staticmethod
    def _recv_exact(sock: socket.socket, size: int) -> bytes:
        data = bytearray()
        while len(data) < size:
            chunk = sock.recv(size - len(data))
            if not chunk:
                raise ConnectionError("Modbus TCP connection closed unexpectedly")
            data.extend(chunk)
        return bytes(data)

    def _transact(self, pdu: bytes, timeout: float = 5.0) -> bytes | None:
        """Send one Modbus request and return its PDU response."""
        with self._lock:
            tid = self._next_tid()
            request = (
                tid.to_bytes(2, "big")
                + b"\x00\x00"
                + (1 + len(pdu)).to_bytes(2, "big")
                + self._slave_id.to_bytes(1, "big")
                + pdu
            )
            try:
                with socket.create_connection((self._host, self._port), timeout=timeout) as sock:
                    sock.settimeout(timeout)
                    sock.sendall(request)
                    header = self._recv_exact(sock, 7)
                    response_tid = int.from_bytes(header[0:2], "big")
                    protocol_id = int.from_bytes(header[2:4], "big")
                    length = int.from_bytes(header[4:6], "big")
                    unit_id = header[6]
                    if response_tid != tid:
                        raise ValueError(f"Transaction ID mismatch: {response_tid} != {tid}")
                    if protocol_id != 0:
                        raise ValueError(f"Invalid Modbus protocol ID: {protocol_id}")
                    if unit_id != self._slave_id:
                        raise ValueError(f"Unit ID mismatch: {unit_id} != {self._slave_id}")
                    if length < 2:
                        raise ValueError(f"Invalid Modbus response length: {length}")
                    return self._recv_exact(sock, length - 1)
            except (OSError, ConnectionError, TimeoutError, ValueError) as ex:
                _LOGGER.error(
                    "Modbus TCP %s:%s unit=%s communication error: %s",
                    self._host, self._port, self._slave_id, ex,
                )
                return None

    @staticmethod
    def _exception(response_pdu: bytes, function_code: int, address: int) -> bool:
        if len(response_pdu) >= 2 and response_pdu[0] == (function_code | 0x80):
            _LOGGER.error(
                "Modbus FC%02X exception 0x%02X at register 0x%04X",
                function_code, response_pdu[1], address,
            )
            return True
        return False

    def read_registers(self, address: int, count: int) -> list[int] | None:
        """Read holding registers with function code 0x03."""
        if not 1 <= count <= 125:
            raise ValueError("Register count must be between 1 and 125")
        pdu = bytes([FC_READ_HOLDING]) + address.to_bytes(2, "big") + count.to_bytes(2, "big")
        response = self._transact(pdu)
        if response is None or self._exception(response, FC_READ_HOLDING, address):
            return None
        if len(response) < 2 or response[0] != FC_READ_HOLDING:
            _LOGGER.error("Unexpected FC03 response at 0x%04X: %s", address, response.hex())
            return None
        byte_count = response[1]
        expected = count * 2
        payload = response[2:]
        if byte_count != expected or len(payload) != expected:
            _LOGGER.error(
                "Invalid FC03 payload at 0x%04X: expected %d bytes, got %d/%d",
                address, expected, byte_count, len(payload),
            )
            return None
        registers = [int.from_bytes(payload[i:i + 2], "big") for i in range(0, expected, 2)]
        _LOGGER.debug("FC03 read 0x%04X count=%d -> %s", address, count, registers)
        return registers

    def read_register(self, address: int) -> int | None:
        regs = self.read_registers(address, 1)
        return regs[0] if regs else None

    def read_uint32(self, address: int) -> int | None:
        regs = self.read_registers(address, 2)
        if regs and len(regs) == 2:
            return (regs[0] << 16) | regs[1]
        return None


    def read_ascii(self, address: int, count: int) -> str | None:
        """Read big-endian ASCII stored in holding registers."""
        regs = self.read_registers(address, count)
        if regs is None:
            return None
        raw = b"".join(register.to_bytes(2, "big") for register in regs)
        return raw.split(b"\x00", 1)[0].decode("ascii", errors="replace").strip()

    def write_holding_register(self, address: int, value: int) -> bool:
        """Write according to protocol 1.6: W/R=FC16, W-only=FC06."""
        if not 0 <= value <= 0xFFFF:
            raise ValueError("Register value must fit in UINT16")
        if address in WRITE_ONLY_REGISTERS:
            return self._write_single(address, value)
        if address in READ_WRITE_REGISTERS:
            return self._write_multiple(address, [value])
        _LOGGER.error("Write attempt to non-writable register 0x%04X", address)
        return False

    def _write_single(self, address: int, value: int) -> bool:
        pdu = bytes([FC_WRITE_SINGLE]) + address.to_bytes(2, "big") + value.to_bytes(2, "big")
        response = self._transact(pdu)
        if response is None or self._exception(response, FC_WRITE_SINGLE, address):
            return False
        expected = pdu
        if response != expected:
            _LOGGER.error("Unexpected FC06 response at 0x%04X: %s", address, response.hex())
            return False
        _LOGGER.debug("FC06 write 0x%04X=%d succeeded", address, value)
        return True

    def _write_multiple(self, address: int, values: list[int]) -> bool:
        count = len(values)
        payload = b"".join(value.to_bytes(2, "big") for value in values)
        pdu = (
            bytes([FC_WRITE_MULTIPLE])
            + address.to_bytes(2, "big")
            + count.to_bytes(2, "big")
            + len(payload).to_bytes(1, "big")
            + payload
        )
        response = self._transact(pdu)
        if response is None or self._exception(response, FC_WRITE_MULTIPLE, address):
            return False
        expected = bytes([FC_WRITE_MULTIPLE]) + address.to_bytes(2, "big") + count.to_bytes(2, "big")
        if response != expected:
            _LOGGER.error("Unexpected FC10 response at 0x%04X: %s", address, response.hex())
            return False
        _LOGGER.debug("FC10 write 0x%04X values=%s succeeded", address, values)
        return True

    def disconnect(self) -> None:
        """Connections are opened per transaction, so nothing is retained."""
