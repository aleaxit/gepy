import httplib
import logging
import Queue
import socket
import threading

import dopngtile
import shpextract

upq = Queue.Queue()
host = 'localhost'
port = 8080
thread_pool_size = 3
thread_pool = []

def start_thread_pool():
  for i in range(thread_pool_size):
    t = threading.Thread(target=uploading_thread)
    t.start()
    thread_pool.append(t)

def finis_thread_pool():
  for t in thread_pool:
    upq.put((None,None))
  for t in thread_pool:
    t.join()

def uploading_thread():
  try: conn = httplib.HTTPConnection(host, port, strict=True)
  except socket.error, e:
    logging.error("Cannot connect: %s", e)
    return

  while True:
    name, data = upq.get()
    if name is None:
      logging.info('Terminating thread.')
      return
    path = 'http://%s:%s/tile?name=%s' % (host, port, name)
    logging.info('Uploading %s', path)
    try: conn.request('POST', path, data)
    except socket.error, e:
      logging.error("Cannot POST: %s", e)
      return
    rl = conn.getresponse()
    logging.info('POST to %s gave: %s %r', path, rl.status, rl.reason)

def upload(name, data):
  logging.info('Queueing %r (%d bytes) for upload', name, len(data))
  upq.put((name, data))

def main():
  logging.basicConfig(format='%(levelname)s: %(message)s')
  logger = logging.getLogger()
  logger.setLevel(logging.DEBUG)

  start_thread_pool()

  SW = (15.19939,-126.03516)
  NE = (50.90303,-64.51172)
  name_format = 'tile_USA_%s_%s_%s'
 
  dopngtile.s = s = shpextract.Shp('fe_2007_us_state/fe_2007_us_state.shp',
                       id_field_name='STUSPS', id_check=lambda x: True)
  logging.info('USA bbox: %s', shpextract.showbb(s.overall_bbox))
  usabb = SW[0], SW[1], NE[0], NE[1]
  for zoom in range(3, 4):
    n = 0
    for gx, gy, x, y, z in dopngtile.tile_coords_generator(
        zoom, *usabb):
      # logging.info('z=%s: tile(%s,%s)=google(%s,%s)', z, x, y, gx, gy)
      n += 1
    print 'Zoom %d: up to %d tiles' % (zoom, n)
    n = 0
    for gx, gy, x, y, z in dopngtile.tile_coords_generator(
        zoom, *usabb):
      name = name_format % (gx, gy, z)
      try:
        data = dopngtile.do_tile(x, y, z)
      except StopIteration:
        logging.info('Skipping %r, out of box', name)
        continue
      n += 1
      upload(name, data)
    logging.info('%d done (%d still in upload queue)', n, upq.qsize())

  finis_thread_pool()

main()

