""" Convert a Shapefile (.shp + .dbf +.shf) into a "polyfile" for fast drawing.

Read a Shapefile (e.g. a TIGER/Line file) containing polygons for some kinds of
boundaries, and produce a Polyfile suitable for fast drawing on Google Maps
(and similar) "tiles".

To customize the conversion's details, you need to subclass the class
shp2polys.Converter provided by this module, and override:
   infile, oufile, nameid: str naming input/output files and record-id field
   and either:
     def valid(cls, id): method returning true if id is valid
   or:
     excluded_ids: set of ids to exclude (to use the provided 'valid' method)
To perform the conversion, init x=ConverterSubclass(), and just call x.doit().

Running this module as a script performs the following operation:
  - reads a Shapefile named fe_2007_us_state/fe_2007_us_state.shp
  - writes a Polyfile named cont_us_state.ply
  - uses as record-identifier the field named STUSPS
  - excludes records for "states" coded: HI AK VI GU PR AS MP

A Polyfile is a zipfile with the following internal organization:
     ids.txt: textfile, each line '<idstring> <idnumber>\n'
     bbox.bin: 4 little-endian 4 bytes ints: bounding box for the whole
       file, meters, in order minx, miny, maxx, maxy
   and a collection of little-end bin files named <idstring>_<recno>.pol, each:
     (4-byte ints...):
     3 unsigned ints: idnum, numparts, totleng
     4 signed ints: bbox for the file (minx, miny, maxx, maxy)
     numparts unsigned ints: starts of each part
     numparts unsigned ints: lengths of each part
     totleng signed ints: x then y for each point in each part (meters)
"""
import array
import cStringIO
import logging
import struct
import zipfile

import shpextract
import tile

m = tile.GlobalMercator()

# ensure all arrays are little-endian
if shpextract.big_endian:
  def normalize_arrays(*arrays):
    for a in arrays: a.byteswap()
else:
  def normalize_arrays(*arrays): pass

def merge_bbox(bb, obb, mima=(min,min,max,max)):
  logging.debug(' MrgBB %s', ' '.join('%.2f'%x for x in obb))
  for i in range(4): bb[i] = mima[i](bb[i], obb[i])

def encode_bbox(bbox):
  ll2m = m.LatLonToMeters
  bbout = array.array('l')
  for i in (0, 2):
    x, y = ll2m(bbox[i+1], bbox[i])
    bbout.append(int(x))
    bbout.append(int(y))
  normalize_arrays(bbout)
  out = cStringIO.StringIO()
  out.write(bbout.tostring())
  try: return out.getvalue()
  finally: out.close()

class Converter(object):
  """ Performs Shapefile -> Polyfile conversion. """
  # overridable data and methods
  infile = 'fe_2007_us_state/fe_2007_us_state.shp'
  oufile = 'cont_us_state.ply'
  nameid = 'STUSPS'
  excluded_ids = set('HI AK VI GU PR AS MP'.split())
  @classmethod
  def valid(cls, id): return id not in cls.excluded_ids

  def __init__(self):
    self.shp = shpextract.Shp(self.infile, None, self.nameid, self.valid)
    self.zip = zipfile.ZipFile(self.oufile, 'w', zipfile.ZIP_DEFLATED)
    self.idnum_by_idvalue = dict()
    self._closed = False

  def close(self):
    if self._closed: return
    self.shp.close()
    self.zip.close()
    self._closed = True

  def doit(self):
    ll2m = m.LatLonToMeters
    def recno_id_bbox_data(s=self.shp):
      i = 0
      while True:
        rec = s.get_next_record(bbox=1)
        if rec is None: return
        yield i, rec[0], rec[1], rec[2:]
        i += 1

    class Extreme(object):
      def __init__(self, allcmp): self.allcmp = allcmp
      def __cmp__(self, other): return self.allcmp
    High = Extreme(1); Low = Extreme(-1)
    overall_bbox = [High, High, Low, Low]

    for recno, id, bbox, indata in recno_id_bbox_data():
      if id not in self.idnum_by_idvalue:
        self.idnum_by_idvalue[id] = len(self.idnum_by_idvalue)
      idnum = self.idnum_by_idvalue[id]
      merge_bbox(overall_bbox, bbox)
      numparts = len(indata)
      parts_starts = array.array('L', [0])
      parts_lengths = array.array('L')
      for p in indata:
        parts_lengths.append(len(p))
        parts_starts.append(parts_starts[-1] + len(p))
      total_length = parts_starts.pop()
      normalize_arrays(parts_starts, parts_lengths)
      out = cStringIO.StringIO()
      out.write(struct.pack('<LLL', idnum, numparts, total_length))
      out.write(encode_bbox(bbox))
      out.write(parts_starts.tostring())
      out.write(parts_lengths.tostring())

      logging.debug('%s (%d): %d@%d', id, idnum, numparts, total_length)

      for p in indata:
        lons = iter(p)
        oudata = array.array('l', [0]*len(p))
        i = 0
        for lon in lons:
          lat = lons.next()
          x, y = ll2m(lat, lon)
          if i==0:
            logging.debug(' Lalo=(%.2f %.2f) xy=(%.2f %.2f)', lat, lon, x, y)
          try:
            oudata[i] = int(x)
            oudata[i+1] = int(y)
          except (OverflowError, ValueError), err:
            logging.fatal('(%s,%s) -> (%s,%s)', lat, lon, x, y)
            raise
          i += 2
        normalize_arrays(oudata)
        out.write(oudata.tostring())
      self.zip.writestr('%s_%d.pol' % (id, recno), out.getvalue())
      out.close()

    out = cStringIO.StringIO()
    for id in sorted(self.idnum_by_idvalue):
      idnum = self.idnum_by_idvalue[id]
      out.write('%s %d\n' % (id, idnum))
    self.zip.writestr('ids.txt', out.getvalue())
    out.close()

    logging.debug(' OvaBB %s', ' '.join('%.2f'%x for x in overall_bbox))
    self.zip.writestr('bbox.bin', encode_bbox(overall_bbox))

    self.close()


def setlogging(level=logging.DEBUG):
    logging.basicConfig(format='%(levelname)s: %(message)s')
    logger = logging.getLogger()
    logger.setLevel(level)


class PolyReader(object):
  infile = 'cont_us_state.ply'

  def __init__(self, zoom=4):
    self.zip = zipfile.ZipFile(self.infile, 'r')
    self._closed = False
    self.zoom = zoom
    names_and_nums = self.zip.read('ids.txt').splitlines()
    self.name_by_num = dict()
    for line in names_and_nums:
      name, num = line.split()
      self.name_by_num[int(num)] = name
    self.filenames = [s for s in self.zip.namelist() if s.endswith('.pol')]

  def __iter__(self):
    def prg():
      for name in self.filenames:
        filedata = self.zip.read(name)
        idnum, numparts, totleng = struct.unpack('<III', filedata[:12])
        bbox = array.array('l')
        bbox.fromstring(filedata[12:28])
        starts = array.array('L')
        starts.fromstring(filedata[28:28+4*numparts])
        lengths = array.array('L')
        lengths.fromstring(filedata[28+4*numparts:28+8*numparts])
        meters = array.array('l')
        meters.fromstring(filedata[28+8*numparts:28+8*numparts+4*totleng])
        yield self.name_by_num[idnum], bbox, starts, lengths, meters
    return prg()

  def close(self):
    if self._closed: return
    self.zip.close()
    self._closed = True

  def setzoom(self, zoom):
    self.zoom = zoom

  def get_tiles_ranges(self):
    bb = array.array('l')
    filedata = self.zip.read('bbox.bin')
    bb.fromstring(filedata)
    logging.debug('BB: %s', list(bb))
    mintx, minty = m.MetersToTile(bb[0], bb[1], self.zoom) 
    maxtx, maxty = m.MetersToTile(bb[2], bb[3], self.zoom) 
    return mintx, minty, maxtx, maxty
 

if __name__ == '__main__':

  def main():
    setlogging()
    c = Converter()
    c.doit()
    r = PolyReader()
    bb = r.get_tiles_ranges()
    print 'zoom %s: tiles %s' % (r.zoom, bb)

  main()

