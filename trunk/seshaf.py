import array
import struct
import sys

big_endian = struct.unpack('>i', struct.pack('=i', 23)) == (23,)
print 'Machine is', ('little', 'big')[big_endian], 'endian'

def read_and_unpack(fp, fmt):
  n = struct.calcsize(fmt)
  return struct.unpack(fmt, fp.read(n))

def read_some(fp, typecode, n):
  data = array.array(typecode)
  data.fromfile(fp, n)
  if big_endian: data.byteswap()
  return data

def read_doubles(fp, nd): return read_some(fp, 'd', nd)
def read_ints(fp, ni): return read_some(fp, 'i', ni)

def showbb(msg, dbls):
  print msg,
  for d in dbls: print '%9.4f'%d,
  print

def showrec(fp):
  recno, conle = read_and_unpack(fp, '>II')
  nexter = fp.tell() + 2*conle
  shaty, = read_and_unpack(fp, '<I')
  print 'Rec#%d, content length %d, shape type %d' % (recno, conle, shaty)
  try:
    if shaty == 0: return True
    elif shaty not in (3, 5): return False
    bbox = read_doubles(fp, 4)
    showbb(' rec bbox:', bbox)
    numparts, numpoints = read_and_unpack(fp, '<II')
    print '%d parts, %d points:' % (numparts, numpoints),
    parts = read_ints(fp, numparts)
    for part in parts: print part,
    print
    return True
  finally:
    fp.seek(nexter)

  
def main(shapefile):
  fp = open(shapefile, 'rb')
  filecode, = read_and_unpack(fp, '>I')
  fp.seek(24)
  fileleng, = read_and_unpack(fp, '>I')
  version, = read_and_unpack(fp, '<I')
  shapetype, = read_and_unpack(fp, '<I')
  print 'File code %d, length %d, version %d, shape type %d' % (
    filecode, fileleng, version, shapetype)
  bbox = read_doubles(fp, 8)
  showbb('File bbox:', bbox[:4])
  if not showrec(fp): return
  if not showrec(fp): return


main('ca/zt06_d00.shp')
