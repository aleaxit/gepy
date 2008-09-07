""" Prepare ZIP files with tiles, and a text indexfile z/x/y -> zipfile.

Expects to find in /tmp files named tile_<theme>_z_x_y.png where:
  - <theme> is an all-uppercase "theme name" string
  - z, x, y are integers (zoom level and x/y Google tile coordinates)
Writes, also in /tmp:
  - zipfiles named <theme>_<N>.zip for increasing integers N, each zip <1MB
  - a sqlite DB named <theme>_tiles.sdb with one table TILE_TO_ZIP with
    string z_x_y as key and N as value (when tile_<theme>_z_x_y is in
    zipfile <theme>_N.zip)
Principles of operation:
  - build zipfiles sequentially (sorting filenames numerically theme-z-x-y)
  - keep track of the total (compressed) size of the current zipfile
  - ensure <1MB by checking that the next tile-file would fit UNcompressed (!),
    else close the current zipfile and open a fresh one for the next tile +
"""
import glob
import logging
import os
import sqlite3
import sys
import zipfile

# use a prudent size as we also need space for the zipfile directory &c
MAX_SIZE = 1000*1000 - 50*1000

def setlogging(dodebug=False):
  logging.basicConfig(format='%(levelname)s: %(message)s')
  logger = logging.getLogger()
  logger.setLevel(logging.DEBUG if dodebug else logging.INFO)
  return logger

def namekey(filename):
  try: tile, theme, z, x, y = filename[:-4].split('_')
  except ValueError, e:
    print "Can't unpack %r: %s" % (filename, e)
    sys.exit(1)
  assert tile=='tile'
  return theme, int(z), int(x), int(y)

def main(working_directory='/tmp'):
  setlogging(dodebug=True)

  os.chdir(working_directory)
  filenames = sorted(glob.iglob('tile_*.png'), key=namekey)
  theme, z, x, y = namekey(filenames[0])
  zxy_start = len('tile_%s_' % theme)
  dbname = '%s_tiles.sdb' % theme
  logging.info('Processing %d files, creating DB %r', len(filenames), dbname)
  conn = sqlite3.connect(dbname)
  conn.isolation_level = None
  conn.execute("""CREATE TABLE IF NOT EXISTS tile_to_zip
                  (z_x_y STRING PRIMARY KEY, n INTEGER)
               """)
  zipnum = 0
  fns = iter(filenames)
  fn = fns.next()
  while True:
    zipnum += 1
    zipfna = '%s_%s.zip' % (theme, zipnum)
    logging.debug('Creating zipfile %r', zipfna)
    num_tiles_in_zip = 0
    zipfil = zipfile.ZipFile(zipfna, 'w', zipfile.ZIP_DEFLATED)
    zipsiz = 0
    while True:
      zipfil.write(fn)
      num_tiles_in_zip += 1
      z_x_y = fn[zxy_start:-4]
      conn.execute("INSERT INTO tile_to_zip VALUES(?,?)", (z_x_y, zipnum))
      zipinfo = zipfil.getinfo(fn)
      zipsiz += zipinfo.compress_size
      try: fn = fns.next()
      except StopIteration:
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
  conn.close()

main()

