""" Given a zoom factor and a bbox, produce the relevant 256x256 PNG files.
"""
from __future__ import with_statement

import logging
import os
import sys

import tile
import pypng
import shpextract
sbb = shpextract.showbb

ZOOM = 12

# unique global Mercator calculator
m = tile.GlobalMercator()
# current global SHP object
s = None

def do_tile(xt, yt, zoom, name=None):
  # print>>sys.stderr, ' Creating file %s' % name
  minlat, minlon, maxlat, maxlon = m.TileLatLonBounds(xt, yt, zoom)
  logging.debug('Tile %s/%s/%s bounds %s',
    xt, yt, zoom, sbb((minlat,minlon,maxlat,maxlon)))
  # print 'Til bnds:', minlat, minlon, maxlat, maxlon
  # print>>sys.stderr, ' BB:', minlat, minlon, maxlat, maxlon
  # careful with the order of params to s: it wants lon, lat (x, y) order!
  s.set_select_bbox((minlon, minlat, maxlon, maxlat))
  s.rewind()
  # note min/max lat must be swapped in PNG drawing to get the Y axis right!
  # also, lat=y axis, lon=y axis, so careful with the arguments order...!!!
  png = pypng.PNG(minlon, maxlat, maxlon, minlat)
  red = png.get_color(255, 0, 0)
  for r in s:
    for d in r[1:]:
      png.polyline(d, red)
  data = png.dump()
  if name is not None:
    with open(name, 'wb') as f:
      f.write(data)
  return data

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

def tile_coords_generator(zoom, minlat, minlon, maxlat, maxlon):
  logging.debug('Tiles covering %s', sbb((minlat,minlon,maxlat,maxlon)))
  meters = m.LatLonToMeters(minlat, minlon)
  minx_tile, miny_tile = m.LatLonToTile(minlat, minlon, zoom)
  tmila, tmilo, tmala, tmalo = m.TileLatLonBounds(minx_tile, miny_tile, zoom)
  logging.debug('%s cov by %s', sbb((minlat,minlon)),
      sbb((tmila,tmilo,tmala,tmalo)))
  # tilemeters = m.TileBounds(minx_tile, miny_tile, zoom)
  # logging.info('in m, %s cov by %s', sbb(meters), sbb(tilemeters))

  maxx_tile, maxy_tile = m.LatLonToTile(maxlat, maxlon, zoom)
  tmila, tmilo, tmala, tmalo = m.TileLatLonBounds(maxx_tile, maxy_tile, zoom)
  logging.debug('%s cov by %s', sbb((maxlat,maxlon)),
      sbb((tmila,tmilo,tmala,tmalo)))
  logging.debug('Tiles x=%s:%s, y=%s:%s',
      minx_tile, maxx_tile, miny_tile, maxy_tile)
  for xt in range(minx_tile, maxx_tile+1):
    for yt in range(miny_tile, maxy_tile+1):
      gxt, gyt = m.GoogleTile(xt, yt, zoom)
      yield gxt, gyt, xt, yt, zoom

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
  return do_tile(gx, gy, z, name)

def usatile(x, y, z, name):
  global s
  s = shpextract.Shp('fe_2007_us_state/fe_2007_us_state.shp',
                     id_field_name='STUSPS', id_check=lambda x: True)
  gx, gy = m.GoogleTile(x, y, z)
  return do_tile(gx, gy, z, name)

if __name__ == '__main__':
  main()

