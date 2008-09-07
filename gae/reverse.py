#!/usr/bin/python2.5
#
# Copyright 2008 Azillia Inc. All Rights Reserved.

from google.appengine.api import urlfetch
from google.appengine.ext import webapp
from django.utils import simplejson
from wsgiref import handlers
import logging

class Reverse(webapp.RequestHandler):
  def get(self):
    lat = self.request.get("lat")
    lng = self.request.get("lng")
    url = "http://ws.geonames.org/findNearbyPostalCodesJSON?lat=%s&lng=%s" % (
           lat, lng)
    result = urlfetch.fetch(url)
    logging.log(logging.INFO, result)
    if result.status_code == 200:
      json = simplejson.loads(result.content)
      logging.log(logging.INFO, json)
      try:
        zips = json['postalCodes']
        zip = zips[0]['postalCode']
        logging.log(logging.INFO, zip)
      except KeyError, e:
        zip = "Not available"
      self.response.out.write(zip)
    else:
      self.response.out.write("Not available")

def application():
    return webapp.WSGIApplication([('/reverse', Reverse)], debug=True)

def main():
    handlers.CGIHandler().run(application())

if __name__ == '__main__':
    main()
