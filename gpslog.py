import argparse
import csv
import os
import signal
import subprocess
import sys
import threading
import time
from math import nan
from typing import List
from typing import Optional
from typing import Union

import adafruit_gps
import serial

if sys.version_info < (3, 8):
    import importlib_metadata
else:
    import importlib.metadata as importlib_metadata


CNAMES = ['timestamp_utc', 'lat', 'lon', 'alt', 'speed', 'satellites']


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog='gpslog')
    parser.add_argument(
        '-V', '--version',
        action='version',
        version=f'%(prog)s {importlib_metadata.version("gpslog")}',
    )
    parser.add_argument(
        'output',
        help='define the outputfile (csv)',
        type=str,
    )
    parser.add_argument(
        '-i', '--interval',
        help='set the logging interval in seconds',
        default=1,
        type=int,
    )
    parser.add_argument(
        '-v', '--verbose',
        help='print readings to stdout',
        action='store_true',
    )
    args = parser.parse_args()
    return args


def _stop() -> None:
    pid_cmd = ['pgrep', '-f', '.gpslog']
    pid = subprocess.check_output(pid_cmd).decode().split('\n')[0]
    kill_cmd = ['kill', '-s', 'SIGTERM', pid]
    subprocess.run(kill_cmd)


class GPS(threading.Thread):
    '''Class for reading the adafruit gps'''

    def __init__(self) -> None:
        threading.Thread.__init__(self)
        self.uart: serial.Serial = serial.Serial(
            '/dev/ttyS0', baudrate=9600, timeout=10,
        )
        self.gps: adafruit_gps.GPS = adafruit_gps.GPS(self.uart, debug=False)
        self.gps.send_command(b'PMTK314,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0')
        self.gps.send_command(b'PMTK220,1000')
        self.running = True

        self.has_fix: Optional[bool] = None
        self.latitude: Optional[float] = None
        self.longitude: Optional[float] = None
        self.satellites: Optional[Union[int, float]] = None
        self.timestamp: Optional[str] = None
        self.alt: Optional[float] = None
        self.speed: Optional[float] = None

    def run(self) -> None:
        '''start thread and get values'''
        while self.running:
            try:
                self.gps.update()
                self.has_fix = self.gps.has_fix
                if self.gps.satellites is not None:
                    self.satellites = self.gps.satellites
                else:
                    self.satellites = nan

                if self.gps.latitude is not None:
                    self.latitude = self.gps.latitude
                else:
                    self.latitude = nan

                if self.gps.longitude is not None:
                    self.longitude = self.gps.longitude
                else:
                    self.longitude = nan

                if self.gps.altitude_m is not None:
                    self.alt = self.gps.altitude_m
                else:
                    self.alt = nan

                if self.gps.speed_knots is not None:
                    self.speed = self.gps.speed_knots
                else:
                    self.speed = nan

                if self.gps.timestamp_utc is not None:
                    self.timestamp = time.strftime(
                        '%Y-%m-%d %H:%M:%S',
                        self.gps.timestamp_utc,
                    )
                time.sleep(.1)
            except Exception:
                continue

    def stop(self) -> None:
        '''close uart port when terminating'''
        self.uart.close()


def _knots_tp_kph(knots: Union[int, float]) -> float:
    return knots * 1.852


def _write_header(filename: str, cnames: List[str]) -> None:
    with open(filename, 'w', newline='') as f:
        writer = csv.DictWriter(f, CNAMES)
        writer.writeheader()


def _exit_program(signum, frame) -> None:
    gps.running = False
    gps.stop()
    gps.join()
    exit(0)


def main() -> None:
    args = parse_arguments()
    gps.start()
    if args.output is not None:
        if not os.path.exists(args.output):
            _write_header(args.output, CNAMES)
        while True:
            if gps.has_fix:
                with open(args.output, 'a', newline='') as f:
                    writer = csv.DictWriter(f, CNAMES)
                    speed = gps.speed
                    if speed is not None:
                        speed_kph = _knots_tp_kph(speed)
                    else:
                        speed_kph = nan
                    log = {
                        'timestamp_utc': gps.timestamp,
                        'lat': gps.latitude,
                        'lon': gps.longitude,
                        'alt': gps.latitude,
                        'speed': speed_kph,
                        'satellites': gps.satellites,
                    }
                    if args.verbose:
                        print(
                            f"{log['timestamp_utc']}: lat:{log['lat']}° "
                            f"lon:{log['lon']}° alt:{log['alt'] } m OSL "
                            f"speed:{log['speed']} kph",
                        )
                    writer.writerow(log)
            time.sleep(args.interval)


gps = GPS()
signal.signal(signal.SIGTERM, _exit_program)

if __name__ == '__main__':
    main()
