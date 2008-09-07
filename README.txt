The gepy project means to cover all kinds of GEographic applications of
PYthon, and it's starting out with ways to use Google App Engine (GAE)
to serve data ("tiles") for mash-ups on Google Maps.

The Python files in gepy's root directory are currently (9/7/08 as of
gepy's r62 -- subject to change, as many of these are semi-obsolete --
in the near future I may move fully obsolete ones to a subdirectory):

dbfUtils.py
  utilities to deal with DBF files (which are an integral part of
  ArcView "Shapefiles", e.g. the TIGER/Line [tm] files freely
  distributed by the US Census), originally by Zachary Forest Johnson
dopngtile.py
  build PNG 256x256 tiles directly from Shapefiles (semi-obsolete)
dousa_tiles.py
  an attempt to generate PNG tiles AND upload them to GAE, didn't work
  too well, obsolete
latlon_totile.py
  trying to map each tile into a class, didn't work too well, obsolete
mkusapik.py
  one-off script to make USA_dict.pik with a pickled dict for USA_1.zip,
  not needed any more and thus obsolete
prepcazip_tiles.py
  prepare tiles for CA zipcode boundaries as PNG files in /tmp/ from a
  Polyfile (see shp2polys.py), shows how to customize shp2polys
prepusa_tiles.py
  prepare tiles for continental US state boundaries as PNG files in
  /tmp/ from a Polyfile (see shp2polys.py).
prepzips.py
  prepare zip files and index from PNG tile files in /tmp/
pypng.py
  pure-Python writing of (and line drawing on) PNG files, not used any
  more (thus, somewhat obsolete -- we use PIL for this task currently)
sdb_to_picked_dict.py
  one-off script to convert a .sdb sqlite3 database to a pickLed dict
  (not needed any more and thus obsolete)
serve.py
  convenience script to serve files in the current directory on
  localhost via HTTP, _and_ serve CGI via cgi-bin, open a browser, &c
shp2polys.py
  convert an Arcview Shapefile into a compact, faster 'Polyfile'
shpextract.py
  read info from a Shapefile, inspired by Zachary Forest Johnson's
  shpUtils.py
test_shpe.py
  tests for shpextract (via doctest)
tile.py
  geographical computation for Tile Map Services, original from
  klokan@klokan.cz 's http://www.klokan.cz/projects/gdal2tiles/
upusa_tiles.py
  attempt to GAE-upload USA state boundaries, now obsolete

Other contents of gepy's root directory at this time:

Scripts:
  dumpdb -- show some summary info from a DBF file
Symlinks:
  cgi-bin -- convenience symlink for ./serve.py
HTML files:
  boxer.html
    utility to see lat/long of centroid and bounds, as well as zoom
    factor, for a map (TODO: make map canvas larger or smaller on
    request, e.g. with +/- buttons, display its size in pixels, ...)
  crosshair.html
    show the tile_crosshair.png file on the map
  egeo.html
    show centroid and boundaries as the user scrolls a map
  index.html
    base file for serve.py, draws boundaries on the fly for some
    Mountain View and Palo Alto zipcodes
  states.html
    another file for serve.py, draws boundaries on the fly for US states
  tiles.html
    another file for serve.py, just shows tile boundaries as squares
Other data files:
  bystate.txt
    population and centroid lat/long for each state
  ca
    directory with Arcview Shapefile for CA's zipcode boundaries
  cazip.ply
    polyfile for CA's zipcode boundaries
  cont_us_state.ply
    polyfile for US state boundaries
  fe_2007_us_state
    directory with Arcview Shapefile for US state boundaries
  nostates.txt
    2-letter USPS abbreviation for Alaska, Hawaii, Puerto Rico, &c
  tile_crosshairs.png
    a 256 x 256 PNG tile with small crosshairs (used as "no tile"
    placeholder and also copied into the GAE subdirectory)
GAE-specific components:
  gae
    what needs to be deployed to Google App Engine (and is currently
    deployed to gepy.appspot.com) for serving 'tiles' for google maps
    and HTML files to demonstrate them.
Directory gae contains:
  USA_1.zip USA_2.zip USA_3.zip USA_dict.pik
    sharded zipfiles for US state boundaries & their index
  ZIPCA_1.zip ZIPCA_2.zip ZIPCA_3.zip ZIPCA_4.zip ZIPCA_5.zip
      ZIPCA_6.zip ZIPCA_7.zip ZIPCA_dict.pik
    sharded zipfiles for CA zipcode boundaries & their index
  app.yaml index.yaml favicon.ico
    usual GAE app config & icon
  gepy.html
    starter HTML file to see US state boundaries, also served as /
  main.py
    serves tiles for any theme (US state boundaries, CA zipcode ones...)
  models.py
    GAE model to save PNG tiles to the datastore
  reverse.py
    reverse geocoding of ZIP codes
  tile_crosshairs.png
    a 256 x 256 PNG tile with small crosshairs (used as "no tile"
    placeholder and also present in the main gepy repo directory)
  zipca.html
    starter HTML file to see CA zipcode boundaries
  zipcode.html
    starter HTML file to see reverse geocoding of ZIP codes

gepy.appspot.com is currently updated and is serving exactly the stuff
that's now in that gae subdirectory of the gepy repository.

Visiting gepy.appspot.com/zipcode.html and clicking somewhere on the
map will show you what zipcode you've clicked on, thanks to reverse
geocoding performed by reverse.py.

Visiting the home URL, http://gepy.appspot.com/ , shows you a map of
the continental US with state boundaries (including DC but excluding
AK and HI as well as other non-states such as Puerto Rico &c)
superimposed in red. You can zoom in a few times and the resolution
will smoothly increase, but if you zoom in too much the only parts in
red will be tiny "crosshair" crosses (which I use to denote that a
"tile" is absent -- you'll also see some of those at sufficiently high
resolution where no state border happens to intersect a tile;-).

All tiles needed for zoom levels 3 to 9 are within zipfiles USA_*.zip,
which are also uploaded to GAE, and "indexed" by USA_dict.pik, a pickled
dict mapping z_x_y strings for a tile to number of USA_* zipfile.

When asked for a tile, main.py checks the cache and store first, or else
tries getting it from the appropriate zipfile (and put it to cache, and
to store too if feasible -- the latter task is dropped if the store is
getting contention, as there's no real hurry to put a tile in store
right now, it WILL get there eventually); if it's not in any zipfile, it
uses the crosshairs tile instead (and puts that to store and cache).

Zoom levels 10 and above remain to be done (too large for the current
simplistic approach to tile preparation, require a rearchitecting).

How I prepare the tiles (on my machine, making the zipfiles that then
get uploaded) may be of some interest.  I start with an ArcView
Shapefile (a TIGER/Line file freely distributed by the US Census) and
preprocess it into a simpler and smaller format of my own invention
which I've called a "polyfile" -- cont_us_state.ply in the gepy repo
is an example, about 2.6 MB vs the 10+MB of the original
fe_2007_us_state/* Shapefile.  Writing of polyfiles (from Shapefiles)
and reading them are handled by classes in shp2polys.py; all
coordinates are uniformly in "meters" as little-endian integers as per
EPSG:900913 standard (not lat/long like Shapefiles, so there's no
further need for trig to process a polyfile, only to generate it); the
.ply format is actually a .zip file under a false name (much like .jar
files &c) so it can conveniently hold any sub-"file" in an easily
copyable way.

Script prepusa_tiles.py uses these modules to prepare the tiles (as PNG
files in /tmp -- prepzips.py is later manually run to prepare the
zipfiles and .pik), doing the painting via PIL (I'm currently not using
the pypng module to paint directly from Python).  The approach is the
reason I can't currently go above a certain zoom level: I do all
painting on ONE large canvas, then successively crop the canvas to get
all the PNG files for the tiles (tiles are always 256x256 pixels).  PIL
currently just offers extra speed for the tile preparation (and some
limitations, such as, ONLY width-1 lines in polygons, sigh) but it has
more potential -- I could do filling of the polygons with some color
(and transparency, with an RGBA image -- would be easy to switch to
that) and also write text on the image in any TTF font I have around.

The reason I've commented off the writing of the state abbreviations
(CA, SC, TX etc) is that I don't know how to find automatically a good
spot for the writing!  The state's centroid can be outside of the
state itself (it's in the Gulf of Mexico for FL, for example!-) or
otherwise look pretty bad for oddly-shaped states; and small states
hardly have space for their 2-letter USPS abbreviations (indeed
manually drawn or corrected maps move state abvs to somewhere in the
ocean, with straight lines connecting them;-).  Finding a fix for this
would be quite interesting.

Some state boundaries look a bit strange but I think they're that way
in the US Census data, for example extending out to sea in weird
shapes to encompass some not-so-close island; I hope the zipcodes will
be better that way.  One graphic anomaly that happens a bit too often
for my tastes is connected with perfectly horizontal borders (running
exactly E-W) which sometimes hardly show (moving to a thickness of 2+
pixels would fix that, but as I said PIL does not currently support
that for polygons, sigh).

Anyway -- the current state of gepy suggests many possible enhancements (TODOs):
1. better docs AND tests!!! (& code reviews &c please...!)
2. reorg and shard things to draw at any desired zoom level
3. besides purely geometric info, also supply demographic &c info
   keyed by state abv / zipcode / etc and show it on the popup (or
   SOMEwhere;-) in a descendant of zipcodes.html + reverse.py
4. try semi-transparent filling; figure out a good way to use text
5. hack PIL (or use a dirtier hack;-) to allow width>1 polygon outlines
6. (stretch) find a good way to allow human spotting and cleaning of
   the data, registering the edits and using them on the site
7. integrate reverse.py with both the zipcode & state boundaries display

