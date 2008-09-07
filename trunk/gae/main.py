#!/usr/bin/env python
from __future__ import with_statement
import cgi
import logging
import pickle
import wsgiref.handlers
import zipfile
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.api import memcache

import models

def persist_tile(name, data):
  tile = models.Tile(name=name, data=data)
  try:
    tile.put()
  except db.TransactionFailedError, e:
    logging.info('%r not stored yet, "%s"', name, e)
  else:
    logging.info('%r just made (%d)', name, len(data))
  memcache.put(name, data)
  return data

tiler_by_theme_registry = dict()
def tiler_by_theme(theme):
  try: return tiler_by_theme_registry[theme]
  except KeyError:
    tiler = tiler_by_theme_registry[theme] = Tiler(theme)
    return tiler

class Tiler(object):
  """ Provide all the tile-management needed for one theme. """
  def __init__(self, theme):
    self.theme = theme
    self.prefix = 'tile_' + theme + '_'
    pickled_dict_name = '%s_dict.pik' % theme
    self.tile_to_zip = pickle.load(pickled_dict_name)
    self.zips = dict()

  def get_tile(self, x, y, z):
    """ Get from cache, store, or zipfile, the PNG data for a tile.

    Args:
      x, y, z: Google Maps coordinates of the tile
    Returns:
      PNG data for the tile (or a place-holder tile, if no tile is found)
    """
    z_x_y = '%s_%s_%s' % (z, x, y)
    name = self.prefix + z_x_y + '.png'
    # first try the cache
    data = memcache.get(name)
    if data is not None:
      logging.info('%r in cache (%d)', name, len(data))
      return data
    # then try the datastore
    query = models.Tile.gql("WHERE name = :1", name)
    tiles = query.fetch(1)
    if len(tiles) == 1:
      data = tiles[0].data
      logging.info('%r in store (%d)', name, len(data))
      memcache.put(name, data)
      return data
    # then try to find a zipfile
    zipnum = self.tile_to_zip.get(z_x_y)
    if zipnum is None:
      # no such tile, make one up!
      with open('tile_crosshairs.png') as f:
        data = f.read()
    else:
      try: zipfile = self.zips[zipnum]
      except KeyError:
        zipname = '%s_%s.zip' % (self.theme, zipnum)
        zipfile = self.zips[zipnum] = zipfile.ZipFile(zipname, 'r')
      data = zipfile.read(name)
    return persist_tile(name, data)


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
  "Serve PNG data (cached, stored or from a zipfile) for Google Maps tiles."

  def get(self):
    """ Serve the requested tile (generate if it needed) """
    query = cgi.parse_qs(self.request.query_string)
    theme = queryget(query, 'png')
    x, y, z = (int(queryget(query, n) or -1) for n in 'xyz')
    # generate/produce tile on-the-fly if needed
    data = tiler_by_theme(theme).get_tile(x, y, z)
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
