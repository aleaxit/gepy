""" Prepare tiles for US state boundaries and place them in a SQLite DB for
    future upload.
"""
import logging
import os
import sqlite3
import sys

from PIL import Image, ImageDraw, ImageFont, ImagePath

import shp2polys
import tile

def s(aray):
  res = []
  for x in aray: res.append('%.2f' % x)
  return '[%s]' % ','.join(res)

def main():
  shp2polys.setlogging()

  conn = sqlite3.connect('usatiles')
  conn.text_factory = str
  c = conn.cursor()
  # Create table (if not already there)
  c.execute('''CREATE TABLE IF NOT EXISTS tiles (name TEXT PRIMARY KEY, 
                                                 data BLOB, uploaded_to TEXT)
            ''')
  conn.commit()
  
  name_format = 'tile_USA_%s_%s_%s'
  MIN_ZOOM = 3; MAX_ZOOM = 3
  m = tile.GlobalMercator()

  for zoom in range(MIN_ZOOM, MAX_ZOOM+1):
    r = shp2polys.PolyReader(zoom)
    bb = r.get_tiles_ranges()
    size = 256*(bb[2]-bb[0]+1), 256*(bb[3]-bb[1]+1)
    logging.info('zoom %s: tiles %s, size %s', r.zoom, bb, size)
    palette = [255]*3 + [255, 0, 0] + [0, 255, 0]
    white = 0
    red = 1
    green = 2
    im = Image.new('P', size, white)
    im.putpalette(palette)

    matrix = m.getMetersToPixelsXform(zoom, bb)
    font = ImageFont.truetype('/Library/Fonts/ChalkboardBold.ttf', 24)
    draw = ImageDraw.Draw(im)
    for name, bbox, starts, lengths, meters in r:
      # print name, s(starts), s(lengths), len(meters), s(bbox)
      p = ImagePath.Path(bbox)
      # print 'bef:', s(p.tolist(1))
      p.transform(matrix)
      # print 'aft:', s(p.tolist(1))
      tsz = draw.textsize(name, font=font)
      tdc = [(p[1][i]+p[0][i]-tsz[i])/2.0 for i in (0,1)]
      # logging.info('txt %s: %s %s %s', name, tsz, s(p.tolist(1)), s(tdc))
      draw.text(tdc, name, fill=green, font=font)
      for s, l in zip(starts, lengths):
        p = ImagePath.Path(meters[s:s+l])
        p.transform(matrix)
        draw.polygon(p, outline=red)
    del draw 
    # sys.exit(0)

    im.save("USA.PNG", transparency=white)
    os.system("open USA.PNG")

main()

