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
     numparts unsigned ints: starts of each part
     numparts unsigned ints: lengts of each part
     totleng signed ints: x then y for each point in each part (meters)
"""
import array
import cStringIO
import logging
import struct
import zipfile

import shpextract
import tile

if shpextract.big_endian:
  def normalize_arrays(*arrays): pass
else:
  def normalize_arrays(*arrays):
    for a in arrays: a.byteswap()

def merge_bbox(bb, obb, mima=(min,min,max,max)):
  for i in range(4): bb[i] = mima[i](bb[i], obb[i])

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
    self.m = tile.GlobalMercator()
    self.idnum_by_idvalue = dict()
    self._closed = False

  def close(self):
    if self._closed: return
    self.shp.close()
    self.zip.close()
    self._closed = True

  def doit(self):
    ll2m = self.m.LatLonToMeters
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
      out.write(parts_starts.tostring())
      out.write(parts_lengths.tostring())

      logging.debug('%s (%d): %d@%d', id, idnum, numparts, total_length)

      for p in indata:
        lats = iter(p)
        oudata = array.array('l', [0]*len(p))
        i = 0
        for lat in lats:
          lon = lats.next()
          x, y = ll2m(lat, lon)
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

    out = cStringIO.StringIO()
    bbout = array.array('l')
    x, y = ll2m(overall_bbox[0], overall_bbox[1])
    bbout.append(int(x))
    bbout.append(int(y))
    x, y = ll2m(overall_bbox[2], overall_bbox[3])
    bbout.append(int(x))
    bbout.append(int(y))
    normalize_arrays(bbout)
    out.write(bbout.tostring())
    self.zip.writestr('bbox.bin', out.getvalue())
    out.close()

    self.close()

if __name__ == '__main__':

  def main():
    logging.basicConfig(format='%(levelname)s: %(message)s')
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    c = Converter()
    c.doit()

  main()

