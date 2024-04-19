# PyAraDisplay

A Python raw ARA data display tool. Displays antenna waveforms given a station event `.dat`
file and pedestal `.dat` files.

## Requirements

- Python3 (tested with 3.12)
- matplotlib, numpy, scipy
- GTK3+

On a Mac laptop, GTK3+ is most easily installed with Homebrew, using

```
brew install pygobject3 gtk+3
```

If a recent version of Python3 is not installed already, you may also need to
```
brew install python@3.12
```
and possibly
```
brew link --overwrite python@3.12
```

## Usage

```
Usage: pyaradisplay.py {[options]} {[data file]}

This is a relatively straightforward Python-based alternative to AraDisplay.
It is not (yet?) a feature-complete port.

If --data-dir is given, this is the directory the "Open data..." dialog will
start in.

If --pedestals-dir is given, this is the directory the "Open pedestals..."
dialog will start in.  Also, if pedestals are not yet loaded when data is being
loaded, this directory will automatically be searched for the most recent
pedestals file prior to the run in question.  Note that this only works if the
data file matches /run(\d+)/.



Options:
  -h, --help            show this help message and exit
  -d DIR, --data-dir=DIR
                        by default load data from DIR
  -f, --first-file      search directories under pwd; load the first found
                        .dat file
  -p DIR, --pedestals-dir=DIR
                        by default load pedestals from DIR
  -P FILE, --pedestals-file=FILE
                        load pedestals from FILE
  --plot-dir=DIR        by default put plots in DIR
  ```
