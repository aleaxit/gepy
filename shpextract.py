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
import contextlib
import doctest
import struct
import sys
import dbfUtils


# determine the endianness of the machine we're running on
big_endian = struct.unpack('>i', struct.pack('=i', 23)) == (23,)
# print 'Machine is', ('little', 'big')[big_endian], 'endian'


def dobox(sw, ne, magnify=1.0):
  """ Get xmin/ymin/xmax/ymax bounding box for given SW/NE + magnify-factor.

  >>> dobox((6,8), (2,4), 1)
  (4, 2, 8, 6)
  >>> dobox((16,18), (12,14), 3)
  (10, 8, 22, 20)
  >>> dobox((1, 2), (3, 4), 5)
  Traceback (most recent call last):
     ...
  AssertionError
  >>>

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
  assert h2>0 and w2>0 and magnify>0
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

  >>> showbb([])
  ''
  >>> showbb(range(3))
  '   0.0000    1.0000    2.0000'
  >>>

  Args:
    dbls: a sequence of numbers
  Returns:
    a space-separated string with the numbers formatted as %9.4s
  """
  return ' '.join('%9.4f'%d for d in dbls)


def read_and_unpack(fp, fmt):
  """ Read bytes from file and unpack according to given format.

  >>> import StringIO
  >>> s = StringIO.StringIO()
  >>> s.write(struct.pack('<I', 23))
  >>> s.seek(0)
  >>> read_and_unpack(s, '<I')
  (23,)
  >>>

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

  >>> import tempfile
  >>> f = tempfile.TemporaryFile()
  >>> f.write(struct.pack('<III', 23, 45, 67))
  >>> f.seek(0)
  >>> list(read_some(f, 'i', 3))
  [23, 45, 67]
  >>>

  Args:
    fp: actual file object (should be open for binary reading)
    typecode: string of length 1, an array.array typecode
    n: number of items (not bytes!) to read
  Returns:
    array.array of given typecode and a length of n items.
  """
  data = array.array(typecode)
  data.fromfile(fp, n)
  if big_endian: data.byteswap()
  return data

def read_doubles(fp, nd):
  """ Read bytes from fil and unpack as little-endian doubles.

  >>> import tempfile
  >>> f = tempfile.TemporaryFile()
  >>> f.write(struct.pack('<ddd', 2.3, 4.5, 6.7))
  >>> f.seek(0)
  >>> xs = read_doubles(f, 3)
  >>> ['%3.1f'%x for x in xs]
  ['2.3', '4.5', '6.7']
  >>>

  Args:
    fp: actual file object (should be open for binary reading)
    n: number of doubles to read
  Returns:
    array.array of doubles with a length of n items.
  """
  return read_some(fp, 'd', nd)

def read_ints(fp, ni):
  """ Read bytes from fil and unpack as little-endian ints.

  >>> import tempfile
  >>> f = tempfile.TemporaryFile()
  >>> f.write(struct.pack('<iii', 23, 45, 67))
  >>> f.seek(0)
  >>> list(read_ints(f, 3))
  [23, 45, 67]
  >>>

  Args:
    fp: actual file object (should be open for binary reading)
    n: number of ints to read
  Returns:
    array.array of ints with a length of n items.
  """
  return read_some(fp, 'i', ni)

def read_one(fp, typecode):
  """ Read bytes from file and unpack *as little-endian* w/given typecode.

  >>> import tempfile
  >>> f = tempfile.TemporaryFile()
  >>> f.write(struct.pack('<I', 234567))
  >>> f.seek(0)
  >>> read_one(f, 'i')
  234567
  >>>

  Args:
    fp: actual file object (should be open for binary reading)
    typecode: string of length 1, an array.array typecode
  Returns:
    a single scalar of the specified type
  """
  return read_some(fp, typecode, 1)[0]


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
    try: id = self._db[record_number-1]
    except IndexError: return False
    if not self._id_check(id): return None
    return id

  def all_out(self, bb, cb=None):
    """ Check if a bounding box is entirely outside the select-bbox (if any)

    Args:
      bb: bounding box to check (xmin, ymin, xmax, ymax)
      cb: the select box (None, default, means to use self._select_bbox)
    Returns:
      True ifd self has a select-bbox and bb lies entirely outside of it
    """
    if cb is None: cb = self._select_bbox
    if cb is None: return False
    return bb[0] > cb[2] or bb[2] < cb[0] or bb[1] > cb[3] or bb[3] < cb[1]

  def set_select_bbox(self, select_bbox):
    if select_bbox is not None and self.all_out(self.overall_bbox, select_bbox):
      msg = 'SHP file %r bbox %s out of select bbox %s' % (self.filename,
          showbb(self.overall_bbox), showbb(select_bbox))
      raise StopIteration, msg
    self._select_bbox = select_bbox

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
    self.filename = filename
    fp = self._fp = open(filename, 'rb')
    fp.seek(32)
    shp_type = read_one(fp, 'i')
    if shp_type not in (3, 5):
      msg = 'SHP file %r shapetype %r, not 3 or 5' % (filename, shp_type)
      raise ValueError, msg
    self.overall_bbox = read_doubles(fp, 4)
    self.set_select_bbox(select_bbox)

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
    # print>>sys.stderr, 'all fields', field_names
    for i, field_name in enumerate(field_names):
      # print 'field:', field_name
      if field_name == id_field_name: break
    else:
      msg = 'DBF file %r has no field named %r' % (dbf_file, id_field_name)
      raise ValueError, msg
    self._db = [entry[i] for entry in self._db]
    self._id_check = id_check

    # try building an ID -> byte offset mapping if the .SHX file is present
    shx_file = filename[:-4] + '.shx'
    try:
      f = open(shx_file, 'rb')
    except IOError:
      # survive missing .SHX file (no indexing in this case, though)
      self._by_id = None
      self._by_recno = None
      self._len = sum(1 for id in self._db if self._id_check(id))
    else:
      self._by_id = {}
      self._by_recno = {}
      with contextlib.closing(f):
        f.seek(100)
        shx_offsets_and_lengths = read_ints(f, 2*len(self._db))
        shx_offsets_and_lengths.byteswap()
        for recno, (id, offs) in enumerate(
            zip(self._db, shx_offsets_and_lengths[0::2])):
          if not self._id_check(id): continue
          self._by_id[id] = self._by_recno[recno+1] = 2*offs
        self._len = len(self._by_id)
    if not self._len:
      raise StopIteration, "No record ID passes the id-check function"

  def __len__(self):
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
    try: offs = offs_dict[key]
    except KeyError: raise KeyError, '%s %r not in index' % (keyname, key)
    else: self._seek_to(offs)

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
    self._set_next(recno, 'Record Number', lambda x: x>=1, self._by_recno)

  # read-only properties for important internal attributes
  for _at in 'last_read_id last_read_recno select_bbox'.split():
    locals()[_at] = property(
        lambda self, _at=_at: getattr(self, '_'+_at))
  del _at

  def close(self):
    """ Close the shapefile. """
    self._fp.close()

  def get_next_record(self, id=1, recno=0, bbox=0, datalen=0, data=1):
    """ Get the next record (if any) with good ID and bounding-box.

    Returns a list with any or all of id, recno, bbox, and data, as requested.
    If no succeeding record is acceptable, returns None

    Args:
      id: bool (default True), should result include the record ID?
      recno: bool (default False), should result include the record number?
      bbox: bool (default False), should result include the record bbox?
      datalen: bool (default False), should result include the tot len of data?
      data: bool (default True), should result include the record data?
    Returns:
      None if no succeeding record is acceptable, else a list with all
        the requested info; data, if requested, is given as 1+ array.array's
        of doubles, in long/lat/long/lat/... order.
    """
    while True:
      try: the_recno, reclen_words = read_and_unpack(self._fp, '>LL')
      except struct.error:
        # print 'EOF on', self._fp, 'at offset', self._fp.tell()
        return None
      endrec = self._fp.tell() + 2*reclen_words
      the_id = self.get_id(the_recno)
      if the_id is None:
        self._fp.seek(endrec)
        continue
      elif the_id is False:
        msg = 'Internal error at rec %r: no id?' % the_recno
        raise SyntaxError, msg
      shapetype = read_one(self._fp, 'i')
      assert shapetype in (3, 5)
      the_bbox = read_doubles(self._fp, 4)
      if self.all_out(the_bbox):
        self._fp.seek(endrec)
        continue
      # record OK, prepare and return result
      self._last_read_id = the_id
      self._last_read_recno = the_recno
      result = []
      if id: result.append(the_id)
      if recno: result.append(the_recno)
      if bbox: result.append(the_bbox)
      if data or datalen:
        # data needed, let's get it
        numparts, numpoints = read_and_unpack(self._fp, '<II')
        if datalen: result.append(numpoints)
        if data:
          # identify lengths of parts
          parts_begin = list(read_ints(self._fp, numparts))
          parts_length = [nx-th for nx,th in zip(parts_begin[1:]+[numpoints],
                                                 parts_begin)]
          # print '#parts=', numparts, '#pts=', numpoints,
          # print 'ptb=', parts_begin, 'ptl=', parts_length
          # read and append to result each part
          for onepart in parts_length:
            result.append(read_doubles(self._fp, 2*onepart))
      self._fp.seek(endrec)
      return result

  def __next__(self):
    result = self.get_next_record()
    if result is None: raise StopIteration
    else: return result


def _test():
    numfailures, numtests = doctest.testmod()
    if numfailures == 0:
      print '%d tests passed successfully' % numtests
    # if there are any failures, doctest does its own reporting!-)

if __name__ == "__main__":
    _test()
