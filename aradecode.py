# aradecode.py

"""Decode binary ARA data.

This code is largely borrowed from Kael Hanson.

"""

import datetime
import gzip
import numpy as np
import os
import csv

from struct import unpack


def decode_ara_blob(f):
    buf = f.read(8)
    data_type, station_id, version, subversion, nbytes = unpack("<4Bi", buf)
    if data_type == 1:
        return atri_event(station_id, f, buf)
    else:
        buf += f.read(nbytes-8)
        return buf


class ara_stream(object):
    def __init__(self, f):
        """
        Parameters
        ----------
        f : gzip _io.BufferedReader
        """
        self.f = f

    def __iter__(self):
        return self

    def __next__(self):
        try:
            return decode_ara_blob(self.f)
        except:
            raise StopIteration


class atri_event(object):
    def __init__(self, station_id, f, buf):
        binary_parts = [buf]
        self.station_id = station_id
        buf = f.read (8)
        binary_parts.append (buf)
        buf = f.read(36)
        binary_parts.append (buf)
        self.unix, self.unix_us, self.sw_event_id, nb, self.timestamp, \
                self.pps, self.event_id, self.version_id, self.nblk = \
                unpack("<q6i2h", buf)
        buf = f.read(16)
        binary_parts.append (buf)
        self.trigger_info = unpack("<4i", buf)
        buf = f.read(4)
        binary_parts.append (buf)
        self.trigger_blk  = unpack("4B", buf)
        self.readouts     = []
        for i in range(self.nblk):
            self.readouts.append(atri_readout(f)) 
            binary_parts.append (self.readouts[-1].binary)
        self.binary = b''.join (binary_parts)

    def get_waveform(self, dda, ch, cal):
        w = np.zeros(int(self.nblk / 4 * 64), 'd')
        ix0 = 0
        for i in range(dda, self.nblk, 4):
            w[ix0:ix0+64] = np.array(self.readouts[i].samples[ch], 'd') \
                    - cal.ped[dda, self.readouts[i].irs_blk, ch]
            ix0 += 64
        return w

    def get_unix_datetime (self):
        t = datetime.datetime.utcfromtimestamp (self.unix + 1e-6 * self.unix_us)
        return t

    def __str__(self):
        txt = "EV: %6d %d %d %d" % (
                self.event_id, self.pps, self.timestamp, self.nblk)
        return txt


class atri_readout(object):
    def __init__(self, f: bytes):
        binary_parts = []
        buf = f.read (4)
        binary_parts.append (buf)
        self.irs_blk, self.mask = unpack("<2h", buf)
        self.samples = [ ]
        for i in range(8):
            if self.mask >> i & 1 == 1:
                # Checks if the ith bit in the bitmask is set/true
                buf = f.read(128)
                binary_parts.append (buf)
                self.samples.append(unpack("<64h", buf))
        self.binary = b''.join (binary_parts)


class ped_cal(object):
    def __init__(self, f=None):
        self.ped = np.zeros([4, 512, 8, 64], 'd')
        if f is None: return
        reader = csv.reader(f, delimiter=' ')
        for r in reader:
            ir = [int(x) for x in r]
            chip, block, ch = ir[0:3]
            self.ped[chip, block, ch, :] = np.array(ir[3:], 'd')
