#!/usr/bin/env python
from __future__ import with_statement

import cgi
import logging
import wsgiref.handlers
from google.appengine.ext import webapp
from google.appengine.api import memcache

import dopngtile
import models

def get_tile(name, x, y, z, maker=None):
  """ Get from cache or store, or make and put in store and cache, a tile.

  Args:
    name: name of the tile (unique key)
    x, y, z: Google Maps coordinates of the tile
    maker: function that generates and returns the tile (or None)
  Returns:
    PNG data for the tile (None if absent and maker was or returned None)
  """
  # first try the cache
  data = memcache.get(name)
  if data is not None:
    logging.info('%r in cache (%d)', name, len(data))
    return data
  else:
    # then try the datastore
    query = models.Tile.gql("WHERE name = :1", name)
    tiles = query.fetch(1)
    if len(tiles) == 1:
      data = tiles[0].data
      logging.info('%r in store (%d)', name, len(data))
    else:
      # nope, generate the tile and put it in the datastore
      if maker is None:
        data = None
        logging.info('%r not there', name)
      else:
        data = maker(x, y, z, None)
        tile = models.Tile(name=name, data=data)
        tile.put()
        logging.info('%r just made (%d)', name, len(data))
    # tile wasn't in cache, put it there
    memcache.add(name, data)
    return data

def queryget(query, name):
  """ Utility function to get a variable's single value from a CGI query dict

  Args:
    query: dict of lists as built from cgi.parse_query
    name: str name of variable sought
  Returns:
    str value of variable, or None if not present
  """
  x = query.get(name)
  return x[0] if x else None

class TileHandler(webapp.RequestHandler):
  "Serve PNG data (generated on the fly, or cached) for Google Maps tiles."

  def get(self):
    """ Serve the requested tile (generate if it needed) """
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
    # temporarily inhibit maker functionality
    maker = None
    name = 'tile_%s_%s_%s_%s' % (png, x, y, z)
    data = get_tile(name, x, y, z, maker)
    if data is None:
      # self.response.set_status(500, "Can't make PNG for %r" % name)
      with open('tile_crosshairs.png') as f: data = f.read()
      # return
    self.response.headers['Content-Type'] = 'image/png'
    self.response.out.write(data)

  def post(self):
    """ Get a tile's name and data from the client, put in the datastore """
    query = cgi.parse_qs(self.request.query_string)
    name = queryget(query, 'name')
    if name is None:
      self.response.set_status(400, "Must pass ?name= in query!")
      return
    # sanity check: tile wasn't already there
    data = get_tile(name, None, None, None)
    if data is not None:
      self.response.set_status(401, "Tile exists for name=%r" % name)
      return
    data = self.request.body
    tile = models.Tile(name=name, data=data)
    tile.put() 
    self.response.out.write("%r created successfully." % name)

def main():
  application = webapp.WSGIApplication([('/tile', TileHandler)],
                                       debug=True)
  wsgiref.handlers.CGIHandler().run(application)

if __name__ == '__main__':
  main()
