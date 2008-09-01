""" Given a zoom factor and a bbox, produce the relevant 256x256 PNG files.
"""
from __future__ import with_statement

import os
import sys

import tile
import pypng
import shpextract

ZOOM = 12

m = tile.GlobalMercator()

def do_tile(xt, yt, zoom, name):
  print>>sys.stderr, ' Creating file %s' % name
  minlat, minlon, maxlat, maxlon = m.TileLatLonBounds(xt, yt, zoom)
  print>>sys.stderr, ' BB:', minlat, minlon, maxlat, maxlon
  s.set_select_bbox((minlon, minlat, maxlon, maxlat))
  s.rewind()
  # zips = set(r[0] for r in s)
  # print ' Zipcodes:', ' '.join(sorted(zips))
  # s.rewind()
  png = pypng.PNG(minlon, minlat, maxlon, maxlat)
  red = png.get_color(255, 0, 0)
  for r in s:
    # if r[0] != '94303': continue
    # print 'drawing 94303...'
    for d in r[1:]:
      png.polyline(d, red)
  with open(name, 'wb') as f:
    f.write(png.dump())

def what_tiles(zoom, minlat, minlon, maxlat, maxlon):
  print>>sys.stderr, 'tiles for', minlat, minlon, maxlat, maxlon
  minx_tile, miny_tile = m.LatLonToTile(minlat, minlon, zoom)
  maxx_tile, maxy_tile = m.LatLonToTile(maxlat, maxlon, zoom)
  print>>sys.stderr, "Tiles at zoom %d: %d/%d to %d/%d" % (
      zoom, minx_tile, miny_tile, maxx_tile, maxy_tile)
  for xt in range(minx_tile, maxx_tile+1):
    for yt in range(miny_tile, maxy_tile+1):
      gxt, gyt = m.GoogleTile(xt, yt, zoom)
      print>>sys.stderr, 'Tile (Z=%d) %d/%d (Goog %d/%d):' % (
          zoom, xt, yt, gxt, gyt)
      name = 'tile_%d_%d_%d.png' % (zoom, gxt, gyt)
      if os.path.exists(name):
        print>>sys.stderr, 'File %s already exists, skipping' % name
        continue
      do_tile(xt, yt, zoom, name)

def main():
  global s
  s = shpextract.Shp('ca/zt06_d00.shp', id_field_name='ZCTA')
  recs = s.recnos_by_id('94303')
  assert len(recs) == 1
  s.set_next_recno(recs[0])
  r = s.get_next_record(id=0, recno=0, bbox=1, datalen=0, data=0)
  bb = r[0]
  print>>sys.stderr, 'removing all existing PNG files'
  os.system('rm *.png')
  what_tiles(ZOOM, bb[1], bb[0], bb[3], bb[2])

def onetile(x, y, z, name):
  global s
  s = shpextract.Shp('ca/zt06_d00.shp', id_field_name='ZCTA')
  gx, gy = m.GoogleTile(x, y, z)
  do_tile(gx, gy, z, name)

if __name__ == '__main__':
  main()

