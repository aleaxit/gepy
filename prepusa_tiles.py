""" Prepare tiles for US state boundaries and place them in a SQLite DB for
    future upload.
"""
import logging
import sqlite3

import dopngtile
import shpextract

def upload(name, data):
  logging.debug('Queueing %r (%d bytes) for upload', name, len(data))
  upq.put((name, data))

def main():
  logging.basicConfig(format='%(levelname)s: %(message)s')
  logger = logging.getLogger()
  logger.setLevel(logging.INFO)
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
  
  SW = (13.19939,-128.03516)
  NE = (52.90303,-62.51172)
  name_format = 'tile_USA_%s_%s_%s'
  MIN_ZOOM = 3
  MAX_ZOOM = 5
 
  dopngtile.s = s = shpextract.Shp('fe_2007_us_state/fe_2007_us_state.shp',
                       id_field_name='STUSPS', id_check=lambda x: True)
  logging.info('USA bbox: %s', shpextract.showbb(s.overall_bbox))
  usabb = SW[0], SW[1], NE[0], NE[1]
  for zoom in range(MIN_ZOOM, MAX_ZOOM+1):
    n = 0
    for gx, gy, x, y, z in dopngtile.tile_coords_generator(
        zoom, *usabb):
      # logging.info('z=%s: tile(%s,%s)=google(%s,%s)', z, x, y, gx, gy)
      n += 1
    logging.info('Zoom %d: up to %d tiles', zoom, n)
    newones = oldones = 0
    for gx, gy, x, y, z in dopngtile.tile_coords_generator(
        zoom, *usabb):
      name = name_format % (gx, gy, z)
      c.execute('SELECT * FROM tiles WHERE name=?', (name,))
      if c.fetchone():
        logging.info('Skipping %r, already in DB', name)
        oldones += 1
        continue
      try:
        data = dopngtile.do_tile(x, y, z)
        logging.info('Done %r, was not in DB', name)
      except StopIteration:
        logging.info('Skipping %r, out of box', name)
        continue
      n += 1
      c.execute('INSERT INTO tiles VALUES (:1, :2, :3)', (name, data, ''))
      conn.commit()
      newones += 1
    logging.info('%d files done for zoom %d (%d new, %d were already there)',
        newones+oldones, zoom, newones, oldones)


main()

