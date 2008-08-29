#!/usr/bin/python

from __future__ import with_statement

""" Process an ARC Shapefile to extract polygons / polylines of interest.

Copyright (C) 2008 Alex Martelli, aleaxit@gmail.com
Licensed under Apache License 2.0, http://www.apache.org/licenses/LICENSE-2.0

Inspired by Zachary Forest Johnson's shpUtils.py file, found at:
http://indiemaps.com/blog/2008/03/easy-shapefile-loading-in-python/ .  See
http://en.wikipedia.org/wiki/Shapefile for more information about the Shapefile
format.

This module is, by default, somewhat-specialized to process the freely available
US Census' TIGER/Line shapefiles for 5-digit ZTCAs in the US; see
http://www.census.gov/geo/www/tiger/ for more information about TIGER/Line
files.  The specialization (besides focusing only on shapefiles that hold
polygons or polylines) lies in the choice of unique-identifier attribute for
each record: in this module, the attribute used as the unique identifier is the
one named ZCTA5CE00, and the module only examines records where that identifier
is made of all digits ("real" zipcodes as opposed to "synthetic" ones for water
areas and land wilderness).

This specialization can be countered (allowing the reading of any shapefile of
polygons or polylines) by instantiating the Shp class with other explicit
values of optional parameters id_field_name (str, default 'ZTCA5CE00') and/or
id_field_check (callable, must return a false value for unacceptable IDs).

The module assumes all bounding boxes are 4 doubles in order: xmin, ymin, xmax,
ymax; AKA, 2 points in order WS, EN (longitude then latitude, longlat, the
natural format for Shapefiles); the module provides a utility function to
make a bbox in that SHP-oriented format given the format that's more natural in
KML &c, which is (latlong) SW, NE, and an optional magnification around the box center.
"""
import array
import itertools
import math
import struct
import dbfUtils


# determine the endianness of the machine we're running on
big_endian = struct.unpack('>i', struct.pack('=i', 23)) == (23,)
# print 'Machine is', ('little', 'big')[big_endian], 'endian'


def dobox(sw, ne, magnify=1.0):
  """ Get xmin/ymin/xmax/ymax bounding box for given SW/NE + magnify-factor.

  Args:
    sw: tuple of 2 floats, (ymax, xmax) [the "SW" LatLong point]
    ne: tuple of 2 floats, (ymin, xmin) [the "NE" LatLong point]
    magnify: optional, float to enlarge the bbox by (default 1.0)
  Returns:
    tuple of 4 floats, xmin, ymin, xmax, ymax (aka W, S, E, N)
  """
  # compute and check half-height and half-width of given bbox
  h2 = (sw[0] - ne[0]) / 2
  w2 = (sw[1] - ne[1]) / 2
  assert h>0 and w>0 and magnify>0
  # compute center of bbox
  c0 = ne[0] + h2
  c1 = ne[1] + w2
  # use magnified half-dimensions to compute corners from center
  h2 *= magnify
  w2 *= magnify
  xmin = c1 - w2
  xmax = c1 + w2
  ymin = c0 - h2
  ymax = c0 + h2
  return xmin, ymin, xmax, ymax


def showbb(dbls):
  """ Format some floats to a string with small display precision.

  Args:
    dbls: a sequence of numbers
  Returns:
    a space-separated string with the numbers formatted as %9.4s
  """
  return ' '.join('%9.4f'%d for d in dbls)


def read_and_unpack(fp, fmt):
  """ Read bytes from file and unpack according to given format.

  Args:
    fp: file-like object (should be open for binary reading)
    fmt: format string for struct.unpack
  Returns:
    tuple of results according to fmt
  """
  n = struct.calcsize(fmt)
  return struct.unpack(fmt, fp.read(n))


def read_some(fp, typecode, n):
  """ Read bytes from file and unpack *as little-endian* w/given typecode.

  Args:
    fp: file-like object (should be open for binary reading)
    typecode: string of length 1, an array.array typecode
    n: number of items (not bytes!) to read
  Returns:
    array.array of given typecode and a length of n items.
  """
  data = array.array(typecode)
  data.fromfile(fp, n)
  if big_endian: data.byteswap()
  return data

def read_doubles(fp, nd): return read_some(fp, 'd', nd)
def read_ints(fp, ni): return read_some(fp, 'i', ni)
def read_one(fp, typecode): return read_some(fp, typecode, 1)[0]


class Shp(object):

  def get_id(self, record_number):
    """ Get and check the ID attribute for record of a given number (1 and up)

    Args:
      record number: int >=1, the record number
    Returns:
      False if record_number is higher than the number of records in the file
      None if the given record's ID does not satisfy the check
      otherwise, str with the ID attribute for the record
    """
    try: id = self._db[record_number-1][self._id_field]
    except IndexError: return False
    if not self._id_check(id): return None
    return id

  def all_out(self, bb):
    """ Check if a bounding box is entirely outside the select-bbox (if any)

    Args:
      bb: bounding box to check (xmin, ymin, xmax, ymax)
    Returns:
      True ifd self has a select-bbox and bb lies entirely outside of it
    """
    cb = self.select_bbox
    if cb is None: return False
    return bb[0] > cb[2] or bb[2] < cb[0] or bb[1] > cb[3] or bb[3] < cb[1]

  def __init__(self, filename, select_bbox=None,
      id_field_name='ZTCA5CE00', id_check=str.isdigit):
    """ Collect relevant info from .SHP, .DBF and .SHX files in the shapefile.

    Keeps the .SHP file open, but the info from the .DBF (and .SHX, if present)
    is kept in memory instead.

    Args:
      filename: path to the .shp file, including the extension
                .dbf (and .shx if any) must have the same dir & basename
      select_bbox: if not None, only records interescting this box matter
      id_field_name: the name of the DBF attribute which identifies records
      id_check: callable with one arg (an id) returning true for "good" ids
    Raises:
      IOError (propagated) for missing .shp or .dbf files
      ValueError if the shape type is anything but 3 or 5 (poly lines/gons), or
                 if the DBF has no attribute with the name given for the ID
      StopIteration if the shapefile's bbox doesn't interest the select one, or
                    if no record has a "good" id
    """
    # get basic shapefile configuration
    fp = self._fp = open(filename, 'rb')
    fp.seek(32)
    shp_type = read_one(fp, 'i')
    if shp_type not in (3, 5):
      msg = 'SHP file %r shapetype %r, not 3 or 5' % (filename, shp_type)
      raise ValueError, msg
    self.overall_bbox = read_doubles(fp, 4)
    self.select_bbox = select_bbox
    if self.all_out(self.overall_bbox):
      msg = 'SHP file %r bbox %s out of select bbox %s' % (filename,
          showbb(self.overall_bbox), showbb(select_bbox))
      raise StopIteration, msg
    # position at first record
    self.rewind()

    # open dbf file and get records as a list
    dbf_file = filename[:-4] + '.dbf'
    with open(dbf_file, 'rb') as dbf:
      dbr = dbfUtils.dbfreader(dbf)
      field_names = dbr.next()
      field_specs = dbr.next()
      self._db = list(dbr)
    # identify index unique-ID field
    for i, field_name in enumerate(field_names):
      if field_name == id_field_name: break
    else:
      msg = 'DBF file %r has no field named %r' % (dbf_file, id_field_name)
      raise ValueError, msg
    self._id_field = i
    self._id_check = id_check

    # try building an ID -> byte offset mapping if the .SHX file is present
    shx_file = filename[:-4] + '.shx'
    try:
      f = open(shx_file, 'rb')
    except IOError:
      # survive missing .SHX file (no indexing in this case, though)
      self._by_id = None
      self._by_recno = None
      self._len = sum(1 for x in self._db if self._id_check(x))
    else:
      self._by_id = {}
      self._by_recno = {}
      with contextlib.closing(f):
        f.seek(100)
        shx_offsets_and_lengths = read_ints(f, 2*len(self._db))
        for id, offs in zip(self._db, shx_offsets_and_lengths[0::2]):
          if not self._id_check(id): continue
          self._by_id[id] = self._by_recno[recno] = 2*offs
        self._len = len(self._by_id)
    if not self._len:
      raise StopIteration, "No record ID passes the id-check function"

  def __length__(self):
    """ Returns the number of records with valid IDs. """
    return self._len

  def __iter__(self):
    """ This class is its own iterator.
    """
    return self

  def _seek_to(self, offs):
    """ Seek the SHP file to an offset and reset the last-read variables.
    """
    self._fp.seek(offs)
    self._last_read_id = None
    self._last_read_recno = None

  def rewind(self):
    """ Re-start reading the shapefile from the first record.
    """
    self._seek_to(100)

  def _set_next(self, key, keyname, check, offs_dict):
    """ Utility method for set_next_... methods """
    if not check(key):
      raise ValueError, 'Invalid %s: %r' % (keyname, key)
    elif offs_dict is None:
      raise AttributeError, 'SHX was not present, SHP not indexable'
    try: self._seek_to(offs_dict[id])
    except KeyError: raise KeyError, '%s %r not in index' % (keyname, key)

  def set_next_id(self, id):
    """ Seek the SHP file to just before a record with the given ID.

    Args:
      id: the id we're looking for
    Raises:
      ValueError if id doesn't pass the good-id test
      AttributeError if the SHX file was not present (SHP not indexable)
      KeyError if there is no record with the requested id
    """
    self._set_next(id, 'ID', self._id_check, self._by_id)

  def set_next_recno(self, recno):
    """ Seek the SHP file to just before a record with the given record #.

    Args:
      recno: the SHP record number (1 and up)
    Raises:
      ValueError if recno < 1
      AttributeError if the SHX file was not present (SHP not indexable)
      KeyError if there is no record with the requested record number
        (record number too high, or record w/that number has bad id)
    """
    self._set_next(recno, 'Record Number', (1).__gt__, self._by_recno)

  @property
  def last_read_id(self):
    """ Read-only property: the ID of the last record read or None
    """
    return self._last_read_id

  @property
  def last_read_recno(self):
    """ Read-only property: the record number of the last record read or None
    """
    return self._last_read_recno

  def close(self):
    """ Close the shapefile. """
    self._fp.close()

  def get_next_record(self, id=1, recno=0, bbox=0, data=1):
    """ Get the next record (if any) with good ID and bounding-box.

    Returns a list with any or all of id, recno, bbox, and data, as requested.
    If no succeeding record is acceptable, returns None

    Args:
      id: bool (default True), should result include the record ID?
      recno: bool (default False), should result include the record number?
      bbox: bool (default False), should result include the record bbox?
      data: book (default True), should result include the record data?
    Returns:
      None if no succeeding record is acceptable, else a list with all
        the requested info; data, if requested, is given as 1+ array.array's
        of doubles, in long/lat/long/lat/... order.
    """
    while True:
      try: the_recno, reclen_words = read_and_unpack(self._fp, '>L>L')
      except struct.error: return None
      endrec = self._fp.tell() + 2*reclen_words
      the_id = self.get_id(the_recno)
      if the_id is None:
        self._fp.seek(endrec)
        continue
      elif the_id is False:
        msg = 'Internal error at rec %r: no id?' % the_recno
        raise SyntaxError, msg
      the_bbox = read_doubles(self._fp, 4)
      if self.all_out(the_bbox):
        self._fp.seek(endrec)
        continue
      # record OK, prepare and return result
      result = []
      if id: result.append(the_id)
      if recno: result.append(the_recno)
      if bbox: result.append(the_bbox)
      if not data:
        self._fp.seek(endrec)
        return result
      # data needed, let's get it
      # TODO: finish from here


def readRecordPolyLine(fp, nexter):
  data = readBoundingBox(fp)
  if not intersect(data):
    fp.seek(nexter)
    return None
  data['numparts']  = readAndUnpack('i', fp.read(4))
  data['numpoints'] = readAndUnpack('i', fp.read(4))
  data['parts'] = []
  for i in range(0, data['numparts']):
    data['parts'].append(readAndUnpack('i', fp.read(4)))
  points_initial_index = fp.tell()
  points_read = 0
  for part_index in range(0, data['numparts']):
    point_index = data['parts'][part_index]

    # if(!isset(data['parts'][part_index]['points']) or !is_array(data['parts'][part_index]['points'])):
    data['parts'][part_index] = {}
    data['parts'][part_index]['points'] = []

    # while( ! in_array( points_read, data['parts']) and points_read < data['numpoints'] and !feof(fp)):
    checkPoint = []
    while (points_read < data['numpoints']):
      currPoint = readRecordPoint(fp)
      data['parts'][part_index]['points'].append(currPoint)
      points_read += 1
      if points_read == 0 or checkPoint == []:
        checkPoint = currPoint
      elif currPoint == checkPoint:
        checkPoint = []
        break

  fp.seek(points_initial_index + (points_read * XY_POINT_RECORD_LENGTH))
  return data

