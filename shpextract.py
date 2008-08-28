#!/usr/bin/python

from __future__ import with_statement

""" Process an ARC Shapefile to extract polygons / polylines of interest.

Inspired by Zachary Forest Johnson's shpUtils.py file, found at:
http://indiemaps.com/blog/2008/03/easy-shapefile-loading-in-python/ .  See
http://en.wikipedia.org/wiki/Shapefile for more information about the Shapefile
format.

This module is somewhat-specialized to process the freely available US Census'
TIGER/Line shapefile for all 5-digit ZTCAs in the US; see
http://www.census.gov/geo/www/tiger/ for more information about TIGER/Line
files.  The specialization (besides focusing only on shapefiles that hold
polygons or polylines) lies in the choice of unique-identifier: in this module,
the attribute used as the unique identifier is the one named ZCTA5CE00, and the
module only examines records where that identifier is made of all digits ("real"
zipcodes as opposed to "synthetic" ones for water areas and land wilderness).

This specialization can be countered (allowing the reading of any shapefile of
polygons or polylines) by instantiating the Shp class with other explicit
values of optional parameters id_field_name (str, default 'ZTCA5CE00') and/or
id_field_check (callable, must return a false value for unacceptable IDs).

The module assumes all bounding boxes are 4 doubles in order: xmin, ymin, xmax,
ymax; AKA 2 points in order WS, EN; the module provides a utility function to
make a bbox in that SHP-oriented format given the format that's more natural in
KML &c, which is SW, NE, and an optional magnification around the box center.
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
  h2 = (sw[0] - ne[0])/2
  w2 = (sw[1] - ne[1])/2
  assert h>0 and w>0 and magnify>0
  # compute center of bbox
  c0 = ne[0] + h2
  c1 = ne[1] + w2
  h2 *= magnify
  w2 *= magnify
  xmin = c1 - w2
  xmax = c1 + w2
  ymin = c0 - h2
  ymax = c0 + h2
  return xmin, ymin, xmax, ymax


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
  """ Read bytes from file and unpack as little-endian w/given typecode.

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
    return bb[0]>cb[2] or bb[2]<cb[0] or bb[1]>cb[3] or bb[3]<cb[1]

  def __init__(self, filename, select_bbox=None,
      id_field_name='ZTCA5CE00', id_check=lambda id: id.isdigit()):
    # get basic shapefile configuration
    fp = self.fp = open(filename, 'rb')
    fp.seek(32)
    shp_type = read_one(fp, 'i')
    if shp_type not in (3, 5):
      msg = 'SHP file %r shapetype %r, not 3 or 5' % (filename, shp_type)
      raise ValueError, msg
    self.overall_bbox = read_doubles(fp, 4)
    self.select_bbox = select_bbox
    if self.all_out(self.overall_bbox):
      msg = 'SHP file %r bbox %s out of select bbox %s' % (filename,
          showbb(self.overall_bbox), select_bbox)
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
    shx_file = filename[:-4] + '.shx')
    try:
      f = open(shx_file, 'rb')
    except IOError:
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
	  self._by_id[id] = 2*offs
	  self._by_recno[recno] = 2*offs
	self._len = len(self._by_id)

  def __length__(self):
    return self._len

  def __iter__(self):
    return self

  def _seek_to(self, offs):
    self.fp.seek(offs)
    self._last_read_id = None
    self._last_read_recno = None

  def rewind(self):
    """ Re-start reading the shapefile from the first record.
    """
    self._seek_to(100)

  def set_next_id(self, id):
    if not self._id_check(id):
      raise ValueError, 'Invalid ID %r' % id
    elif self._by_id is None:
      raise AttributeError, 'SHX was not present, SHP not indexable'
    elif id not in self._by_id:
      raise KeyError, 'ID %r not in index' % id
    self._seek_to(self._by_id[id])

  def set_next_recno(self, recno):
    if recno<1:
      raise ValueError, 'Invalid recno %r' % recno
    elif self._by_recno is None:
      raise AttributeError, 'SHX was not present, SHP not indexable'
    elif recno not in self._by_recno:
      raise IndexError, 'Record # %r not in index' % recno
    self._seek_to(self._by_recno[recno])

  @property
  def last_read_id(self):
    return self._last_read_id

  @property
  def last_read_recno(self):
    return self._last_read_recno

  def close(self):
    """ Close the shapefile.
    """
    self.fp.close()

    records.append(shp_record)
    nr += 1
    if maxn is not None and nr >= maxn:
      break

  # TODO: finish it up from here
  def get_next_record(self, id=1, recno=0, bbox=0, data=1):
    result = []
    the_recno = read_and_unpack(self._fp, '>L')
    the_id = self.get_id(the_recno)
    if not the_id: return the_id

    

  return records



record_class = {0:'RecordNull', 1:'RecordPoint', 8:'RecordMultiPoint',
    3:'RecordPolyLine', 5:'RecordPolygon'}

def createRecord(fp):
  # read header
  record_number = readAndUnpack('>L', fp.read(4))
  if record_number == '':
    print 'doner'
    return False
  else:
    print 'Reading record #%d' % record_number
  content_length = readAndUnpack('>L', fp.read(4))
  nexter = fp.tell() + 2*content_length
  record_shape_type = readAndUnpack('<L', fp.read(4))

  shp_data = readRecordAny(fp, record_shape_type, nexter)
  if shp_data is None:
    return None
  dbf_data = {}
  for i in range(0, len(db[record_number+1])):
    if db[0][i] != 'ZCTA5CE00': continue
    dbf_data['zip'] = db[record_number+1][i]
    if not dbf_data['zip'].isdigit(): return None
    break

  return {'shp_data':shp_data, 'dbf_data':dbf_data}

# Reading defs

def readRecordAny(fp, type, nexter):
  if type==0:
    record = readRecordNull(fp, nexter)
  elif type==1:
    record = readRecordPoint(fp)
  elif type==8:
    record = readRecordMultiPoint(fp, nexter)
  elif type==3 or type==5:
    record = readRecordPolyLine(fp, nexter)
  else:
    return False
  # record['type'] = type
  return record

def readRecordNull(fp):
  data = {}
  return data

point_count = 0
def readRecordPoint(fp):
  global point_count
  data = {}
  data['x'] = readAndUnpack('d', fp.read(8))
  data['y'] = readAndUnpack('d', fp.read(8))
  point_count += 1
  return data


def readRecordMultiPoint(fp, nexter):
  data = readBoundingBox(fp)
  data['numpoints'] = readAndUnpack('i', fp.read(4))
  for i in range(0,data['numpoints']):
    data['points'].append(readRecordPoint(fp))
  return data


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

# General defs

def readBoundingBox(fp):
  data = {}
  data['xmin'] = readAndUnpack('d',fp.read(8))
  data['ymin'] = readAndUnpack('d',fp.read(8))
  data['xmax'] = readAndUnpack('d',fp.read(8))
  data['ymax'] = readAndUnpack('d',fp.read(8))
  return data

def readAndUnpack(type, data):
  if data=='': return data
  return struct.unpack(type, data)[0]

def intersect(data):
  if data['xmax'] < bb[0]: return False
  if data['ymax'] < bb[2]: return False
  if data['xmin'] > bb[1]: return False
  if data['ymin'] > bb[3]: return False
  # print data, 'DOES intersect', bb, '!'
  return True

####
#### additional functions
####

def getCentroids(records, projected=False):
  # for each feature
  if projected:
    points = 'projectedPoints'
  else:
    points = 'points'

  for feature in records:
    numpoints = cx = cy = 0
    for part in feature['shp_data']['parts']:
      for point in part[points]:
        numpoints += 1
        cx += point['x']
        cy += point['y']
    cx /= numpoints
    cy /= numpoints
    feature['shp_data']['centroid'] = {'x':cx, 'y':cy}


def getBoundCenters(records):
  for feature in records:
    cx = .5 * (feature['shp_data']['xmax']-feature['shp_data']['xmin']) + feature['shp_data']['xmin']
    cy = .5 * (feature['shp_data']['ymax']-feature['shp_data']['ymin']) + feature['shp_data']['ymin']
    feature['shp_data']['boundCenter'] = {'x':cx, 'y':cy}

def getTrueCenters(records, projected=False):
  #gets the true polygonal centroid for each feature (uses largest ring)
  #should be spherical, but isn't

  if projected:
    points = 'projectedPoints'
  else:
    points = 'points'

  for feature in records:
    maxarea = 0
    for ring in feature['shp_data']['parts']:
      ringArea = getArea(ring, points)
      if ringArea > maxarea:
        maxarea = ringArea
        biggest = ring
    #now get the true centroid
    tempPoint = {'x':0, 'y':0}
    if biggest[points][0] != biggest[points][len(biggest[points])-1]:
      print "mug", biggest[points][0], biggest[points][len(biggest[points])-1]
    for i in range(0, len(biggest[points])-1):
      j = (i + 1) % (len(biggest[points])-1)
      tempPoint['x'] -= (biggest[points][i]['x'] + biggest[points][j]['x']) * ((biggest[points][i]['x'] * biggest[points][j]['y']) - (biggest[points][j]['x'] * biggest[points][i]['y']))
      tempPoint['y'] -= (biggest[points][i]['y'] + biggest[points][j]['y']) * ((biggest[points][i]['x'] * biggest[points][j]['y']) - (biggest[points][j]['x'] * biggest[points][i]['y']))

    tempPoint['x'] = tempPoint['x'] / ((6) * maxarea)
    tempPoint['y'] = tempPoint['y'] / ((6) * maxarea)
    feature['shp_data']['truecentroid'] = tempPoint


def getArea(ring, points):
  #returns the area of a polygon
  #needs to be spherical area, but isn't
  area = 0
  for i in range(0,len(ring[points])-1):
    j = (i + 1) % (len(ring[points])-1)
    area += ring[points][i]['x'] * ring[points][j]['y']
    area -= ring[points][i]['y'] * ring[points][j]['x']

  return math.fabs(area/2)


def getNeighbors(records):

  #for each feature
  for i in range(len(records)):
    #print i, records[i]['dbf_data']['ADMIN_NAME']
    if not 'neighbors' in records[i]['shp_data']:
      records[i]['shp_data']['neighbors'] = []

    #for each other feature
    for j in range(i+1, len(records)):
      numcommon = 0
      #first check to see if the bounding boxes overlap
      if overlap(records[i], records[j]):
        #if so, check every single point in this feature to see if it matches a point in the other feature

        #for each part:
        for part in records[i]['shp_data']['parts']:

          #for each point:
          for point in part['points']:

            for otherPart in records[j]['shp_data']['parts']:
              if point in otherPart['points']:
                numcommon += 1
                if numcommon == 2:
                  if not 'neighbors' in records[j]['shp_data']:
                    records[j]['shp_data']['neighbors'] = []
                  records[i]['shp_data']['neighbors'].append(j)
                  records[j]['shp_data']['neighbors'].append(i)
                  #now break out to the next j
                  break
            if numcommon == 2:
              break
          if numcommon == 2:
            break




def projectShapefile(records, whatProjection, lonCenter=0, latCenter=0):
  print 'projecting to ', whatProjection
  for feature in records:
    for part in feature['shp_data']['parts']:
      part['projectedPoints'] = []
      for point in part['points']:
        tempPoint = projectPoint(point, whatProjection, lonCenter, latCenter)
        part['projectedPoints'].append(tempPoint)

def projectPoint(fromPoint, whatProjection, lonCenter, latCenter):
  latRadians = fromPoint['y'] * math.pi/180
  if latRadians > 1.5: latRadians = 1.5
  if latRadians < -1.5: latRadians = -1.5
  lonRadians = fromPoint['x'] * math.pi/180
  lonCenter = lonCenter * math.pi/180
  latCenter = latCenter * math.pi/180
  newPoint = {}
  if whatProjection == "MERCATOR":
    newPoint['x'] = (180/math.pi) * (lonRadians - lonCenter)
    newPoint['y'] = (180/math.pi) * math.log(math.tan(latRadians) + (1/math.cos(latRadians)))
    if newPoint['y'] > 200:
      newPoint['y'] = 200
    if newPoint['y'] < -200:
      newPoint['y'] = 200
    return newPoint
  if whatProjection == "EQUALAREA":
    newPoint['x'] = 0
    newPoint['y'] = 0
    return newPoint


def overlap(feature1, feature2):
  if (feature1['shp_data']['xmax'] > feature2['shp_data']['xmin'] and feature1['shp_data']['ymax'] > feature2['shp_data']['ymin'] and feature1['shp_data']['xmin'] < feature2['shp_data']['xmax'] and feature1['shp_data']['ymin'] < feature2['shp_data']['ymax']):
    return True
  else:
    return False
