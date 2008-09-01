#!/usr/bin/env python
""" Make a 256 x 256 PNG map-tile with transparent background + polylines.
"""
import array
import struct
import zlib

png_signature = struct.pack("8B", 137, 80, 78, 71, 13, 10, 26, 10)

class PNG(object):

  def __init__(self, minx=None, miny=None, maxx=None, maxy=None,
      width=256, height=256):
    self.width = width
    self.height = height
    arow = ''.join('\0' for i in range(width))
    self.data = [array.array('B', arow) for i in range(height)]
    black = 0, 0, 0
    white = 255, 255, 255
    self.palette = array.array('B', struct.pack('9B', *(2*black+white)))
    self.color_index = dict(black=1, white=2)
    if minx is None:
      def coords(x, y): return x, y
      self.coords = coords
      return
    self.minx = minx
    self.miny = miny
    self.xmul = width / (maxx - minx)
    self.ymul = height / (maxy - miny)

  def coords(self, x, y):
    result = int(self.xmul*(x-self.minx)), int(self.ymul*(y-self.miny))
    # print 'K', x, y, result
    return result

  def get_color(self, r, g, b):
    rgb = r, g, b
    if rgb not in self.color_index:
      index = self.color_index[rgb] = len(self.palette) // 3
      self.palette.extend(rgb)
      return index
    return self.color_index[rgb]

  def plot(self, x, y, color):
    if x<0 or y<0: return
    try: self.data[y][x] = color
    except IndexError: return

  # draw line by Bresenham algorithm
  def draw_line(self, (x0, y0), (x1, y1), color):
    steep = abs(y1 - y0) > abs(x1 - x0)
    if steep:
      x0, y0 = y0, x0
      x1, y1 = y1, x1
    if x0 > x1:
      x0, x1 = x1, x0
      y0, y1 = y1, y0
    deltax = x1 - x0
    deltay = abs(y1 - y0)
    error = deltax // 2
    if y0 < y1:
      ystep = 1
    else:
      ystep = -1
    y = y0
    for x in range(x0, x1):
      if steep: self.plot(y, x, color)
      else: self.plot(x, y, color)
      error -= deltay
      if error < 0:
        y += ystep
        error += deltax
    if steep: self.plot(y1, x1, color)
    else: self.plot(x1, y1, color)

  def polyline(self, arr, color):
    pts = iter(arr)
    previous = self.coords(pts.next(), pts.next())
    for pt in pts:
      pt = self.coords(pt, pts.next())
      self.draw_line(previous, pt, color)
      previous = pt

  def dump(self):
    raw_data = '\0' + '\0'.join(row.tostring() for row in self.data)

    return ''.join((png_signature,
      self.pack_chunk('IHDR',
          struct.pack("!2I5B", self.width, self.height, 8,3,0,0,0)),
      self.pack_chunk('PLTE',
          self.palette.tostring()),
      self.pack_chunk('tRNS',
          '\0'),
      self.pack_chunk('IDAT',
          zlib.compress(raw_data, 9)),
      self.pack_chunk('IEND', '')
      ))

  def pack_chunk(self, tag, data):
    to_check = tag + data
    return struct.pack("!I", len(data)) + to_check + \
           struct.pack("!I", zlib.crc32(to_check) & 0xffffffff)


if __name__ == '__main__':
  def maintest():
    print 'creating test PNG'
    p = PNG()
    red = p.get_color(255, 0, 0)
    green = p.get_color(0, 255, 0)
    p.draw_line((0,0), (255,255), red)
    p.draw_line((0,255), (255,0), green)
    print 'writing to file test.png'
    f = open("test.png", "wb")
    f.write(p.dump())
    f.close()
  maintest()
