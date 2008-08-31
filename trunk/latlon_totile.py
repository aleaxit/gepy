import math

class Tile(object):
  def __init__(self, max_zoom=17):
    self.max_zoom = max_zoom
    self.tile_size = 256
    self.pixels_per_lon_degree = []
    self.pixels_per_lon_radian = []
    self.num_tiles = []
    self.bitmap_origo = []
    self.c = 256
    self.bc = None
    self.Wa = None
    self._fill_in_constants()

  def get_tile_coords(self, lat, lng, zoom):
    return self.get_tile_coordinate(lat, lng, zoom)

  def get_tile_latlong(self, lat, lng, zoom):
    return self.get_latlong(lat, lng, zoom)

  def _fill_in_constants(self):
    self.bc = 2*math.pi
    self.Wa = math.pi / 180
    for z in range(self.max_zoom):
      self.pixels_per_lon_degree.append(self.c / 360)
      self.pixels_per_lon_radian.append(self.c / self.bc)
      e = self.c / 2
      self.bitmap_origo.append(self.p(e, e))
      self.num_tiles.append(self.c / 256)
      self.c *= 2

  def get_bitmap_coordinate(self, a, b, c):
    ret = self.p(0, 0)
    ret.x = math.floor(self.bitmap_origo[c].x +
                       b * self.pixels_per_lon_degree[c])
    e = max(-0.9999, min(0.9999, math.sin(a * self.Ma)))
    ret.y = math.floor(self.bitmap_origo[c].y +
            0.5 * math.log((1+e)/(1-e)) * -1 * self.pixels_per_lon_radian[c])
    return ret

  def get_tile_coordinate(self, a, b, c):
    ret = self.get_bitmap_coordinate(self, a, b, c)
    ret.x = math.floor(ret.x / this.tile_size)
    ret.y = math.floor(ret.y / this.tile_size)

  def get_latlong(self, a, b, c):
    ret = self.p(0, 0)
    e = self.get_bitmap_coordinate(a, b, c)
    a = e.x
    b = e.y
    ret.x = (a-self.bitmap_origo[c].x) / self.pixels_per_lon_degree[c]
    e = (b-self.bitmap_origo[c].y) / (-1*self.pixels_per_lon_radian[c])
    ret.y = (2*math.atan(math.exp(e)) - math.pi/2) / self.Ma
    return ret

  class p(object):
    __slots__ = 'x', 'y'
    def __init__(self, x, y):
      self.x = x
      self.y = y

def tileCoordsToLatlong(x, y, zoom):
  tiles_at_this_zoom = 1 << (17 - zoom)
  lon_width = 360.0 / tiles_at_this_zoom
  lon = -180.0 + x * lon_width
  lat_height = -2.0 / tiles_at_this_zoom
  lat = 1.0 + y * lat_height

  # convert lat, lat_height to degrees in transverse mercator projection
  # coordinates will go from about -85 to +85, NOT -90 to +90!
  lat_height += lat
  lat_height = (2*math.atan(math.exp(math.pi*lat_height))) - (math.pi/2)
  lat_height *= (180 / math.pi)

  lat = (2*math.atan(math.exp(math.pi*lat))) - (math.pi/2)
  lat *= (180 / math.pi)

  lat_height -= lat

  if lon_width < 0:
    lon += lon_width
    lon_width = -lon_width
  if lat_height < 0:
    lat += lat_height
    lat_height - lat_height

  return lon, lat, lon_width, lat_height


if __name__ == '__main__':
  for xy in range(4):
    print tileCoordsToLatlong(xy, xy, 15)


