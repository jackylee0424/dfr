#!/usr/bin/env python

## face server
import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web
import os
import tornado.websocket
import base64
import urllib2
import time
import sys
import json
import cv2
from tinyfacerec.model import EigenfacesModel
from tinyfacerec.model import FisherfacesModel
from tinyfacerec.distance import CosineDistance
import pickle

tornado.options.define("port", default=8080, help="run on the given port", type=int)

def imgpreprocess(filepath):
    im = cv2.imread(filepath)
    im = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    im = cv2.resize(im,(128, 128), interpolation = cv2.INTER_CUBIC)
    im = cv2.equalizeHist(im)
    return im

class WSocketHandler(tornado.websocket.WebSocketHandler):
    def open(self):
        print "ws opened"
        self.dir_name = "%.0f"%(time.time()*1000.0)
        self.mode = 0
        self.model_loaded = False
        self.mmodel = None
        self.labeldict = dict(ts=time.time())
        self.load_data()
        self.genesis_ts = 1392697800000
    
    
    def load_data(self):
        with open('data//model//model.bin', 'rb') as input:
            self.mmodel = pickle.load(input)
            self.model_loaded = True
        with open('data//labels.bin', 'rb') as input:
            self.labeldict = pickle.load(input)
            print self.labeldict
    
    def detect_face(self, img):
        t = time.time()
        output_name, min_dist =  self.mmodel["eigen"].predict(img,-.5)
        try:
            output_label = self.labeldict[str(output_name+self.genesis_ts)]
        except:
            print "no mapped label found"
            output_label = str(output_name+self.genesis_ts)
        
        print "predicted (eigen)= %s (%f). took %.3f ms"%(output_label, min_dist,(time.time()-t)*1000.)
        t = time.time()
        output_name, min_dist =  self.mmodel["fisher"].predict(img,-.5)
        print "predicted (fisher)= %s (%f). took %.3f ms"%(output_label, min_dist,(time.time()-t)*1000.)

    def allow_draft76(self):
        # for iOS 5.0 Safari
        return False
    
    def on_message(self, message):
        parsed = tornado.escape.json_decode(message)
        self.mode = int(parsed["mode"])

        d = urllib2.unquote(parsed["base64Data"])
        img = base64.b64decode(d.split(',')[1])
        fname = "%.0f"%(time.time()*1000.0)
        
        if not os.path.exists("data//raw//"+self.dir_name):
            os.makedirs("data//raw//"+self.dir_name)
        
        fullpath = "data//raw//%s//%s.png"%(self.dir_name,fname)
        with open(fullpath,"wb") as f:
            f.write(img)
            print "saved to %s.png"%fname
                               
        if (self.mode>0):
            print "Detect mode"
            self.detect_face(imgpreprocess(fullpath))
        
        else:
            print "Training mode"
            self.labeldict[self.dir_name]=parsed["label"]
            print "Labels- %s"%(self.labeldict[self.dir_name])

    def on_close(self):
        # save label pairs to disk
        with open('data//labels.bin', 'wb') as output:
            pickle.dump(self.labeldict, output, pickle.HIGHEST_PROTOCOL)
        print "ws closed"


class CapturePageHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("face.html")

def main():
    settings = dict(
            template_path=os.path.join(os.path.dirname(__file__), "template"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            debug=False)
    
    tornado.options.parse_command_line()
    application = tornado.web.Application([
        (r"/", CapturePageHandler),
        (r"/ws",WSocketHandler),

    ],**settings)
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(tornado.options.options.port)
    print "open your chrome at http://localhost:8080"
    tornado.ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    main()
