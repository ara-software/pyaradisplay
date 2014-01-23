#!/usr/bin/env python
# select_events.py


from __future__ import print_function

__doc__ = """Select events for a new file"""

import datetime
import gzip
import numpy as np
import optparse
import os
import re
import shutil
import sys

from glob import glob

import aradecode
from vars_class import Vars

@np.vectorize
def timedelta_in_seconds (dt):
    """Get a timedelta in seconds."""
    return 1e-6 * (
            ((dt.days * 86400 * 1e6) + dt.seconds * 1e6) + dt.microseconds)

class Select (object):

    def run (self):
        usage = '%prog {[options]} [outfile_base] [infile] {[infile]...}'
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
        parser.add_option ('-p', '--pass-early', dest='pass_early',
                default=20, type=float, metavar='DT',
                help='skip file if first event is DT earlier than --min-time')

        parser.add_option ('-l', '--logfile', dest='logfile',
                default='', metavar='FILE',
                help='read run information from FILE')

        opts, args = self.opts, self.args = parser.parse_args ()

        if len (args) < 2:
            parser.error (
                    'must provide output file and at least one input file')

        self.outfile_base = args[0]
        self.infiles = args[1:]

        for infile in self.infiles:
            if not os.path.isfile (infile):
                parser.error ('could not find "{0}"'.format (infile))
        outdir = os.path.dirname (self.outfile_base)
        if outdir and not os.path.isdir (outdir):
            parser.error ('output directory "{0}" does not exist'.format (
                outdir))

        self.min_time = self.parse_times (self.opts.min_time)
        self.max_time = self.parse_times (self.opts.max_time)

        self.handle_logfile ()
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

    def handle_logfile (self):
        self.time_ranges = {}
        if self.opts.logfile:
            with open (self.opts.logfile) as f:
                orig_lines = f.readlines ()
            lines = []
            for line in orig_lines:
                line = re.sub ('#.*', '', line).strip ()
                if line:
                    lines.append (line)
            self.opts.part_of_second, self.opts.within = \
                    map (float, lines[0].split ())
            m = re.match (r'UTC([+-]\d+)', lines[1])
            if m:
                lines.pop (0)
                dt = datetime.timedelta (
                        seconds=-3600 * float (m.group (1)))
            for line in lines[1:]:
                if not line[:-1]:
                    continue
                date1, time1, date2, time2, suffix = line.split ()
                t1 = dt + self.parse_times ('{0} {1}'.format (date1, time1))
                t2 = dt + self.parse_times ('{0} {1}'.format (date2, time2))
                self.time_ranges[suffix] = t1, t2
        t1s = [time_range[0] for time_range in self.time_ranges.itervalues ()]
        t2s = [time_range[1] for time_range in self.time_ranges.itervalues ()]
        self.min_time = min (t1s)
        self.max_time = max (t2s)

    def handle_files (self):
        """Handle files."""
        blobs = dict ((suffix, [[]]) for suffix in self.time_ranges)
        ns = dict ((suffix, 0) for suffix in self.time_ranges)
        blobs[''] = [[]]
        ns[''] = 0

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
                        early_by = timedelta_in_seconds (self.min_time - t)
                        if early_by > self.opts.pass_early:
                            break
                        continue
                if self.max_time is not None:
                    if not t <= self.max_time:
                        break
                if self.opts.part_of_second >= 0:
                    part_of_second = 1e-6 * t.microsecond
                    dt = part_of_second - self.opts.part_of_second
                    if abs (dt) > self.opts.within:
                        continue
                if self.time_ranges:
                    the_suffix = ''
                    for suffix, (t1, t2) in self.time_ranges.iteritems ():
                        if t1 <= t and t <= t2:
                            the_suffix = suffix
                            break
                    if not the_suffix:
                        continue
                else:
                    the_suffix = ''
                n += 1
                N += 1
                blobs[the_suffix][-1].append (ev.binary)
                n_blob = len (blobs[the_suffix][-1])
                if self.opts.n_events and n_blob == self.opts.n_events:
                    blobs[the_suffix].append ([])
            print (' {0} kept.'.format (n))


        print ('{0} events kept in total.'.format (N))

        print ('Writing output...')
        for suffix in sorted (blobs):
            if len (blobs) >= 2 and not suffix:
                continue
            if self.opts.n_events == 0:
                binary = ''.join (blobs[suffix][0])
                if suffix:
                    ending = '_{0}.dat'.format (suffix)
                else:
                    ending = '.dat'
                outfile = '{0}{1}'.format (self.outfile_base, ending)
                print ('* {0} ...'.format (outfile))
                f = gzip.GzipFile (outfile, 'wb')
                f.write (binary)
                f.close ()
            else:
                for n_file, file_blobs in enumerate (blobs):
                    binary = ''.join (file_blobs)
                    if suffix:
                        ending = '_{0}.dat'.format (suffix)
                    else:
                        ending = '.dat'
                    outfile = '{0}{1}_{2:05d}'.format (
                            self.outfile, ending, n_file)
                    print ('* {0} ...'.format (outfile))
                    f = gzip.GzipFile (outfile, 'wb')
                    f.write (binary)
                    f.close ()

        print ('Done.')

if __name__ == '__main__':
    Select ().run ()
