import logging
import Queue
import threading

import dopngtile
import shpextract

upq = Queue.Queue()

def upload(name, data):
  logging.info('Queueing %r (%d bytes) for upload', name, len(data))
  upq.put((name, data))

def main():
  logging.basicConfig(format='%(levelname)s: %(message)s')
  logger = logging.getLogger()
  logger.setLevel(logging.DEBUG)


  SW = (15.19939,-126.03516)
  NE = (50.90303,-64.51172)
  name_format = 'tile_USA_%s_%s_%s'
 
  dopngtile.s = s = shpextract.Shp('fe_2007_us_state/fe_2007_us_state.shp',
                       id_field_name='STUSPS', id_check=lambda x: True)
  logging.info('USA bbox: %s', shpextract.showbb(s.overall_bbox))
  for zoom in range(3, 4):
    n = 0
    for gx, gy, x, y, z in dopngtile.tile_coords_generator(
        zoom, -126, 16, -65, 50):
      n += 1
    print 'Zoom %d: up to %d tiles' % (zoom, n)
    n = 0
    for gx, gy, x, y, z in dopngtile.tile_coords_generator(
        zoom, -126, 16, -65, 50):
      name = name_format % (gx, gy, z)
      try:
        data = dopngtile.do_tile(x, y, z)
      except StopIteration:
        logging.info('Skipping %r, out of box', name)
        continue
      n += 1
      upload(name, data)
    logging.info('%d done (%d still in upload queue)', n, upq.qsize())
  upq.put((None, None))

main()

