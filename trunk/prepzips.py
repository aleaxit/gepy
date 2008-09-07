""" Prepare ZIP files with tiles, and an indexfile z/x/y -> zipfile.

Expects to find in /tmp files named tile_<theme>_z_x_y.png where:
  - <theme> is an all-uppercase "theme name" string
  - z, x, y are integers (zoom level and x/y Google tile coordinates)
Writes, also in /tmp:
  - zipfiles named <theme>_<N>.zip for increasing integers N, each zip <1MB
  - a pickled dict with string z_x_y as key and N as value (when
    tile_<theme>_z_x_y is in zipfile <theme>_N.zip) named <theme>_dict.pik
Principles of operation:
  - build zipfiles sequentially (sorting filenames numerically theme-z-x-y)
  - keep track of the total (compressed) size of the current zipfile
  - ensure <1MB by checking that the next tile-file would fit UNcompressed (!),
    else close the current zipfile and open a fresh one for the next tile +
"""
from __future__ import with_statement
import cPickle
import glob
import logging
import os
import sys
import zipfile

# use a prudent size as we also need space for the zipfile directory &c
MAX_SIZE = 1000*1000 - 50*1000

def setlogging(dodebug=False):
  """ Set logging config and level (to INFO, default, or DEBUG). """
  logging.basicConfig(format='%(levelname)s: %(message)s')
  logger = logging.getLogger()
  logger.setLevel(logging.DEBUG if dodebug else logging.INFO)
  return logger


def namekey(filename):
  """ Return key (theme, z, x, y) for a filename 'tile_theme_z_x_y.png'.

  Args:
    filename: str like 'tile_FOOBAR_1_2_3.png'
  Returns:
    4-item tuple: str like FOOBAR, then ints like 1, 2, 3
  """
  try: tile, theme, z, x, y = filename[:-4].split('_')
  except ValueError, e:
    print "Can't unpack %r: %s" % (filename, e)
    sys.exit(1)
  assert tile=='tile'
  return theme, int(z), int(x), int(y)


def main(working_directory='/tmp'):
  """ Prepare zipfiles and .pik dictionary index from .png tile files. """
  setlogging(dodebug=True)

  # get all filenames, properly sorted, and the theme
  os.chdir(working_directory)
  filenames = sorted(glob.iglob('tile_*.png'), key=namekey)
  theme = namekey(filenames[0])[0]
  # check that all filenames are for the same theme
  lastheme = namekey(filenames[-1])[0]
  assert theme == lastheme
  # precompute and initialize as needed
  zxy_start = len('tile_%s_' % theme)
  dbname = '%s_dict.pik' % theme
  logging.info('Processing %d files, creating index %r', len(filenames), dbname)
  zipnum = 0
  fns = iter(filenames)
  fn = fns.next()
  index_dict = dict()
  # main loop: open, fill and close one more zipfile
  while True:
    # loop invariants: all zipfiles from 1 to zipnum are done and closed;
    # fn names a PNG file that must be the first in this next zipfile
    zipnum += 1
    zipfna = '%s_%s.zip' % (theme, zipnum)
    logging.debug('Creating zipfile %r', zipfna)
    num_tiles_in_zip = 0
    zipfil = zipfile.ZipFile(zipfna, 'w', zipfile.ZIP_DEFLATED)
    zipsiz = 0
    # inner loop: add fn to current zipfile, get next fn, break if too big
    while True:
      zipfil.write(fn)
      num_tiles_in_zip += 1
      z_x_y = fn[zxy_start:-4]
      index_dict[z_x_y] = zipnum
      zipinfo = zipfil.getinfo(fn)
      zipsiz += zipinfo.compress_size
      try: fn = fns.next()
      except StopIteration:
        # done all tile files, set fn to None to mark end of main loop
        fn = None
        break
      filsiz = os.stat(fn).st_size
      if filsiz > MAX_SIZE:
        logging.error("Can never pack %r, size %s: terminating!", fn, filsiz)
        fn = None
      if zipsiz + filsiz > MAX_SIZE:
        break
    zipfil.close()
    logging.debug('%d tiles in zip, next tile %s', num_tiles_in_zip, fn)
    if fn is None:
      break
  with open(dbname, 'w') as f:
    cPickle.dump(index_dict, f)

main()

