#!/usr/bin/env python
# select_events.py


from __future__ import print_function

__doc__ = """Select events for a new file"""

import datetime
import gzip
import matplotlib as mpl
import matplotlib.backends.backend_gtk as mplgtk
import matplotlib.pyplot as plt
import numpy as np
import optparse
import os
import re
import shutil
import sys

from glob import glob

import pygtk
pygtk.require ('2.0')
import gtk
if gtk.pygtk_version < (2, 4, 0):
    print ('PyGtk 2.4.0 or later is required')
    raise SystemExit
import gobject

import aradecode
from vars_class import Vars

class Select (object):

    def run (self):
        usage = '%prog {[options]} [outfile] [infile] {[infile]...}'
        self.parser = parser = optparse.OptionParser (usage=usage)

        parser.add_option ('-t', '--min-time', dest='min_time',
                default=None,
                metavar='YYYY-MM-DD HH:MM:SS',
                help='minimum time to retain')
        parser.add_option ('-T', '--max-time', dest='max_time',
                default=None,
                metavar='YYYY-MM-DD HH:MM:SS',
                help='maximum time to retain')
        parser.add_option ('-s', '--part-of-second', dest='part_of_second',
                default=-1, type=float, metavar='FRACTION',
                help='require times close to FRACTION of each second')
        parser.add_option ('-w', '--within', dest='within',
                default=.1, type=float, metavar='WITHIN',
                help='require times WITHIN fraction of --part-of-second')
        parser.add_option ('-n', '--n-events', dest='n_events',
                default=0, type=int, metavar='N',
                help='store N events per outfile '
                '(will add "_[N].dat" to given outfile name)')

        opts, args = self.opts, self.args = parser.parse_args ()

        if len (args) < 2:
            parser.error (
                    'must provide output file and at least one input file')

        self.outfile = args[0]
        self.infiles = args[1:]

        for infile in self.infiles:
            if not os.path.isfile (infile):
                parser.error ('could not find "{0}"'.format (infile))
        outdir = os.path.dirname (self.outfile)
        if outdir and not os.path.isdir (outdir):
            parser.error ('output directory "{0}" does not exist'.format (
                outdir))

        self.min_time = self.parse_times (self.opts.min_time)
        self.max_time = self.parse_times (self.opts.max_time)

        self.handle_files ()


    @staticmethod
    def parse_times (time_str):
        """Parse time string."""
        if time_str is None:
            return None
        time_re = r'(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})'
        m = re.match (time_re, time_str)
        numbers = map (int,m.groups ())
        t = datetime.datetime (*numbers)
        return t


    def handle_files (self):
        """Handle files."""
        blobs = [[]]

        print ('Handling input...')
        N = 0
        for infile in self.infiles:
            print ('- {0} ...'.format (infile), end='')
            n = 0
            astr = aradecode.ara_stream (gzip.GzipFile (infile))
            for ev in astr:
                t = ev.get_unix_datetime ()
                if self.min_time is not None:
                    if not self.min_time <= t:
                        continue
                if self.max_time is not None:
                    if not t <= self.max_time:
                        break
                if self.opts.part_of_second >= 0:
                    part_of_second = 1e-6 * t.microsecond
                    dt = part_of_second - self.opts.part_of_second
                    if abs (dt) > self.opts.within:
                        continue
                n += 1
                N += 1
                blobs[-1].append (ev.binary)
                n_blob = len (blobs[-1])
                if self.opts.n_events and n_blob == self.opts.n_events:
                    blobs.append ([])
            print (' {0} kept.'.format (n))


        print ('{0} events kept in total.'.format (N))

        print ('Writing output...')
        if self.opts.n_events == 0:
            print ('* {0} ...'.format (self.outfile))
            with gzip.GzipFile (self.outfile, 'wb') as f:
                binary = ''.join (blobs[0])
                f.write (binary)
        else:
            for n_file, file_blobs in enumerate (blobs):
                outfile = '{0}_{1:05d}.dat'.format (self.outfile, n_file)
                print ('* {0} ...'.format (outfile))
                f = gzip.GzipFile (outfile, 'wb')
                binary = ''.join (file_blobs)
                f.write (binary)
                f.close ()

        print ('Done.')

if __name__ == '__main__':
    Select ().run ()
