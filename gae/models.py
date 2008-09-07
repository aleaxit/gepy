""" Models for the GEPY demo on GAE
"""
import logging
from google.appengine.ext import db


class Tile(db.Model):
  """Models a tile (PNG data).

  Attributes:
    name: unique tile id in a form such as tile_USA_234_567_4
    data: blob of PNG data
  """
  name = db.StringProperty(required=True)
  data = db.BlobProperty(required=True)
