#!/usr/bin/env python

## face server
import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web
import os
from os.path import exists, join
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
import hashlib
import shutil

genesis_ts = 1392697800000
total_images=0

if (len(sys.argv)!=2):
    print "$ python node_server.py [your ip]"
    sys.exit(0)
myIP = sys.argv[1]

tornado.options.define("port", default=8080, help="run on the given port", type=int)

def sha256_for_file(path, block_size=256*128, hr=True):
    sha256 = hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda: f.read(block_size), b''):
            sha256.update(chunk)
    if hr:
        return sha256.hexdigest()
    return sha256.digest()

def read_data(path, sz=None):
    X = []
    y = []
    for dirname, dirnames, filenames in os.walk(path):
        for subdirname in dirnames:
            subject_path = os.path.join(dirname, subdirname)
            for filename in os.listdir(subject_path):
                try:
                    if filename[-3:] =="png":
                        im = imgpreprocess(os.path.join(subject_path, filename))
                        X.append(im)
                        y.append(int(subdirname)-genesis_ts)
                except IOError:
                    print "I/O error({0}): {1}".format(errno, strerror)
                except:
                    print "Unexpected error:", sys.exc_info()[0]
                    raise
    return X,y

def imgpreprocess(filepath):
    im = cv2.imread(filepath)
    im = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    im = cv2.resize(im,(128, 128), interpolation = cv2.INTER_CUBIC)
    im = cv2.equalizeHist(im)
    return im

def train():
    global total_images
    ## read images
    t = time.time()
    X,y = read_data("data/raw/")
    
    ## save to matrix data
    #filename_temp = os.urandom(8).encode('hex')
    filename_temp = "raw"
    if not os.path.exists("data//processed"):
        os.makedirs("data//processed")
    with open('data//processed//%s.data'%filename_temp, 'wb') as output:
        pickle.dump({'X': X, 'y':y}, output, pickle.HIGHEST_PROTOCOL) ## X: image, y: label(integer)

    total_images = len(X)
    #print "total images: %d"%total_images
    if len(X)<10:
        print "too few images stored. train more!"
        return
    else:
        print "%d raw images loaded. took %.3f ms"%(len(X),(time.time()-t)*1000.)

    ## to compute a model, need to merge all the data by simpling appending [X,X,X,...], [y,y,y,...]
    with open('data//processed//%s.data'%filename_temp, 'rb') as input:
        xydata = pickle.load(input)
    
    # compute models
    t = time.time()
    
    # train eigen and fisher model (excluding 1st element in each label
    model_eigen = EigenfacesModel(xydata['X'][1:], xydata['y'][1:], dist_metric = CosineDistance())
    model_fisher = FisherfacesModel(xydata['X'][1:], xydata['y'][1:], dist_metric = CosineDistance())
    
    if not os.path.exists("data//model"):
        os.makedirs("data//model")
    with open('data//model//model.bin', 'wb') as output:
        pickle.dump(dict(eigen=model_eigen, fisher=model_fisher), output, pickle.HIGHEST_PROTOCOL)
    
    print "model computed and saved. took %.3f ms"%((time.time()-t)*1000.)
    
    # hashing model as a signature to get the latest model up-to-date
    #t = time.time()
    #print "model hashing: %s took %.3f ms"%(sha256_for_file('data//model//model.bin',hr=True),(time.time()-t)*1000.)

## for model file download
class ModelDownloadSocket(tornado.websocket.WebSocketHandler):
    def open(self):
        print "ModelDownloadSocket opened"
        filetx = join("data","model","model.bin")
        self.filehash = sha256_for_file(filetx)
        print "file hash", self.filehash
        indata = open(filetx, "rb").read()
        self.write_message(indata, binary=True)
    
    def on_message(self, m):
        print "client response: %s"%m
        jm = json.loads(str(m))
        if jm["confirm_hash"] == self.filehash:
            print "model sent successfully"
        print "closing FileDownloadSocket connection"
        self.close()
    
    def on_close(self):
        print "ModelDownloadSocket closed"

## for label file download
class LabelDownloadSocket(tornado.websocket.WebSocketHandler):
    def open(self):
        print "LabelDownloadSocket opened"
        filetx = join("data","labels.bin")
        self.filehash = sha256_for_file(filetx)
        print "file hash", self.filehash
        indata = open(filetx, "rb").read()
        self.write_message(indata, binary=True)
    
    def on_message(self, m):
        print "client response: %s"%m
        jm = json.loads(str(m))
        if jm["confirm_hash"] == self.filehash:
            print "label sent successfully"
        print "closing LabelDownloadSocket connection"
        self.close()
    
    def on_close(self):
        print "LabelDownloadSocket closed"

class WSocketHandler(tornado.websocket.WebSocketHandler):
    def open(self):
        print "ws opened"
        self.dir_name = "%.0f"%(time.time()*1000.0)
        self.mode = 0
        self.data_loaded = False
        self.mmodel = None
        self.labeldict = dict(ts=time.time())
        self.load_data()
    
    def load_data(self):
        try:
            with open('data//labels.bin', 'rb') as input:
                self.labeldict = pickle.load(input)
                #print self.labeldict
        except:
            print "no label file found"

        try:
            with open('data//model//model.bin', 'rb') as input:
                self.mmodel = pickle.load(input)
            self.data_loaded = True
        except:
            self.data_loaded = False
    
    def detect_face(self, img):
        t = time.time()
        output_name, min_dist =  self.mmodel["eigen"].predict(img,-.5)
        try:
            output_label = self.labeldict[str(output_name+genesis_ts)]
        except:
            print "no mapped label found"
            output_label = str(output_name+genesis_ts)
        
        print "predicted (eigen)= %s (%f). took %.3f ms"%(output_label, min_dist,(time.time()-t)*1000.)
        t = time.time()
        output_name, min_dist =  self.mmodel["fisher"].predict(img,-.5)
        print "predicted (fisher)= %s (%f). took %.3f ms"%(output_label, min_dist,(time.time()-t)*1000.)

        self.write_message(json.dumps(dict(computed=output_label)))

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
                               
        if (self.mode>0) and (self.data_loaded):
            print "Detect mode"
            self.detect_face(imgpreprocess(fullpath))
        else:
            print "Training mode"
            self.labeldict[self.dir_name]=parsed["label"]
            print "Labels- %s"%(self.labeldict[self.dir_name])

    def on_close(self):
        global total_images
        if (self.mode>0):
            shutil.rmtree("data//raw//%s"%(self.dir_name))
        # save label pairs to disk
        if not os.path.exists("data"):
            os.makedirs("data")
        with open('data//labels.bin', 'wb') as output:
            pickle.dump(self.labeldict, output, pickle.HIGHEST_PROTOCOL)

        # check if re-train is needed
        X,y = read_data("data/raw/")
        if (len(X)-total_images)>5:
            train()
        print "ws closed"

class CapturePageHandler(tornado.web.RequestHandler):
    def get(self):
        try:
            try:
                label = self.get_argument('label',None, True)
                if label=='':
                    self.redirect('/new')
                self.render("face.html",mode=-1, title="New User", myIP=myIP,label=label)
            except:
                self.redirect('/new')
        except:
            self.redirect('/new')

class DoneLoginPageHandler(tornado.web.RequestHandler):
    def get(self):
        try:
            label = self.get_argument('label',None, True)
            if label=='':
                self.redirect('/')
        except:
            self.redirect('/')
        self.write('''<html><head>
            <meta charset="utf-8">
            <title>p2pID</title>
            <link rel="stylesheet" href="static/css/bootstrap.css">
            <link rel="stylesheet" href="static/css/jsfeat.css">
            </head><body>''')
        self.write("<h2>Login Successfully, %s</h2>"%label)
        self.write("<p>move on to integrate p2pID to your system</p>")
        self.write("<p><a href='/how'>how to</a></p><br><br>")
        self.write("<p><a href='/'>home</a></p>")
        self.write("</body></html>")


class LoginPageHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("face.html",mode=1, title="Login", myIP=myIP,label="")

class IndexPageHandler(tornado.web.RequestHandler):
    def get(self):
        self.write('''<html><head>
                   <meta charset="utf-8">
                   <title>p2pID</title>
                   <link rel="stylesheet" href="static/css/bootstrap.css">
                   <link rel="stylesheet" href="static/css/jsfeat.css">
                   </head><body>''')
        self.write("<br><h2>p2pID</h2><br>")
        self.write("<p>A peer-to-peer bio-identification service for verifying a user's presence</p><br><br>")
        self.write("<p><a href='/login'>login</a></p>")
        self.write("<p><a href='/new'>new user</a></p>")
        self.write("<p><a href='/how'>soure</a></p>")
        self.write("<p><a href='http://p2pid.co'>home</a></p>")
        self.write("</body></html>")

class DonePageHandler(tornado.web.RequestHandler):
    def get(self):
        self.write('''<html><head>
            <meta charset="utf-8">
            <title>p2pID</title>
            <link rel="stylesheet" href="static/css/bootstrap.css">
            <link rel="stylesheet" href="static/css/jsfeat.css">
            </head><body>''')
        self.write("<h2>ok</h2>")
        self.write("<p>new user database established. try login now.</p>")
        self.write("<p><a href='/login'>login</a></p><br>")
        self.write("<p><a href='/'>home</a></p>")
        self.write("</body></html>")

class HowToPageHandler(tornado.web.RequestHandler):
    def get(self):
        self.write('''<html><head>
            <meta charset="utf-8">
            <title>p2pID</title>
            <link rel="stylesheet" href="static/css/bootstrap.css">
            <link rel="stylesheet" href="static/css/jsfeat.css">
            </head><body>''')
        self.write("<h3>build my own p2pID service</h3>")
        self.write("<p><a href='http://www.python.org'><b>Python</b>: a tool that connects you to lots scientific tools</a></p>")
        self.write("<p><a href='http://www.opencv.org'><b>OpenCV</b>: a shortcut to learn computer vision</a></p>")
        self.write("<p><a href='http://docs.opencv.org/modules/contrib/doc/facerec/facerec_tutorial.html'><b>Face Recognition</b>: a begining of bio-identification</a></p>")
        self.write("<p><a href='http://cs.berry.edu/~nhamid/p2p/framework-python.html'><b>peer-to-peer networking</b>: share training datasets and data models </a></p>")
        self.write("<p><a href='https://github.com/bitcoin/bitcoin'><b>incentive system</b>: integrating with cryptocurrency (TODO)</a></p><br>")
        self.write("<p><a href='https://github.com/jackylee0424/dfr'><b>[download source code]</b></a></p><br>")
        self.write("<p><i>known issues</i>:<br>socket bug cause dropping p2p connection<br>false acceptance rate is high when training set is small</p><br><br>")
        self.write("<p><a href='/'>home</a></p>")
        self.write("</body></html>")

class NewLabelPageHandler(tornado.web.RequestHandler):
    def get(self):
        self.write('''<html><head>
            <meta charset="utf-8">
            <title>New User</title>
            <link rel="stylesheet" href="static/css/bootstrap.css">
            <link rel="stylesheet" href="static/css/jsfeat.css">
            <script type="text/javascript" src="static/js/jquery-1.8.2.min.js"></script>
            </head><body>''')
        self.write("<br><h3>your name?</h3>")
        self.write("<input type='text' id='label_name' />")
        self.write("<p><a id='next_stop'>next</a></p><br><br>")
        self.write("<p><a href='/'>home</a></p>")
        self.write('''<script type="text/javascript">$("a#next_stop").on('click',function()
            {
                //alert("/cap?label="+$("#label_name").val());
                var label_name = $("#label_name").val();
                if (label_name!='')
                    window.location.href = "/cap?label="+$("#label_name").val();
            });
            </script>''')
        self.write("</body></html>")

def main():
    train()
    settings = dict(
            template_path=os.path.join(os.path.dirname(__file__), "template"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            debug=True)
    
    tornado.options.parse_command_line()
    application = tornado.web.Application([
        (r"/", IndexPageHandler),
        (r"/login", LoginPageHandler),
        (r"/new", NewLabelPageHandler),
        (r"/cap", CapturePageHandler),
        (r"/how", HowToPageHandler),
        (r"/done",DonePageHandler),
        (r"/logged", DoneLoginPageHandler),
        (r"/ws",WSocketHandler),
        (r"/modeldownload", ModelDownloadSocket),
        (r"/labeldownload", LabelDownloadSocket),

    ],**settings)
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(tornado.options.options.port)
    print "open your chrome at http://localhost:8080"
    tornado.ioloop.IOLoop.instance().start()

if __name__ == "__main__":
    main()
