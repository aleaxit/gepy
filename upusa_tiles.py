""" Upload tiles for US state boundaries from a SQLite DB.
"""
import httplib
import logging
import Queue
import socket
import sqlite3
import sys
import time
import threading

upq = Queue.Queue()
req = Queue.Queue()
host = 'localhost'
port = 8080

thread_pool_size = 4
thread_pool = []

def start_thread_pool():
  for i in range(thread_pool_size):
    t = threading.Thread(target=uploading_thread)
    t.start()
    thread_pool.append(t)

def finis_thread_pool():
  for t in thread_pool:
    upq.put((None,None))
  logging.info('%d left', upq.qsize())
  for t in thread_pool:
    t.join()
    logging.info('%d left', upq.qsize())


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

    outret = 0
    while outret < 10:
      retries = 0
      while retries < 10:
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
        outret += 1
    if outret >= 10:
      logging.error('gave up on posting %s', path)
      conn = httplib.HTTPConnection(host, port, strict=True)
      continue

    retries = 0
    while retries < 100:
      try: rl = conn.getresponse()
      except httplib.ResponseNotReady:
        time.sleep(1.0)
        retries += 1
      else:
        req.put(name)
        logging.debug('%s: %s %r', path, rl.status, rl.reason)
        break
    if retries > 100:
      logging.error('gave up on response on %s', path)
      conn = httplib.HTTPConnection(host, port, strict=True)


def upload(name, data):
  logging.debug('Queueing %r (%d bytes) for upload', name, len(data))
  upq.put((name, data))

def update_uploads(conn, c, hostport):
  n = req.qsize()
  while req.qsize():
    name = req.get()
    c.execute('SELECT uploaded_to FROM tiles WHERE name=?', (name,))
    c.execute('UPDATE tiles SET uploaded_to=? WHERE name=?',
        (uploaded_to+' '+hostport, name))
    conn.commit()
  logging.info('Uploaded %d files', n)

def main():
  global host, port

  logging.basicConfig(format='%(levelname)s: %(message)s')
  logger = logging.getLogger()
  logger.setLevel(logging.DEBUG)

  if len(sys.argv) > 3:
    logging.error('Usage: %s [host [port]]', sys.argv[0])
    sys.exit(1)
  if len(sys.argv) > 1:
    host = sys.argv[1]
    if sys.argv == 2:
      port = 80
  if len(sys.argv) > 2:
    port = int(sys.argv[2])

  hostport = '%s:%s' % (host, port)

  conn = sqlite3.connect('usatiles')
  conn.text_factory = str
  c = conn.cursor()

  start_thread_pool()

  c.execute('SELECT * FROM tiles')
  for name, data, uploaded_to in c.fetchall():
    if hostport in uploaded_to:
      logging.info('Skip %r, already uploaded to %r', name, hostport)
      continue
    upload(name, data)

  finis_thread_pool()

  update_uploads(conn, c, hostport)


main()

