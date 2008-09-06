#!/usr/bin/env python
# inspired from: http://www.klokan.cz/projects/gdal2tiles/
# original by: klokan@klokan.cz

""" tile.py: support global map tiles as defined in Tile Map Service profiles
Offers class: GlobalMercator (based on EPSG:900913 = EPSG:3785)
  compatible with: Google Maps, Yahoo Maps, Microsoft Maps
See also:
  http://wiki.osgeo.org/wiki/Tile_Map_Service_Specification
  http://wiki.osgeo.org/wiki/WMS_Tiling_Client_Recommendation
  http://msdn.microsoft.com/en-us/library/bb259689.aspx
  http://code.google.com/apis/maps/documentation/overlays.html#\
         Google_Maps_Coordinates
"""
import math

class GlobalMercator(object):
  """ TMS Global Mercator Profile

  Functions necessary for generation of tiles in Spherical Mercator projection,
  As per: EPSG:900913 (EPSG:gOOglE, Google Maps Global Mercator),
  EPSG:3785, OSGEO:41001.

  Such tiles are compatible with Google Maps, Microsoft Virtual Earth, Yahoo
  Maps, UK Ordnance Survey OpenSpace API, ...  and you can overlay them on top
  of base maps of those web mapping applications.

  Pixel and tile coordinates are in TMS notation (origin [0,0] in bottom-left).

  What coordinate conversions do we need for TMS Global Mercator tiles::
       LatLon      <->       Meters      <->     Pixels    <->       Tile
   WGS84 coordinates   Spherical Mercator  Pixels in pyramid  Tiles in pyramid
       lat/lon            XY in metres     XY pixels Z zoom      XYZ from TMS
      EPSG:4326           EPSG:900913
       .----.              ---------               --                TMS
      /      \     <->     |       |     <->     /----/    <->      Google
      \      /             |       |           /--------/          QuadTree
       -----               ---------         /------------/
     KML, public         WebMapService         Web Clients      TileMapService

  Coordinate extent of Earth in EPSG:900913:
    [-20037508.342789244, -20037508.342789244,
      20037508.342789244, 20037508.342789244]
    The constant 20037508.342789244 comes from the circumference of the Earth
    in meters, which is 40 thousand kilometers, the coordinate origin is in the
    middle of extent.
    In fact you can calculate the constant as: 2 * math.pi * 6378137 / 2.0
  Polar areas with abs(latitude) bigger then 85.05112878 are clipped off.

  What are zoom level constants (pixels/meter) for pyramid with EPSG:900913?
    whole region is on top of pyramid (zoom=0) covered by 256x256 pixels tile,
    every lower zoom level resolution is always divided by two
    initialResolution = 20037508.342789244 * 2 / 256 = 156543.03392804062

  What is the difference between TMS and Google Maps/QuadTree tile name
  convention?
    The tile raster itself is the same (equal extent, projection, pixel size),
    there is just different identification of the same raster tile.
    Tiles in TMS are counted from [0,0] in the bottom-left corner, id is XYZ.
    Google placed the origin [0,0] to the top-left corner, reference is XYZ.
    Microsoft is referencing tiles by a QuadTree name, defined on the website:
    http://msdn2.microsoft.com/en-us/library/bb259689.aspx

  The lat/lon coordinates are using WGS84 datum, yes?
    Yes, all lat/lon we are mentioning should use WGS84 Geodetic Datum.
  """

  def __init__(self, tileSize=256):
    "Initialize the TMS Global Mercator pyramid"
    self.tileSize = tileSize
    self.initialResolution = 2 * math.pi * 6378137 / self.tileSize
    # 156543.03392804062 for tileSize 256 pixels
    self.originShift = 2 * math.pi * 6378137 / 2.0
    # 20037508.342789244
    self._oSd = self.originShift / 180.0
    self._p2 = math.pi / 2.0
    self._pd = math.pi / 180.0
    self._pd2 = math.pi / 360.0

  def LatLonToMeters(self, lat, lon):
    "Converts lat/lon in WGS84 Datum to XY in Spherical Mercator EPSG:900913"
    mx = lon * self._oSd
    my = math.log(math.tan((90 + lat) * self._pd2)) / self._pd
    my = my * self._oSd
    return mx, my

  def MetersToLatLon(self, mx, my):
    "Converts XY point from Spherical Mercator to lat/lon in WGS84 Datum"
    lon = mx / self._oSd
    lat = my / self._oSd
    lat = (2*math.atan(math.exp(lat * self._pd)) - self._p2) / self._pd
    return lat, lon

  def PixelsToMeters(self, px, py, zoom):
    "Converts pixel coordinates in given zoom level of pyramid to EPSG:900913"
    res = self.Resolution(zoom)
    mx = px * res - self.originShift
    my = py * res - self.originShift
    return mx, my

  def MetersToPixels(self, mx, my, zoom):
    "Converts EPSG:900913 to pyramid pixel coordinates in given zoom level"
    res = self.Resolution(zoom)
    px = (mx + self.originShift) / res
    py = (my + self.originShift) / res
    return px, py

  def getMetersToPixelsXform(self, zoom, tilesbb):
    """Returns the 6 parameters to convert meters to pixels by affine transform.

    An affine transform is given by 2 equations:
      out_x = a * in_x + b * in_y + c
      out_y = d * in_x + e * in_y + d
    Args:
      zoom: zoom factor for the transform
      tilesbb: tiles for transform, minx, miny, maxx, maxy
    Returns:
      a, b, c, d, e, f  when in_x, in_y are meters, out_x, out_y are pixels
      i.e.: 1/res, 0, originShift/res twice (res depends on zoom!)
    """
    ires = 1.0 / self.Resolution(zoom)
    delta = self.originShift * ires
    return (ires,   0.0, delta-tilesbb[0]*256,
             0.0, -ires, (tilesbb[3]+1)*256-delta)

  def PixelsToTile(self, px, py):
    "Returns a tile covering region in given pixel coordinates"
    tx = int( math.ceil( px / float(self.tileSize) ) - 1 )
    ty = int( math.ceil( py / float(self.tileSize) ) - 1 )
    return tx, ty

  def PixelsToRaster(self, px, py, zoom):
    "Move the origin of pixel coordinates to top-left corner"
    mapSize = self.tileSize << zoom
    return px, mapSize - py

  def MetersToTile(self, mx, my, zoom):
    "Returns tile for given mercator coordinates"
    px, py = self.MetersToPixels(mx, my, zoom)
    return self.PixelsToTile(px, py)

  def LatLonToTile(self, lat, lon, zoom):
    "Returns tile for given lat/lon in WGS84 Datum"
    mx, my = self.LatLonToMeters(lat, lon)
    return self.MetersToTile(mx, my, zoom)

  def TileBounds(self, tx, ty, zoom):
    "Returns bounds of the given tile in EPSG:900913 coordinates"
    minx, miny = self.PixelsToMeters(tx*self.tileSize, ty*self.tileSize, zoom)
    maxx, maxy = self.PixelsToMeters((tx+1)*self.tileSize,
                                     (ty+1)*self.tileSize, zoom )
    return minx, miny, maxx, maxy

  def TileLatLonBounds(self, tx, ty, zoom):
    "Returns bounds of the given tile in latitude/longitude using WGS84 datum"
    bounds = self.TileBounds(tx, ty, zoom)
    minLat, minLon = self.MetersToLatLon(bounds[0], bounds[1])
    maxLat, maxLon = self.MetersToLatLon(bounds[2], bounds[3])
    return minLat, minLon, maxLat, maxLon

  def Resolution(self, zoom):
    "Resolution (meters/pixel) for given zoom level (measured at Equator)"
    return self.initialResolution / (2**zoom)

  def ZoomForPixelSize(self, pixelSize):
    "Maximal scaledown zoom of the pyramid closest to the pixelSize."
    for i in range(30):
      if pixelSize > self.Resolution(i):
        return i-1 if i!=0 else 0 # We don't want to scale up

  def GoogleTile(self, tx, ty, zoom):
    "Converts TMS tile coordinates to Google Tile coordinates"
    # coordinate origin is moved from bottom-left to top-left corner of extent
    return tx, (2**zoom - 1) - ty

  def QuadTree(self, tx, ty, zoom ):
    "Converts TMS tile coordinates to Microsoft QuadTree"
    quadKey = ""
    ty = (2**zoom - 1) - ty
    for i in range(zoom, 0, -1):
      digit = 0
      mask = 1 << (i-1)
      if (tx & mask) != 0:
          digit += 1
      if (ty & mask) != 0:
          digit += 2
      quadKey += str(digit)
    return quadKey


if __name__ == "__main__":
  import sys

  def Usage(s = ""):
    print "Usage: tile.py zoomlevel lat lon [latmax lonmax]"
    if s:
      print
      print s
    print """
This utility prints for given WGS84 lat/lon coordinates (or bounding
box) the list of tiles covering specified area. Tiles are in Google Maps
'mercator', and in the given pyramid 'zoomlevel'.  For each tile various
information is printed including bonding box in EPSG:900913 and WGS84."""
    sys.exit(1)

  def main():
    zoomlevel = None
    lat, lon, latmax, lonmax = None, None, None, None
    boundingbox = False

    for arg in sys.argv[1:]:
      if zoomlevel is None: zoomlevel = int(arg)
      elif lat is None: lat = float(arg)
      elif lon is None: lon = float(arg)
      elif latmax is None: latmax = float(arg)
      elif lonmax is None: lonmax = float(arg)
      else: Usage("ERROR: Too many parameters")

    if zoomlevel == None or lat == None or lon == None:
        Usage("ERROR: Specify at least 'zoomlevel', 'lat' and 'lon'.")
    if latmax is not None and lonmax is None:
        Usage("ERROR: give both or neither of 'latmax' and 'lonmax'.")

    if latmax is not None and lonmax is not None:
      if latmax < lat: Usage("ERROR: 'latmax' must be bigger then 'lat'")
      if lonmax < lon: Usage("ERROR: 'lonmax' must be bigger then 'lon'")
      boundingbox = lon, lat, lonmax, latmax

    tz = zoomlevel
    mercator = GlobalMercator()

    mx, my = mercator.LatLonToMeters(lat, lon)
    print "Spherical Mercator (ESPG:900913) coordinates for lat/lon:"
    print mx, my
    tminx, tminy = mercator.MetersToTile(mx, my, tz)

    if boundingbox:
      mx, my = mercator.LatLonToMeters(latmax, lonmax)
      print "Spherical Mercator (ESPG:900913) coordinate for maxlat/maxlon:"
      print mx, my
      tmaxx, tmaxy = mercator.MetersToTile(mx, my, tz)
    else:
      tmaxx, tmaxy = tminx, tminy

    for ty in range(tminy, tmaxy+1):
      for tx in range(tminx, tmaxx+1):
        tilefilename = "%s/%s/%s" % (tz, tx, ty)
        print tilefilename, "( TileMapService: z / x / y )"

        gx, gy = mercator.GoogleTile(tx, ty, tz)
        print "\tGoogle:", gx, gy, mercator.GoogleTile(gx, gy, tz)
        # quadkey = mercator.QuadTree(tx, ty, tz)
        # print "\tQuadkey:", quadkey, '(',int(quadkey, 4),')'
        # bounds = mercator.TileBounds( tx, ty, tz)
        # print
        # print "\tEPSG:900913 Extent: ", bounds
        wgsbounds = mercator.TileLatLonBounds( tx, ty, tz)
        print "\tWGS84 Extent:", wgsbounds
        # print "\tgdalwarp -ts 256 256 -te %s %s %s %s %s %s_%s_%s.tif" % (
        #     bounds[0], bounds[1], bounds[2], bounds[3],
        #     "<your-raster-file-in-epsg900913.ext>", tz, tx, ty)
        print

  main()

