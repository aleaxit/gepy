import httplib
import logging
import Queue
import socket
import time
import threading

import dopngtile
import shpextract

upq = Queue.Queue()
host = 'localhost'
port = 8080
host = 'gepy.appspot.com'
port = 80
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
  logging.info('%d left', upq.qsize)
  for t in thread_pool:
    t.join()
    logging.info('%d left', upq.qsize)


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
    logging.debug('Uploading %s', path)

    while True:
      retries = 0
      while retries < 100:
        try:
          try: conn.request('POST', path, data)
          except socket.error, e:
            logging.error("Cannot POST: %s", e)
            return
        except httplib.CannotSendRequest:
          time.sleep(1.0)
          retries += 1
        else: break
      if retries > 100:
        logging.error('gonna retry to send %s', path)
        conn = httplib.HTTPConnection(host, port, strict=True)

    retries = 0
    while retries < 100:
      try: rl = conn.getresponse()
      except httplib.ResponseNotReady:
        time.sleep(1.0)
        retries += 1
      else: break
    if retries > 100:
      logging.error('gave up on response on %s', path)
      conn = httplib.HTTPConnection(host, port, strict=True)
    else:
      logging.debug('%s: %s %r', path, rl.status, rl.reason)


def upload(name, data):
  logging.debug('Queueing %r (%d bytes) for upload', name, len(data))
  upq.put((name, data))

def main():
  logging.basicConfig(format='%(levelname)s: %(message)s')
  logger = logging.getLogger()
  logger.setLevel(logging.INFO)

  start_thread_pool()

  SW = (13.19939,-128.03516)
  NE = (52.90303,-62.51172)
  name_format = 'tile_USA_%s_%s_%s'
 
  dopngtile.s = s = shpextract.Shp('fe_2007_us_state/fe_2007_us_state.shp',
                       id_field_name='STUSPS', id_check=lambda x: True)
  logging.info('USA bbox: %s', shpextract.showbb(s.overall_bbox))
  usabb = SW[0], SW[1], NE[0], NE[1]
  for zoom in range(3, 8):
    n = 0
    for gx, gy, x, y, z in dopngtile.tile_coords_generator(
        zoom, *usabb):
      # logging.info('z=%s: tile(%s,%s)=google(%s,%s)', z, x, y, gx, gy)
      n += 1
    logging.info('Zoom %d: up to %d tiles', zoom, n)
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
    logging.info('%d files done for zoom %d (%d still in upload queue)',
        n, zoom, upq.qsize())

  finis_thread_pool()

main()
