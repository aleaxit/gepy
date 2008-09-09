""" Add tiles for one level of zoom on one theme.

Invoke this script with an argument, the theme name, from gepy's repo root.
Script loads gae/<theme>_dict.pik to determine what zoom level has been
  already finished for the theme, and adds one more zoom level.

Theme must be 'known' in order to let the script determine Shapefile,
Polyfile and/or ID Field Name for the theme in question.

If the theme is known, but there is as yet no .pik file for it, then you must
also specify on the command line the min and max zoom levels you want (or just
one zoom level, to be both the min and max, i.e., the only zoom level for the
new theme).  Explicit specification of min and max zoom (or just one) is also
allowed if the .pik file is already there; in that case, tiles will be done (and
put in place of the old ones) for the zoom level[s] you specified.
"""
from __future__ import with_statement

import cPickle
import cStringIO
import glob
import logging
import os
import sys

from PIL import Image, ImageDraw, ImageFont, ImagePath

import shp2polys
import tile
PIK_FORMAT = 'gae/%s_dict.pik'

class ThemeData(dict):
  __getattr__ = dict.__getitem__

themes = dict(
  USA=ThemeData(infile='fe_2007_us_state/fe_2007_us_state.shp',
                oufile='cont_us_state.ply',
                nameid='STUSPS',
                excluded_ids=set('HI AK VI GU PR AS MP'.split()),
                ),
  ZIPCA=ThemeData(infile='ca/zt06_d00.shp',
                  oufile='cazip.ply',
                  nameid='ZTCA',
                  valid=str.isdigit,
                  ),
  )

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

def usage():
  logging.error('Usage: %s theme [minzoom [maxzoom]]', sys.argv[0])
  logging.error('Known themes are: %s', ' '.join(sorted(themes)))
  pikfiles = glob.glob('gae/*_dict.pik')
  logging.error('PIK indices are known for: %s',
      ' '.join(sorted(x[4:-9] for x in pikfiles)))
  sys.exit(1)

def study_args():
  nargs = len(sys.argv)
  if nargs < 2 or nargs > 4:
    logging.error('Invalid number of arguments (%d)', nargs-1)
    usage()
  theme = sys.argv[1]
  if not theme.isupper():
    logging.error('Invalid theme %r, not all-uppercase', theme)
    usage()
  if theme not in themes:
    logging.error('Unknown theme %r', theme)
    usage()
  try:
    f = open(PIK_FORMAT % theme)
  except IOError:
    f = None
  if f is None:
    index_dict = None
  else:
    try:
      index_dict = cPickle.load(f)
      f.close()
    except Exception, e:
      logging.error('Invalid PIK index for %r: %s', theme, e)
      index_dict = None
  if nargs > 2:
    try:
      minzoom = int(sys.argv[2])
    except ValueError:
      logging.error('Invalid integer for minzoom: %r', sys.argv[2])
      usage()
    try:
      maxzoom = int(sys.argv[3]) if nargs == 4 else minzoom
    except ValueError:
      logging.error('Invalid integer for maxzoom: %r', sys.argv[3])
      usage()
    if not (0<minzoom<=maxzoom<18):
      logging.error('Invalid min/max zoom: not 0<%s<=%s<18', minzoom, maxzoom)
      usage()
    logging.info('Theme=%s, zooms=%s to %s', theme, minzoom, maxzoom)
    return theme, minzoom, maxzoom, index_dict or dict()
  if index_dict is None:
    logging.error('Must give zoom for theme %r (no PIK)', theme)
    usage()
  existing_zoom = max(int(zxy.split('_')[0]) for zxy in index_dict)
  logging.info('Theme=%s, next zoom: %s', theme, existing_zoom+1)
  return theme, existing_zoom+1, existing_zoom+1, index_dict

def main():
  """ Perform the script's tasks. """
  shp2polys.setlogging()
  theme, minzoom, maxzoom, index_dict = study_args()
  name_format = '/tmp/tile_%s_%%s_%%s_%%s.png' % theme
  m = tile.GlobalMercator()
  meta = themes[theme]

  # ensure the Polyfile we need is around
  if not os.path.isfile(meta.oufile):
    logging.info('Building polyfile %r', meta.oufile)
    c = shp2polys.Converter(**meta)
    c.doit()

  # make a Reader for the polyfile, and do all required tiles
  r = shp2polys.PolyReader(infile=meta.oufile)
  for zoom in range(minzoom, maxzoom+1):
    do_all_tiles(m, r, zoom, name_format)


def do_all_tiles(m, r, zoom, name_format):
    bb = r.get_tiles_ranges(zoom)
    do_tiles(m, r, zoom, name_format, bb)


MAX_SIZE = 1000 * 1000 * 1000

def _dodivide(bb, dd, minind):
  midbb = bb[minind] + dd // 2
  if midbb >= bb[minind+2]:
    logging.error("Can't split %s, stopping", bb)
    raise ValueError
  bbs = list(bb), list(bb)
  bbs[0][minind+2] = midbb
  bbs[1][minind] = midbb+1
  return bbs

def do_tiles(m, r, zoom, name_format, bb):
  dx = bb[2] - bb[0]
  dy = bb[3] - bb[1]
  size = 256*(dx+1), 256*(dy+1)
  logging.info('zoom %s: tiles %s, size %s', zoom, bb, size)
  if size[0]*size[1] > MAX_SIZE:
    logging.info('splitting along %s', 'XY'[dx<dy])
    bbs = _dodivide(bb, max(dx, dy), int(dx<dy))
    for abb in bbs: do_tiles(m, r, zoom, name_format, abb)
    return
  logging.info('Computing %d tiles', (dx+1)*(dy+1))

  white = 0
  im = Image.new('P', size, white)
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

