# aradecode.py

import gzip
import numpy as np
import os
import csv

from struct import unpack


def decode_ara_blob(f):
   buf = f.read(8)
   data_type, station_id, version, subversion, nbytes = unpack("<4Bi", buf)
   if data_type == 1:
       return atri_event(station_id, f)
   else:
       buf += f.read(nbytes-8)
       return buf


class ara_stream(object):
   def __init__(self, f):
       self.f = f

   def __iter__(self):
       return self

   def next(self):
       try:
           return decode_ara_blob(self.f)
       except:
           raise StopIteration


class atri_event(object):
   def __init__(self, station_id, f):
       self.station_id = station_id
       f.seek(8, 1)
       self.unix, self.unix_us, self.sw_event_id, nb, self.timestamp, \
               self.pps, self.event_id, self.version_id, self.nblk = \
               unpack("<q6i2h", f.read(36))
       self.trigger_info = unpack("<4i", f.read(16))
       self.trigger_blk  = unpack("4B", f.read(4))
       self.readouts     = []
       for i in range(self.nblk):
           self.readouts.append(atri_readout(f)) 

   def get_waveform(self, dda, ch, cal):
       w = np.zeros(self.nblk / 4 * 64, 'd')
       ix0 = 0
       for i in range(dda, self.nblk, 4):
           w[ix0:ix0+64] = np.array(self.readouts[i].samples[ch], 'd') \
                   - cal.ped[dda, self.readouts[i].irs_blk, ch]
           ix0 += 64
       return w

   def __str__(self):
       txt = "EV: %6d %d %d %d" % (
               self.event_id, self.pps, self.timestamp, self.nblk)
       return txt


class atri_readout(object):
   def __init__(self, f):
       self.irs_blk, self.mask = unpack("<2h", f.read(4))
       self.samples = [ ]
       for i in range(8):
           if self.mask >> i & 1 == 1:
               self.samples.append(unpack("<64h", f.read(128)))


class ped_cal(object):
   def __init__(self, f=None):
       self.ped = np.zeros([4, 512, 8, 64], 'd')
       if f is None: return
       reader = csv.reader(f, delimiter=' ')
       for r in reader:
           ir = [int(x) for x in r]
           chip, block, ch = ir[0:3]
           self.ped[chip, block, ch, :] = np.array(ir[3:], 'd')
