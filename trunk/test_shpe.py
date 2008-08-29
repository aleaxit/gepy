""" Tests of shpextract module using ca/zt06_d00 Shapefile (5-digits ZCTAs
    in CA, freely supplied by the US Census as a TIGER/Line [TM] file).
"""
import doctest
import shpextract

def test_some_metas():
  """ 
  >>> s = shpextract.Shp('ca/zt06_d00.shp', id_field_name='ZCTA')
  >>> len(s)
  1678
  >>> s.last_read_id
  >>> s.last_read_recno
  >>> s.set_next_id('94303')
  >>> r = s.get_next_record(id=1, recno=1, bbox=1, datalen=1, data=0)
  >>> s.last_read_id
  '94303'
  >>> s.last_read_recno
  2459
  >>> print r[0], r[1], r[3]
  94303 2459 77
  >>> print shpextract.showbb(r[2]).strip()
  -122.1552   37.4162 -122.0780   37.5001
  >>> s.get_id(2459)
  '94303'
  >>> s.select_bbox
  >>> s.set_select_bbox(r[2])
  >>> print shpextract.showbb(s.select_bbox).strip()
  -122.1552   37.4162 -122.0780   37.5001
  >>> s.rewind()
  >>> zips = []
  >>> for r in s:
  ...   zips.append(r[0])
  ...
  >>> ' '.join(sorted(zips))
  '94025 94043 94063 94301 94303 94304 94304 94305 94306 94560'
  >>> len(zips)
  10
  >>>
  """

def _test():
    numfailures, numtests = doctest.testmod()
    if numfailures == 0:
      print '%d tests passed successfully' % numtests
    # if there are any failures, doctest does its own reporting!-)

if __name__ == "__main__":
    _test()
