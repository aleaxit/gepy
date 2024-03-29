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
  """ Put Tile with given name and data to storage and cache.

  Args:
    name: str name of the tile
    data: PNG binary blob of data for the tile
  Returns:
    data
  Side effects:
    saves the tile to Storage (if there isn't too much contention there);
    also sets the name/data correspondence in the cache.
  """
  tile = models.Tile(name=name, data=data)
  try:
    tile.put()
  except db.TransactionFailedError, e:
    logging.info('%r not stored yet, "%s"', name, e)
  else:
    logging.info('%r just made (%d)', name, len(data))
  memcache.set(name, data)
  return data


# a registry that keeps a Tiler instance per theme of interest
tiler_by_theme_registry = dict()

def tiler_by_theme(theme):
  """ Returns Tiler instance for the given theme. """
  try: return tiler_by_theme_registry[theme]
  except KeyError:
    tiler = tiler_by_theme_registry[theme] = Tiler(theme)
    return tiler

class Tiler(object):
  """ Provide all the tile-management needed for one theme. """

  def __init__(self, theme):
    """ Record the theme and read the tile-to-zipnumber mapping.

    Args:
      theme: the str name of the theme (<theme>_dict.pik must exist!)
    """
    self.theme = theme
    self.prefix = 'tile_' + theme + '_'
    pickled_dict_name = '%s_dict.pik' % theme
    with open(pickled_dict_name, 'rb') as f:
      self.tile_to_zip = pickle.load(f)
    self.zips = dict()

  def get_tile(self, x, y, z):
    """ Get from cache, store, or zipfile, the PNG data for a tile.

    Args:
      x, y, z: Google Maps coordinates of the tile
    Returns:
      PNG data for the tile (or a place-holder tile, if no tile is found)
    """
    # form the z_x_y key, and the corresponding PNG filename
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
      memcache.set(name, data)
      return data
    # then try to find a zipfile
    zipnum = self.tile_to_zip.get(z_x_y)
    if zipnum is None:
      # no such tile, make one up!
      with open('tile_crosshairs.png') as f:
        data = f.read()
    else:
      try: thezip = self.zips[zipnum]
      except KeyError:
        zipname = '%s_%s.zip' % (self.theme, zipnum)
        thezip = self.zips[zipnum] = zipfile.ZipFile(zipname, 'r')
      data = thezip.read(name)
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


def main():
  application = webapp.WSGIApplication([('/tile', TileHandler)],
                                       debug=True)
  wsgiref.handlers.CGIHandler().run(application)

if __name__ == '__main__':
  main()
