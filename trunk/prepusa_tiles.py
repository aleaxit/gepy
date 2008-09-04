""" Prepare tiles for US state boundaries and place them in a SQLite DB for
    future upload.
"""
import logging
import sqlite3

from PIL import Image, ImageDraw

import shp2polys
import tile

def main():
  shp2polys.setlogging()

  conn = sqlite3.connect('usatiles')
  conn.text_factory = str
  c = conn.cursor()
  # Create table (if not already there)
  c.execute('''CREATE TABLE IF NOT EXISTS tiles
               (name TEXT PRIMARY KEY, 
                data BLOB,
                uploaded_to TEXT)
            ''')
  conn.commit()
  
  name_format = 'tile_USA_%s_%s_%s'
  MIN_ZOOM = 3
  MAX_ZOOM = 3
  r = shp2polys.PolyReader()
  bb = r.get_tiles_ranges()
  logging.info('zoom %s: tiles %s', r.zoom, bb)

main()

