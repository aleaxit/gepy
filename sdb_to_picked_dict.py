""" Oops -- no sqlite on GAE, so convert the .sdb to a pickled dict!
This module reads (from the current working directory):
  - a sqlite DB named <theme>_tiles.sdb with one table TILE_TO_ZIP with
    string z_x_y as key and N as value (when tile_<theme>_z_x_y is in
    zipfile <theme>_N.zip)
..and writes (to the same cwd):
  - a file <theme>_dict.pik with a pickled dict with z_x_y as key, N as value.
"""
from __future__ import with_statement
import cPickle
import glob
import logging
import sqlite3

def setlogging(dodebug=False):
  logging.basicConfig(format='%(levelname)s: %(message)s')
  logger = logging.getLogger()
  logger.setLevel(logging.DEBUG if dodebug else logging.INFO)
  return logger

def main():
  setlogging(dodebug=True)

  filenames = sorted(glob.iglob('*_tiles.sdb'))
  for fn in filenames:
    sdb_to_picked_dict(fn)

def sdb_to_picked_dict(fn):
  theme, _ = fn.split('_')
  oufn = '%s_dict.pik' % theme
  logging.info("Reading %r, writing %r", fn, oufn)
  conn = sqlite3.connect(fn)
  conn.isolation_level = None
  c = conn.execute("""SELECT * FROM tile_to_zip""")
  allem = c.fetchall()
  logging.info("Processing %d records", len(allem))
  conn.close()
  result = dict(allem)
  with open(oufn, 'wb') as f:
    cPickle.dump(result, f)


main()

