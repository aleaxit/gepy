#!/usr/bin/python
from __future__ import with_statement
""" A script to locally serve the current directory AND also serve CGI.

This convenience script, when invoked from the command line, starts a
CGIHTTPServer in the current directory on http://localhost:8000/ and opens a
web browser on a specified HTML file there.  Usage: ./serve.py port file --
you can omit file or both (to use index.html and port 8000).

When invoked via a CGI url, it serves CGI as requested.
"""
import cgi
import CGIHTTPServer
import contextlib
import socket
import sys
import threading
import webbrowser

import pypng

# ensure binary stdout on Windows (it's already guaranteed elsewhere)
try: import msvcrt, os
except ImportError: pass
else: msvcrt.setmode(1, os.OS_BINARY)

def square(p, mi, ma, color, sq=(0,1,3,2,0)):
  """ Draw a square (mi,mi)->(mi,ma)->(ma,ma)->(ma,mi)->(mi,mi) on a PNG.
  """
  def pt(j,c=(mi,ma)): return c[j&1], c[j>1]
  def ps(i, color=color, sq=sq): p.draw_line(pt(sq[i]), pt(sq[i+1]), color)
  for i in range(4): ps(i)

def do_cgi(form, tmpdir='/tmp'):
  """ Utility CGI service for all kinds of useful doodads. So far...:
  - if a png=foo is requested, makes a "foo png" on the fly
    (the idea is to show all other parameters on log/console too!)
    (currently also tries caching it on disk in /tmp)
  - that's it (no other uses yet)
  If none of the useful doodads is requested, serves a text/plain "hello world".
  """
  if form.has_key('png'):
    k = tuple(form.getfirst(k) for k in ('png','x','y','z'))
    fn = '%s/srv_%s_%s_%s_%s.png' % ((tmpdir,)+k)
    try:
      with open(fn, 'rb') as f: data = f.read()
    except IOError:
      p = pypng.PNG()
      green = p.get_color(0, 255, 0)
      square(p, 1, 254, green)
      red = p.get_color(255, 0, 0)
      square(p, 3, 252, red)
      data = 'Content-Type: image/png\n\n' + p.dump()
      with open(fn, 'wb') as f: f.write(data)
    sys.stdout.write(data)
  else:
    print 'Content-Type: text/plain'
    print
    print 'hello world!'

def do_browse():
  try: page = sys.argv[2]
  except IndexError: page = 'index.html'
  try: port = sys.argv[1]
  except IndexError: port = '8000'
  url = 'http://localhost:%s/%s' % (port, page)
  print 'Browsing', url
  # wait for server to start
  while True:
    with contextlib.closing(
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
      try: s.connect(('localhost', int(port)))
      except socket.error: time.sleep(0.5)
      else: break
  # server now working, let's browse!
  webbrowser.open(url)

def main():
  if 'cgi' in sys.argv[0]:
    form = cgi.FieldStorage()
    do_cgi(form)
    return
  t = threading.Thread(target=do_browse)
  t.setDaemon(True)
  t.start()
  print 'Starting server, end w/Control-C'
  try: CGIHTTPServer.test()
  except KeyboardInterrupt:
    print 'Got a Control-C, bye!'

if __name__ == '__main__':
  main()

