#!/usr/bin/python

from __future__ import with_statement

""" Process an ARC Shapefile to extract polygons / polylines of interest.

Inspired by Zachary Forest Johnson's shpUtils.py file, found at:
http://indiemaps.com/blog/2008/03/easy-shapefile-loading-in-python/ .  See
http://en.wikipedia.org/wiki/Shapefile for more information about the Shapefile
format.

This module is specialized to process the freely available US Census' TIGER/Line
shapefile for all 5-digit ZTCAs in the US; see
http://www.census.gov/geo/www/tiger/ for more information about TIGER/Line
files.  The specialization (besides focusing only on shapefiles that hold
polygons or polylines) lies in the choice of unique-identifier: in this module,
the attribute used as the unique identifier is the one named ZCTA5CE00, and the
module only examines records where that identifier is made of all digits ("real"
zipcodes as opposed to "synthetic" ones for water areas and land wilderness).

The module assumes all bounding boxes are 4 doubles in order: xmin, ymin, xmax,
ymax; AKA 2 points in order WN, ES; the module provides a utility function to
make a bbox in that SHP-oriented format given the format that's more natural in
KML &c, which is SW, NE, and an optional magnification around the box center.
"""
import itertools
import math
import struct
import dbfUtils

XY_POINT_RECORD_LENGTH = 16

def dobox(sw, ne, magnify=1.0):
  h = ne[0] - sw[0]
  w = ne[1] - sw[1]
  assert h>0 and w>0 and magnify>0
  c0 = ne[0] + h/2
  c1 = ne[1] + w/2
  h *= magnify/2
  w *= magnify/2
  xmin = c1 - w
  xmax = c1 + w
  ymin = c0 - h
  ymax = c0 + h
  return xmin, ymin, xmax, ymax

class shp(object):

  def getid(self, record_number):
    try: id = self.db[record_number-1][self._id_field]
    except IndexError: return None
    if not id.isdigit(): return None
    return id

  def __init__(self, filename, id_field_name='ZTCA5CE00'):
    # get basic shapefile configuration
    fp = self.fp = open(filename, 'rb')
    fp.seek(32)
    shp_type = readAndUnpack('i', fp.read(4))
    if shp_type not in (3, 5):
      msg = 'SHP file %r shapetype %r, not 3 or 5' % (filename, shp_type)
      raise ValueError, msg
    self.overall_bbox = readBoundingBox(fp)
    self.select_bbox = None
    # position at first record
    fp.seek(100)

    # open dbf file and get records as a list
    dbf_file = filename[:-4] + '.dbf'
    with open(dbf_file, 'rb') as dbf:
      dbr = dbfUtils.dbfreader(dbf)
      field_names = dbr.next()
      field_specs = dbr.next()
      self.db = list(dbr)
    # identify index unique-ID field
    for i, field_name in enumerate(field_names):
      if field_name == id_field_name: break
    else:
      msg = 'DBF file %r has no field named %r' % (dbf_file, id_field_name)
      raise ValueError, msg
    self._id_field = i

  def set_select_bbox(self, bbox):
    


  # fetch Records
  fp.seek(100)
  nr = 0
  while True:
    shp_record = createRecord(fp)
    if shp_record is None:
      # print 'none'
      continue
    elif shp_record == False:
      # print 'break'
      break
    # print 'nr:', nr
    records.append(shp_record)
    nr += 1
    if maxn is not None and nr >= maxn:
      break

  return records


def loadShapefileIntersecting(file_name, (y0, x0, y1, x1), maxn=None):
  global db
  shp_bounding_box = []
  shp_type = 0
  file_name = file_name
  records = []
  # open dbf file and get all records as a list
  dbf_file = file_name[0:-4] + '.dbf'
  dbf = open(dbf_file, 'rb')
  db = list(dbfUtils.dbfreader(dbf))
  dbf.close()
  print 'Read %d records from DBF file' % len(db)

  fp = open(file_name, 'rb')

  # get basic shapefile configuration
  fp.seek(32)
  shp_type = readAndUnpack('i', fp.read(4))
  shp_bounding_box = readBoundingBox(fp)
  global bb
  bb = (x0, x1, y0, y1)

  # fetch Records
  fp.seek(100)
  nr = 0
  while True:
    shp_record = createRecord(fp)
    if shp_record is None:
      # print 'none'
      continue
    elif shp_record == False:
      # print 'break'
      break
    print 'nr:', nr
    records.append(shp_record)
    nr += 1
    if maxn is not None and nr >= maxn:
      break

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
