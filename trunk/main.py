#!/usr/bin/env python
import cgi
import wsgiref.handlers
from google.appengine.ext import webapp
from google.appengine.api import memcache

import dopngtile
import models

def get_tile(name, x, y, z, maker):
  data = memcache.get(name)
  if data is not None:
    return data
  else:
    query = models.Tile.gql("WHERE name = :1", name)
    tiles = query.fetch(1)
    if len(tiles) == 1:
      data = tiles[0].data
    else:
      data = maker(x, y, z, None)
      tile = models.Tile(name=name, data=data)
      tile.put()
    memcache.add(name, data)
    return data

def queryget(query, name):
  x = query.get(name)
  return x[0] if x else None

class TileHandler(webapp.RequestHandler):

  def get(self):
    query = cgi.parse_qs(self.request.query_string)
    png = queryget(query, 'png')
    x, y, z = (int(queryget(query, n) or -1) for n in 'xyz')
    # generate tile on-the-fly
    if png=='USA':
      maker = dopngtile.usatile
    elif png=='ZIP':
      maker = dopngtile.onetile
    else:
      # unknown PNG type requested
      self.response.set_status(404, "PNG type %r not found" % png)
      return
    name = 'tile_%s_%s_%s_%s' % (png, x, y, z)
    data = get_tile(name, x, y, z, maker)
    if data is None:
      self.response.set_status(500, "Can't make PNG for %r" % name)
      return
    self.response.headers.add_header('Content-Type', 'image/png')
    self.response.out.write(data)

def main():
  application = webapp.WSGIApplication([('/tile', TileHandler)],
                                       debug=True)
  wsgiref.handlers.CGIHandler().run(application)

if __name__ == '__main__':
  main()
