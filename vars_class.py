# vars.py

"""Provide the Vars class.

Vars is like dict, but with . style access in addition to [] style access.

"""


import numpy as np


class Vars (object):

    """Store objects as in a dict, but also with object.key style access.

    The Vars class is a mapping similar to dict, but it allows both
    object[key] and object.key style access.

    Note: keys must not start with '_'.
    """

    def __init__ (self, initializer={}):
        self._variables = []
        self._dict = {}
        for k in initializer.keys ():
            self[k] = initializer[k]

    def __repr__ (self):
        return ('{0} object at 0x{1:x} with members {2}'.format (
            type (self), id (self), self._variables))

    def __getstate__ (self):
        return self._dict

    def __setstate__ (self, d):
        self._variables = []
        self._dict = {}
        if '_variables' in d:
            self._variables = d['_variables']
        if '_dict' in d:
            self._variables = d['_dict']
        for k in d:
            setattr (self, k, d[k])
            #self[k] = d[k]

    def __setattr__ (self, name, value):
        if name[0] != '_':
            self._set (name, value)
        else:
            object.__setattr__ (self, name, value)

    def __setitem__ (self, name, value):
        self._set (name, value)

    def __contains__ (self, name):
        return name in self._variables

    def __getitem__ (self, name):
        return self._dict[name]

    def __iter__ (self):
        """Returns an iterator to keys tuples."""
        for key in sorted (self._dict):
            yield key

    def _set (self, name, value):
        """Set self.name = value."""
        if not name in self._variables:
            self._variables.append (name)
            self._variables.sort ()
        object.__setattr__ (self, name, value)
        self._dict[name] = value

    def _unset (self, name):
        """Unset self.name."""
        if name in self._variables:
            self._variables.remove (name)
            del self._dict[name]
            self.__delattr__ (name)

    def _rename (self, oldname, newname):
        """Change self.oldname to self.newname."""
        val = self[oldname]
        self._unset (oldname)
        self._set (newname, val)


