import csv
import struct
import time
from datetime import datetime, timezone
from pathlib import Path

import smbus2

I2C_BUS = 1
I2C_ADDRESS = 0x76
CSV_PATH = Path(__file__).resolve().parent / "bmp280_readings.csv"
INTERVAL_S = 10


class BMP280Configuration:
    POWER_MODE_FORCED = 1

    def __init__(self) -> None:
        self._power_mode = self.POWER_MODE_FORCED

    @property
    def ctrl_meas(self) -> bytes:
        temperature_os_1x = 1
        pressure_os_1x = 1
        b = temperature_os_1x << 5 | pressure_os_1x << 2 | self._power_mode
        return bytes([b])

    @property
    def config(self) -> bytes:
        standby_time = 5 << 5
        filter_off = 0 << 2
        return bytes([standby_time | filter_off])

    @property
    def power_mode(self) -> int:
        return self._power_mode


class BMP280:
    def __init__(self, configuration: BMP280Configuration) -> None:
        self.configuration = configuration

    def _unpack_u16(self, lo: int, hi: int) -> int:
        return struct.unpack_from("<H", bytes([lo, hi]))[0]

    def _unpack_i16(self, lo: int, hi: int) -> int:
        return struct.unpack_from("<h", bytes([lo, hi]))[0]

    def _load_calibration(self) -> None:
        rxdata = self._read(0x88, 24)
        self._dig_T1 = self._unpack_u16(rxdata[0], rxdata[1])
        self._dig_T2 = self._unpack_i16(rxdata[2], rxdata[3])
        self._dig_T3 = self._unpack_i16(rxdata[4], rxdata[5])
        self._dig_P1 = self._unpack_u16(rxdata[6], rxdata[7])
        self._dig_P2 = self._unpack_i16(rxdata[8], rxdata[9])
        self._dig_P3 = self._unpack_i16(rxdata[10], rxdata[11])
        self._dig_P4 = self._unpack_i16(rxdata[12], rxdata[13])
        self._dig_P5 = self._unpack_i16(rxdata[14], rxdata[15])
        self._dig_P6 = self._unpack_i16(rxdata[16], rxdata[17])
        self._dig_P7 = self._unpack_i16(rxdata[18], rxdata[19])
        self._dig_P8 = self._unpack_i16(rxdata[20], rxdata[21])
        self._dig_P9 = self._unpack_i16(rxdata[22], rxdata[23])

    def _calculate_pressure(self, adc_p: int, t_fine: float) -> float:
        var1 = (t_fine / 2) - 64000
        var2 = var1 * var1 * self._dig_P6 / 32768
        var2 = var2 + var1 * self._dig_P5 * 2
        var2 = (var2 / 4) + (self._dig_P4 * 65536)
        var1 = (self._dig_P3 * var1 * var1 / 524288 + self._dig_P2 * var1) / 524288
        var1 = (1 + var1 / 32768) * self._dig_P1
        if var1 == 0:
            return 0.0
        p = 1048576 - adc_p
        p = (p - (var2 / 4096)) * 6250 / var1
        var1 = self._dig_P9 * p * p / 2147483648
        var2 = p * self._dig_P8 / 32768
        p = p + (var1 + var2 + self._dig_P7) / 16
        return p / 100

    def read_temperature_pressure(self) -> tuple[float, float]:
        if self._configuration.power_mode == BMP280Configuration.POWER_MODE_FORCED:
            self._write(0xF4, self._configuration.ctrl_meas)
            time.sleep(0.005)

        rxdata = self._read(0xF7, 6)
        p_adc = rxdata[0] << 12 | rxdata[1] << 4 | rxdata[2] >> 4
        t_adc = rxdata[3] << 12 | rxdata[4] << 4 | rxdata[5] >> 4

        var1 = (t_adc / 16384 - self._dig_T1 / 1024) * self._dig_T2
        var2 = (
            (t_adc / 131072 - self._dig_T1 / 8192)
            * (t_adc / 131072 - self._dig_T1 / 8192)
        ) * self._dig_T3
        t_fine = var1 + var2
        temp_c = t_fine / 5120
        pressure_hpa = self._calculate_pressure(p_adc, t_fine)
        return temp_c, pressure_hpa

    @property
    def configuration(self) -> BMP280Configuration:
        return self._configuration

    @configuration.setter
    def configuration(self, configuration: BMP280Configuration) -> None:
        self._configuration = configuration
        self._write(0xE0, b"\xb6")
        time.sleep(0.002)
        self._write(0xF4, self._configuration.ctrl_meas)
        time.sleep(0.005)
        self._write(0xF5, self._configuration.config)
        time.sleep(0.04)


def bmp280_sample_row(sensor: BMP280) -> dict[str, object]:
    ts = datetime.now(timezone.utc).isoformat()
    temp_c, pressure_hpa = sensor.read_temperature_pressure()
    return {
        "time": ts,
        "temperature_c": float(temp_c),
        "pressure_hpa": float(pressure_hpa),
    }


class BMP280I2C(BMP280):
    def __init__(self) -> None:
        self._bus = smbus2.SMBus(I2C_BUS)
        self._address = I2C_ADDRESS
        super().__init__(BMP280Configuration())
        self._load_calibration()

    def close(self) -> None:
        self._bus.close()

    def _write(self, register: int, txdata: bytes) -> None:
        for offset, byte in enumerate(txdata):
            self._bus.write_byte_data(self._address, register + offset, byte)

    def _read(self, register: int, nbytes: int) -> bytes:
        return bytes(
            self._bus.read_byte_data(self._address, register + i) for i in range(nbytes)
        )


def main() -> None:
    sensor = BMP280I2C()
    try:
        while True:
            ts = datetime.now(timezone.utc).isoformat()
            temp_c, pressure_hpa = sensor.read_temperature_pressure()
            header_needed = not CSV_PATH.exists() or CSV_PATH.stat().st_size == 0
            with CSV_PATH.open("a", newline="") as f:
                w = csv.writer(f)
                if header_needed:
                    w.writerow(["timestamp_iso", "temperature_c", "pressure_hpa"])
                w.writerow([ts, f"{temp_c:.4f}", f"{pressure_hpa:.2f}"])
            print(ts, temp_c, pressure_hpa)
            time.sleep(INTERVAL_S)
    except KeyboardInterrupt:
        pass
    finally:
        sensor.close()


if __name__ == "__main__":
    main()
