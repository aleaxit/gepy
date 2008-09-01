""" Given a zoom factor and a bbox, produce the relevant 256x256 PNG files.
"""
import os

import tile
import pypng
import shpextract

m = tile.GlobalMercator()

def do_tile(xt, yt, zoom, name):
  print ' Creating file %s' % name
  minlat, minlon, maxlat, maxlon = m.TileLatLonBounds(xt, yt, zoom)
  print ' BB:', minlat, minlon, maxlat, maxlon
  s.set_select_bbox((minlon, minlat ,maxlon, maxlat))
  s.rewind()
  zips = []
  for r in s: zips.append(r[0])
  print ' Zipcodes:', ' '.join(sorted(zips))

def what_tiles(zoom, minlat, minlon, maxlat, maxlon):
  print 'tiles for', minlat, minlon, maxlat, maxlon
  minx_tile, miny_tile = m.LatLonToTile(minlat, minlon, zoom)
  maxx_tile, maxy_tile = m.LatLonToTile(maxlat, maxlon, zoom)
  print "Tiles at zoom %d: %d/%d to %d/%d" % (
      zoom, minx_tile, miny_tile, maxx_tile, maxy_tile)
  for xt in range(minx_tile, maxx_tile+1):
    for yt in range(miny_tile, maxy_tile+1):
      gxt, gyt = m.GoogleTile(xt, yt, zoom)
      print 'Tile (Z=%d) %d/%d (Goog %d/%d):' % (zoom, xt, yt, gxt, gyt)
      name = 'tile_%d_%d_%d.png' % (zoom, gxt, gyt)
      if os.path.exists(name):
        print 'File %s already exists' % name
        continue
      do_tile(xt, yt, zoom, name)

def main():
  global s
  s = shpextract.Shp('ca/zt06_d00.shp', id_field_name='ZCTA')
  s.set_next_id('94303')
  r = s.get_next_record(id=0, recno=0, bbox=1, datalen=0, data=0)
  bb = r[0]
  what_tiles(10, bb[1], bb[0], bb[3], bb[2])

main()
