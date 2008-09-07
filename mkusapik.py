""" One-off script to make USA_dict.pik with a pickled dict for USA_1.zip.
"""
from __future__ import with_statement
import cPickle
import logging
import zipfile

def setlogging(dodebug=False):
  logging.basicConfig(format='%(levelname)s: %(message)s')
  logger = logging.getLogger()
  logger.setLevel(logging.DEBUG if dodebug else logging.INFO)
  return logger

def main():
  setlogging(dodebug=True)

  zif = zipfile.ZipFile('USA_1.zip', 'r')
  start = len('tile_USA_')
  result = dict()
  for fn in zif.namelist():
    result[fn[start:-4]] = 1
  with open('USA_dict.pik', 'wb') as f:
    cPickle.dump(result, f)

main()

