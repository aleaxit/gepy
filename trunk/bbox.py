import shpUtils

def f(n):
  return '%.3f' % n

def main():
  # a sample bounding-box for SF Bay Area around Palo Alto
  CT = (37.44187102188893, -122.14187622070314)
  SW = (37.40098280627522, -122.21054077148438)
  NE = (37.482759237502634, -122.07321166992188) 

  shapefile = 'fe_2007_us_zcta500/fe_2007_us_zcta500.shp'

  # xmin, ymin, xmax, ymax
  bbox = (CT[0] - (CT[0]-SW[0])*3, CT[1] - (CT[1]-SW[1])*3,
          CT[0] + (NE[0]-CT[0])*3, CT[1] + (NE[1]-CT[1])*3,
         )

  recs = shpUtils.loadShapefileIntersecting(shapefile, bbox, 20)
  print len(recs), 'zipcodes apply:'
  for i, r in enumerate(recs):
    s = r['shp_data']
    print 'Record %d, zip=%r' % (i, r['dbf_data']['zip']),
    print 'rng:', s.get('numparts'),
    print 'pts: %4s' % s.get('numpoints'),
    print 'bb', f(s.get('xmin')), f(s.get('ymin')),
    print f(s.get('xmax')), f(s.get('ymax'))
  print 'for bb:',
  for x in bbox: print f(x),
  print

main()
