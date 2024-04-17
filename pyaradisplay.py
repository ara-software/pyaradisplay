#!/usr/bin/env python
# pyaradisplay.py


from __future__ import print_function

__doc__ = """Display ARA data.

This is a relatively straightforward Python-based alternative to AraDisplay.
It is not (yet?) a feature-complete port.
"""

import datetime
import gzip
import matplotlib as mpl
mpl.use('GTK3Agg')
import matplotlib.pyplot as plt
import numpy as np
import optparse
import os
import re
import scipy.signal
import shutil
import sys

from glob import glob

import gi
gi.require_version("Gtk", "3.0")

from gi import pygtkcompat
pygtkcompat.enable()
pygtkcompat.enable_gtk(version='3.0')

from gi.repository import Gtk

import aradecode
from vars_class import Vars


class DataSetModel (Gtk.GenericTreeModel):

    """DataSetModel (dataset) -> new Gtk.TreeModel for an ARA dataset."""

    def __init__ (self, filename):
        Gtk.GenericTreeModel.__init__ (self)
        self.astr = aradecode.ara_stream (gzip.GzipFile (filename))
        self.events = list (self.astr)

    # Section: Implementation of Gtk.GenericTreeModel
    def on_get_flags(self):
        return Gtk.TREE_MODEL_LIST_ONLY

    def on_get_n_columns(self):
        return 2

    def on_get_column_type(self, index):
        if index in (0, 1):
            return str
        else:
            raise IndexError

    def on_get_iter(self, path):
        return path[0]

    def on_get_path(self, rowref):
        return (rowref,)

    def on_get_value(self, row, col):
        if 0 <= row < len (self.events):
            ev = self.events[row]
            if col == 0:
                return str (ev.get_unix_datetime ())
            if col == 1:
                return str (ev.event_id)
        else:
            raise IndexError

    def on_iter_next(self, rowref):
        if rowref == len (self.events) - 1:
            return None
        else:
            return rowref + 1

    def on_iter_children(self, parent):
        if rowref:
            return None
        return 0

    def on_iter_has_child(self, rowref):
        return False

    def on_iter_n_children(self, rowref):
        if rowref:
            return 0
        else:
            return len (self.events)

    def on_iter_nth_child(self, parent, n):
        if parent:
            return None
        elif n < len (self.events):
            return n
        else:
            return None

    def on_iter_parent(self, child):
        return None

usage = r"""%prog {[options]} {[data file]} 

This is a relatively straightforward Python-based alternative to AraDisplay.
It is not (yet?) a feature-complete port.

If --data-dir is given, this is the directory the "Open data..." dialog will
start in.

If --pedestals-dir is given, this is the directory the "Open pedestals..."
dialog will start in.  Also, if pedestals are not yet loaded when data is being
loaded, this directory will automatically be searched for the most recent
pedestals file prior to the run in question.  Note that this only works if the
data file matches /run(\d+)/.

"""

class Window (object):

    """PyAraDisplay window."""

    channels = {}
    channels[100] = [0, 1, 2, 3]
    channels[2] = [3, 1, 2, 0]
    channels[3] = [2, 0, 3, 1]
    channel_labels = ['Top Hpol', 'Top Vpol', 'Bottom Hpol', 'Bottom Vpol']

    subplot_args = dict (top=.94, bottom=.05, left=.09, right=.98,
                hspace=0.02, wspace=0.02)

    def __init__ (self, commandline=''):
        
        self.parser = parser = optparse.OptionParser (usage=usage)

        parser.add_option ('-d', '--data-dir', dest='data_dir',
                metavar='DIR', help='by default load data from DIR')

        parser.add_option ('-f', '--first-file', dest='first_file',
                default=False, action='store_true',
                help='search directories under pwd; '
                'load the first found .dat file')

        parser.add_option ('-p', '--pedestals-dir', dest='pedestals_dir',
                metavar='DIR', help='by default load pedestals from DIR')

        parser.add_option ('-P', '--pedestals-file', dest='pedestals_file',
                metavar='FILE', help='load pedestals from FILE')

        parser.add_option ('--plot-dir', dest='plot_dir',
                metavar='DIR', help='by default put plots in DIR')

        argv = commandline.split (' ') if commandline else sys.argv[1:]

        self.opts, self.args = opts, args = parser.parse_args (argv)

        self.cal_dir = opts.pedestals_dir or os.curdir
        self.data_dir = opts.data_dir or os.curdir
        self.plots_dir = opts.plot_dir or os.curdir
        self._clear ()

        if opts.pedestals_file:
            self.load_cal (opts.pedestals_file)

        if self.opts.first_file:
            options = sorted (glob ('ev*.dat')) \
                    + sorted (glob ('*/ev*.dat')) \
                    + sorted (glob ('*/*/ev*.dat')) \
                    + sorted (glob ('*/*/*/ev*.dat'))
            if options:
                self.load_data (options[0])
        elif len (args) == 1:
            self.load_data (args[0])

    def _clear (self):
        self.window = None
        self.title = 'PyAraDisplay'
        self.cal = None
        self.dsm = None
        self.n = -1
        self.menu = Vars ()
        self.el = Vars ()
        self.events = Vars ()
        self.events.ag = None
        self._build_window ()

    def _build_window (self):
        """Assemble the underlying Gtk.Window."""
        # the window
        if self.window is None:
            self.window = Gtk.Window (type=Gtk.WINDOW_TOPLEVEL)
            self.window.connect ('delete_event', self._cb_delete_event)
            self.window.set_size_request (1000, 500)
            self.window.set_position(Gtk.WIN_POS_CENTER)
        else:
            self.window.remove (self.menu_vbox)
        self._set_title (self.title)
        # vbox: menu, then everything else
        self.menu_vbox = Gtk.VBox (homogeneous=False, spacing=2)
        self.window.add (self.menu_vbox)
        self._build_menu ()
        self._build_hpane ()
        # done!
        self.window.show_all ()

    def _build_menu (self):
        """Build the menu for the window, given its current state."""
        self.uim = Gtk.UIManager ()
        self.accel_group = self.uim.get_accel_group ()
        self.window.add_accel_group (self.accel_group)
        self.menu.ag = Gtk.ActionGroup (name='base action group')
        self.menu.ag.add_actions (
            [
            ('File', None, '_File', None, None, None),
            ('Open pedestals', None, 'Open _pedestals', '<control>p', None,
                self._cb_open_cal), 
            ('Open data', None, 'Open _data', '<control>o', None,
                self._cb_open_data), 
            ('Save plots', Gtk.STOCK_SAVE, '_Save plots', '<control>s', None,
                self._cb_save_plots), 
            ('Quit', Gtk.STOCK_QUIT, None, '<control>q', None, self._cb_quit),
            ('View', None, '_View', None, None, None),
            ]
        )
        self.menu.ag.add_toggle_actions (
            [
            ('equally', None, 'Scale _y-axis equally',
                '<control>e', None, self._cb_update_plots, True),
            ('mean', None, 'Subtract _mean of waveform',
                '<control>u', None, self._cb_update_plots, False),
            ('fullscreen', None, '_Fullscreen',
                'F11', None, self._cb_fullscreen, False),
            ]
        )
        def get_action (name):
            return [a for a in self.menu.ag.list_actions ()
                if a.get_name () == name][0]

        self.menu.equally_action = get_action ('equally')
        self.menu.mean_action = get_action ('mean')
        self.menu.fullscreen_action = get_action ('fullscreen')
        self.menu.ui = """
        <ui>
            <menubar name="MenuBar">
                <menu action="File">
                    <menuitem action = "Open pedestals" />
                    <menuitem action = "Open data" />
                    <menuitem action = "Save plots" />
                    <separator />
                    <menuitem action = "Quit" />
                </menu>
                <menu action="View">
                    <menuitem action = "equally" />
                    <menuitem action = "mean" />
                    <separator />
                    <menuitem action = "fullscreen" />
                </menu>
            </menubar>
        </ui>
        """
        self.uim.insert_action_group (self.menu.ag, 0)
        self.uim.add_ui_from_string (self.menu.ui)
        self.menu.bar = self.uim.get_widget ('/MenuBar')
        self.menu_vbox.pack_start (self.menu.bar, False, False, 0)

    def _build_hpane (self):
        """Build the HPane with plots on left, trigger list on right."""
        # hpane: notebook on left, event list on right
        self.main_hpane = Gtk.HPaned ()
        self.main_hpane.pack1 (Gtk.HBox (), resize=True)
        self.main_hpane.pack2 (Gtk.HBox (), resize=True)
        self.menu_vbox.pack_start (self.main_hpane)
        self._setup_event_plots ()
        self._setup_event_list ()

    def _setup_event_plots (self):
        """Set up plots for single events."""
        self.events.plots = [
                'Waveform',
                'FFT (linear-y)',
                'FFT (semilog-y)',
                'Hilbert',
                ]
        if not self.events.ag is None:
            self.uim.remove_action_group (self.events.ag)
            self.uim.remove_ui (self.events.merge_id)
        if self.dsm:
            self.events.vbox = Gtk.VBox (False, 1)
            self.events.vbox.set_size_request (650, 10)
            self.main_hpane.remove (self.main_hpane.get_child1 ())
            self.main_hpane.pack1 (self.events.vbox, resize=True)
            self.events.hbox = Gtk.HBox (False, 4)
            self.events.combo = Gtk.combo_box_new_text ()
            self.events.hbox.pack_start (self.events.combo, expand=True)
            self.events.vbox.pack_start (self.events.hbox, expand=False)
            self.events.ag = Gtk.ActionGroup ('events action group')
            self.events.ag.add_actions ([
                ('wf', None, 'wf', '<control>m', None,
                    self._cb_events_combo_switch) ], 0)
            self.events.ag.add_actions ([
                ('fft_linear', None, 'fft_linear', '<control>f', None,
                    self._cb_events_combo_switch) ], 1)
            self.events.ag.add_actions ([
                ('fft_semilogy', None, 'fft_semilogy', '<control>y', None,
                    self._cb_events_combo_switch) ], 2)
            self.events.ag.add_actions ([
                ('hilbert', None, 'hilbert', '<control>h', None,
                    self._cb_events_combo_switch) ], 3)
            self.events.ui = """
            <ui>
                <accelerator action="wf" />
                <accelerator action="fft_linear" />
                <accelerator action="fft_semilogy" />
                <accelerator action="hilbert" />
            </ui>
            """
            self.uim.insert_action_group (self.events.ag, -1)
            self.events.merge_id = self.uim.add_ui_from_string (
                    self.events.ui)
            self.events.combo.append_text ('Waveform [Ctrl-M]')
            self.events.combo.set_active (0)
            self.events.combo.append_text ('FFT (linear) [Ctrl-F]')
            self.events.combo.append_text ('FFT (semilog-y) [Ctrl-Y]')
            self.events.combo.append_text ('Hilbert [Ctrl-H]')
            self.events.combo.connect ('changed', self._cb_update_plots)
            self.events.figure = mpl.figure.Figure (
                    figsize=(3,3), dpi=50, facecolor='.85')
            self.events.canvas = mplGtk.FigureCanvasGTK (self.events.figure)
            self.events.vbox.pack_start (self.events.canvas)
        self.window.show_all ()

    def _setup_event_list (self):
        if self.dsm:
            self.el.tv = Gtk.TreeView (model=self.dsm)
            self.el.tv.connect ('cursor-changed', self._cb_update_plots)
            self.el.sw = Gtk.ScrolledWindow ()
            self.el.sw.add_with_viewport (self.el.tv)
            self.el.sw.set_size_request (300, 10)
            self.el.frame = Gtk.Frame ('Trigger List')
            self.el.frame.add (self.el.sw)
            cur = self.main_hpane.get_child2 ()
            if cur:
                self.main_hpane.remove (cur)
            vbox = Gtk.VBox (False, 4)
            vbox.pack_start (self.el.frame, expand=True)
            self.main_hpane.pack2 (vbox, resize=True, shrink=False)
            self.el.tv.get_selection ().select_path (0)
            cell = Gtk.CellRendererText ()
            column = Gtk.TreeViewColumn (
                    'unix time', cell, text=0)
            self.el.tv.insert_column (column, 0)
            cell = Gtk.CellRendererText ()
            column = Gtk.TreeViewColumn (
                    'event id', cell, text=1)
            self.el.tv.insert_column (column, 1)
        else:
            self.main_hpane.add2 (Gtk.HBox ())
        self.window.show_all ()

    def main (self):
        Gtk.main ()

    def load_cal (self, filename):
        """Load a pedestals file."""
        self.cal_dir = os.path.dirname (filename)
        with open (filename) as f:
            self.cal = aradecode.ped_cal (f)
        print ('Loaded pedestals from "{0}".'.format (filename))
        if self.dsm:
            self._cb_update_plots (None)

    def load_data (self, filename):
        """Load the data file."""
        self.data_dir = os.path.dirname (filename)
        # try to guess the best pedestals file
        if not self.cal:
            m = re.search (r'run_?(\d+)', filename)
            pedestal_files = np.array (sorted (glob (
                '{0}/pedestal*dat'.format (self.cal_dir))))
            if m and len (pedestal_files):
                run_number = int (m.group (1))
                pedestal_runs = np.array ([
                    int (f[-10:-4]) for f in pedestal_files])
                older_idx = pedestal_runs < run_number
                if older_idx.sum ():
                    pedestal_file = pedestal_files[older_idx][-1]
                else:
                    pedestal_file = pedestal_files[0]
                self.load_cal (pedestal_file)
        if not self.cal:
            dialog = Gtk.MessageDialog (
                    self.window, Gtk.DIALOG_MODAL,
                    Gtk.MESSAGE_WARNING, Gtk.BUTTONS_OK,
                    'Could not find a suitable pedestal file; please specify '
                    'one manually.')
            response = dialog.run ()
            dialog.destroy ()
            return
        self.dsm = DataSetModel (filename)
        print ('Loaded data from "{0}".'.format (filename))
        self._setup_event_list ()
        self._setup_event_plots ()
        self._cb_update_plots (None)


    def _set_title (self, title):
        self.title = title
        self.window.set_title (self.title)
        self.window.show_all ()

    def _get_selected_event_number (self):
        model, path = self.el.tv.get_selection ().get_selected_rows ()
        if path:
            return path[0][0]
        else:
            return 0

    def _plot_event (self, fig):
        """Plot the event."""
        active = self.events.combo.get_active ()
        if active == 0:
            self._plot_event_wf (fig)
        elif active == 1:
            self._plot_event_fft (fig, log=False)
        elif active == 2:
            self._plot_event_fft (fig, log=True)
        elif active == 3:
            self._plot_event_hilbert (fig)

    def _get_ws (self, ev):
        ws = np.array ([[ev.get_waveform (dda, chan, self.cal)
            for dda in xrange (4)]
            for chan in self.channels[ev.station_id]])
        if self.menu.mean_action.get_active ():
            ws = (ws.T - ws.mean (axis=-1).T).T
        return ws

    def _plot_event_wf (self, fig):
        n = self._get_selected_event_number ()
        ev = self.dsm.events[n]
        station = ev.station_id

        fig.clf ()
        ws = self._get_ws (ev)
        y_extrema = np.max (np.max (np.abs (ws), axis=-1), axis=1)
        for chan in xrange (4):
            for dda in xrange (4):
                which = 4 * chan + dda + 1
                ax = fig.add_subplot (4, 4, which)
                w = ws[chan][dda]
                t = np.arange (len (w)) / 3.2  # rough approximation!
                ax.plot (t, w, '-', lw=.5)
                ax.xaxis.set_major_locator (
                        mpl.ticker.MaxNLocator (nbins=4))
                ax.yaxis.set_major_locator (
                        mpl.ticker.MaxNLocator (nbins=6, symmetric=True))
                if chan < 3:
                    ax.set_xticklabels ([])
                if dda > 0:
                    ax.set_yticklabels ([])
                # NOTE: this works because we do not account for cable delays
                ax.set_xlim (0, t.max ())
                if self.menu.equally_action.get_active ():
                    ax.set_ylim (-y_extrema[chan], y_extrema[chan])
                else:
                    ax.set_yticklabels ([])
                    extremum = max (ax.get_ylim ())
                    ax.set_ylim (-extremum, extremum)
                ax.grid (color='.7', zorder=-10)
                if dda == 0:
                    ax.set_ylabel (self.channel_labels[chan])
                if chan == 0:
                    ax.set_title ('DDA {0}'.format (dda + 1))
        fig.subplots_adjust (**self.subplot_args)

    def _plot_event_fft (self, fig, log):
        n = self._get_selected_event_number ()
        ev = self.dsm.events[n]

        fig.clf ()

        def get_fft (w):
            basic_amplitudes = np.fft.rfft (w)
            amplitudes = basic_amplitudes.T[:-1].T
            return amplitudes

        def get_fftfreqs (w):
            t_range = len (w) / 3.2  # ns, rough approximation!
            n = len (w)
            dt = 1e-9 * t_range / n
            frequencies = np.fft.fftfreq (n)[:n/2] / dt # Hz
            return frequencies

        ws = self._get_ws (ev)
        ffts = np.abs (get_fft (ws)).T[1:].T
        fftfreqs = get_fftfreqs (ws[0][0])[1:] / 1e6 # in MHz
        ymax = np.max (np.max (ffts, axis=-1), axis=1)
        ymin = np.min (np.min (ffts, axis=-1), axis=1)
        for chan in xrange (4):
            for dda in xrange (4):
                which = 4 * chan + dda + 1
                ax = fig.add_subplot (4, 4, which)
                plot = ax.semilogy if log else ax.plot
                plot (fftfreqs, ffts[chan][dda], '-', lw=.5)
                ax.xaxis.set_major_locator (
                        mpl.ticker.MaxNLocator (nbins=4))
                ax.yaxis.set_major_locator (
                        mpl.ticker.MaxNLocator (nbins=4))
                if chan < 3:
                    ax.set_xticklabels ([])
                if dda > 0:
                    ax.set_yticklabels ([])
                ax.set_xlim (0, 1000)
                the_ymin = ymin[chan] if log else 0
                if self.menu.equally_action.get_active ():
                    ax.set_ylim (the_ymin, 1.05 * ymax[chan])
                else:
                    ax.set_ylim (the_ymin, 1.05 * ffts[chan][dda].max ())
                    ax.set_yticklabels ([])
                ax.grid (color='.7', zorder=-10)
                if dda == 0:
                    ax.set_ylabel (self.channel_labels[chan])
                if chan == 0:
                    ax.set_title ('DDA {0}'.format (dda + 1))
        fig.subplots_adjust (**self.subplot_args)

    def _plot_event_fft_semilogy (self, fig):
        self._plot_event_fft (fig)
        n = self._get_selected_event_number ()
        ev = self.dsm.events[n]
        channels = self.channels[ev.station_id]
        channel_positions = self.channel_positions[ev.station_id]
        for chan in xrange (4):
            for dda in xrange (4):
                which = 4 * chan + dda + 1
                ax = fig.add_subplot (4, 4, which)
                ax.set_ylim (ymin=1)
                ax.set_yscale ('log')
                if chan < 3:
                    ax.set_xticklabels ([])
                if dda > 0:
                    ax.set_yticklabels ([])

    def _plot_event_hilbert (self, fig):
        n = self._get_selected_event_number ()
        ev = self.dsm.events[n]

        fig.clf ()

        ws = self._get_ws (ev)
        hilberts = np.abs (scipy.signal.hilbert (ws))
        y_extrema = np.max (np.max (hilberts.T[1:].T, axis=-1), axis=1)
        t = np.arange (len (hilberts[0,0])) / 3.2  # rough approximation!
        for chan in xrange (4):
            for dda in xrange (4):
                which = 4 * chan + dda + 1
                ax = fig.add_subplot (4, 4, which)
                ax.plot (t, hilberts[chan][dda], '-', lw=.5)
                ax.xaxis.set_major_locator (
                        mpl.ticker.MaxNLocator (nbins=4))
                ax.yaxis.set_major_locator (
                        mpl.ticker.MaxNLocator (nbins=4))
                if chan < 3:
                    ax.set_xticklabels ([])
                if dda > 0:
                    ax.set_yticklabels ([])
                ax.set_xlim (0, t.max ())
                if self.menu.equally_action.get_active ():
                    ax.set_ylim (0, y_extrema[chan])
                else:
                    ax.set_yticklabels ([])
                ax.grid (color='.7', zorder=-10)
                if dda == 0:
                    ax.set_ylabel (self.channel_labels[chan])
                if chan == 0:
                    ax.set_title ('DDA {0}'.format (dda + 1))
        fig.subplots_adjust (**self.subplot_args)
        

    def _cb_delete_event (self, widget, event, *args):
        """Handle the X11 delete event."""
        self._cb_quit (widget)
        return False

    def _cb_fullscreen (self, whence, *args):
        if self.menu.fullscreen_action.get_active ():
            self.window.fullscreen ()
        else:
            self.window.unfullscreen ()

    def _cb_events_combo_switch (self, whence, data, *args):
        self.events.combo.set_active (data)
        self._cb_update_plots (self.events.combo)

    def _cb_open_cal (self, whence, *args):
        """Handle the 'Open calibration' action."""
        dialog = Gtk.FileChooserDialog ('Open calibration...',
                None, Gtk.FILE_CHOOSER_ACTION_OPEN,
                (Gtk.STOCK_CANCEL, Gtk.RESPONSE_CANCEL,
                 Gtk.STOCK_OPEN, Gtk.RESPONSE_OK))
        dialog.set_current_folder (self.cal_dir)
        dialog.set_default_response (Gtk.RESPONSE_OK)
        filt = Gtk.FileFilter ()
        filt.set_name ('ARA calibration dat files')
        filt.add_pattern ('*.dat')
        dialog.add_filter (filt)
        filt = Gtk.FileFilter ()
        filt.set_name ('All Files')
        filt.add_pattern ('*')
        dialog.add_filter (filt)
        response = dialog.run ()
        if response == Gtk.RESPONSE_OK:
            filename = dialog.get_filename ()
        else:
            filename = None
        dialog.destroy ()
        if filename:
            self.load_cal (filename)

    def _cb_open_data (self, whence, *args):
        """Handle the 'Open data' action."""
        dialog = Gtk.FileChooserDialog (title='Open...',
                parent=None, action=Gtk.FILE_CHOOSER_ACTION_OPEN,
                buttons=(Gtk.STOCK_CANCEL, Gtk.RESPONSE_CANCEL,
                 Gtk.STOCK_OPEN, Gtk.RESPONSE_OK))
        dialog.set_current_folder (self.data_dir)
        dialog.set_default_response (Gtk.RESPONSE_OK)
        filt = Gtk.FileFilter ()
        filt.set_name ('ARA dat files')
        filt.add_pattern ('*.dat')
        dialog.add_filter (filt)
        filt = Gtk.FileFilter ()
        filt.set_name ('All Files')
        filt.add_pattern ('*')
        dialog.add_filter (filt)
        response = dialog.run ()
        if response == Gtk.RESPONSE_OK:
            filename = dialog.get_filename ()
        else:
            filename = None
        dialog.destroy ()
        if filename:
            self.load_data (filename)

    def _cb_save_plots (self, whence, *args):
        """Handle the Save plots action."""
        dialog = Gtk.FileChooserDialog ('Save plots...',
                None, Gtk.FILE_CHOOSER_ACTION_SAVE,
                (Gtk.STOCK_CANCEL, Gtk.RESPONSE_CANCEL,
                 Gtk.STOCK_SAVE, Gtk.RESPONSE_OK))
        dialog.set_current_folder (self.plots_dir)
        dialog.set_default_response (Gtk.RESPONSE_OK)
        filt = Gtk.FileFilter ()
        filt.set_name ('PDF files')
        filt.add_pattern ('*.pdf')
        dialog.add_filter (filt)
        filt = Gtk.FileFilter ()
        filt.set_name ('Portable Network Graphics (PNG) files')
        filt.add_pattern ('*.png')
        dialog.add_filter (filt)
        filt = Gtk.FileFilter ()
        filt.set_name ('Encapsulated PostScript (EPS) files')
        filt.add_pattern ('*.eps')
        dialog.add_filter (filt)
        filt = Gtk.FileFilter ()
        filt = Gtk.FileFilter ()
        filt.set_name ('All Files')
        filt.add_pattern ('*')
        dialog.add_filter (filt)
        response = dialog.run ()
        if response == Gtk.RESPONSE_OK:
            filename = dialog.get_filename ()
        else:
            filename = None
        if filename:
            self.plots_dir = dialog.get_current_folder ()
            fig = plt.figure (figsize=(11,9))
            self._plot_event (fig)
            fig.savefig (filename)
            plt.close (fig)
        dialog.destroy ()

    def _cb_update_plots (self, widget, *args):
        """Update whatever plots need updating."""
        self.events.vbox.remove (self.events.canvas)
        self.events.figure = mpl.figure.Figure (
                figsize=(3,3), dpi=50, facecolor='.85')
        self._plot_event (self.events.figure)
        self.events.canvas = mplGtk.FigureCanvasGTK (self.events.figure)
        self.events.vbox.pack_start (self.events.canvas)
        self.events.canvas.draw ()
        self.window.show_all ()

    def _cb_quit (self, whence, *args):
        Gtk.main_quit ()


if __name__ == '__main__':
    window = Window ()
    window.main ()
