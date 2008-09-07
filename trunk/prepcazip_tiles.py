""" Prepare tiles for CA zipcode boundaries as PNG files in /tmp/.

Overall input is Shapefile ca/zt06_d00.shp .
This script makes an intermediate Polyfile cazip.ply in the current directory,
then uses this Polyfile to paint PNG tiles in /tmp/ for all relevant tiles.
"""
from __future__ import with_statement

import cStringIO
import logging
import os
import sys

from PIL import Image, ImageDraw, ImageFont, ImagePath

import shp2polys
import tile

POLYFILE = 'cazip.ply'

class Converter(shp2polys.Converter):
  """ A Shapefile-to-Polyfile converter for the CA zipfile boundaries. """
  infile = 'ca/zt06_d00.shp'
  oufile = 'cazip.ply'
  nameid = 'ZCTA'
  @classmethod
  def valid(cls, id): return id.isdigit()


class PolyReader(shp2polys.PolyReader):
  """ A Polyfile reader for the CA zipfile boundaries. """
  infile = Converter.oufile


def s(aray):
  """ Return a reasonable string to display several floats.

  Args:
    aray: a sequence of floats
  Returns:
    a str with comma-separated 2-digits reprs of floats within brackets
  """
  res = []
  for x in aray: res.append('%.2f' % x)
  return '[%s]' % ','.join(res)


def main():
  """ Perform the script's tasks. """
  shp2polys.setlogging()

  name_format = 'tile_ZIPCA_%s_%s_%s'
  MIN_ZOOM = 6
  MAX_ZOOM = 12
  m = tile.GlobalMercator()

  if not os.path.isfile(POLYFILE):
    logging.info('Building %r', POLYFILE)
    c = Converter(infile='ca/zt06_d00.shp', oufile=POLYFILE, nameid='ZTCA',
                  valid=str.isdigit)
    c.doit()

  r = PolyReader(infile=POLYFILE)
  for zoom in range(MIN_ZOOM, MAX_ZOOM+1):
    bb = r.get_tiles_ranges(zoom)
    size = 256*(bb[2]-bb[0]+1), 256*(bb[3]-bb[1]+1)
    logging.info('zoom %s: tiles %s, size %s', r.zoom, bb, size)
    white = 0
    try: im = Image.new('P', size, white)
    except MemoryError:
      logging.error('sorry, zoom %r takes too much memory, stopping', zoom)
      break
    palette = [255]*3 + [255, 0, 0] + [0, 255, 0]
    red = 1
    green = 2
    im.putpalette(palette)

    # draw all polygons -> prepare 1 large image with all tiles side by side
    matrix = m.getMetersToPixelsXform(zoom, bb)
    draw = ImageDraw.Draw(im)
    for name, bbox, starts, lengths, meters in r:
      for s, l in zip(starts, lengths):
        p = ImagePath.Path(meters[s:s+l])
        p.transform(matrix)
        draw.polygon(p, outline=red)
    del draw 

    # save all tiles (obtained by chopping the 1 large image in 256x256 squares)
    for tx in range(bb[0], bb[2]+1):
      left = (tx-bb[0]) * 256
      right = left+255
      for ty in range(bb[1], bb[3]+1):
        top = (bb[3]-ty) * 256
        bottom = top+255
        tileim = im.crop((left, top, right, bottom))
        # explicitly skip tiles with no pixels drawn on them
        if tileim.getbbox() is None:
          logging.debug('Skip empty tile %s/%s', tx, ty)
          continue
        gtx, gty = m.GoogleTile(tx, ty, zoom)
        name = name_format % (zoom, gtx, gty)
        out = cStringIO.StringIO()
        tileim.save(out, format='PNG', transparency=white)
        data = out.getvalue()
        out.close()
        with open('/tmp/%s.png'%name, 'wb') as f:
          f.write(data)

if __name__ == '__main__':
  main()

