#!/usr/bin/env python
from __future__ import with_statement

import cgi
import logging
import wsgiref.handlers
import zipfile
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.api import memcache

import models

zipnames = dict(USA='tiles', ZIPCA='tiles_zipca')
thezips = dict()
def fromzip(png, name, x, y, z, unused_lastarg):
  thezip = thezips.get(png)
  zn = zipnames.get(png)
  if thezip is None:
    if zn is None: return None
    thezip = thezips[png] = zipfile.ZipFile('%s.zip'%zn, 'r')
  name += '.png'
  logging.info('From zip: %s in %s', name, zn)
  try:
    return thezip.read(name)
  except KeyError:
    return None

def persist_tile(name, data):
  tile = models.Tile(name=name, data=data)
  try:
    tile.put()
  except db.TransactionFailedError, e:
    logging.info('%r not stored yet, "%s"', name, e)
  else:
    logging.info('%r just made (%d)', name, len(data))

def get_tile(png, name, x, y, z, maker=None):
  """ Get from cache or store, or make and put in store and cache, a tile.

  Args:
    png: name of the PNG family (USA, ZIPCA, &c)
    name: name of the tile (unique key)
    x, y, z: Google Maps coordinates of the tile
    maker: function that generates and returns the tile (or None)
           when called with args: png, name, x, y, z, None
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
      else:
        data = maker(png, name, x, y, z, None)
      if data is None:
        logging.info('%r not there', name)
        with open('tile_crosshairs.png') as f:
          data = f.read()
      persist_tile(name, data)
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
    # generate/produce tile on-the-fly if needed
    if png=='USA' or png=='ZIPCA':
      maker = fromzip
    else:
      # unknown PNG type requested
      self.response.set_status(404, "PNG type %r not found" % png)
      return
    # temporarily inhibit maker functionality
    name = 'tile_%s_%s_%s_%s' % (png, z, x, y)
    data = get_tile(png, name, x, y, z, maker)
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
