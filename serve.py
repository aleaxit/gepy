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

def do_cgi(form):
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

