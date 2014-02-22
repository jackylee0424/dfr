import sys
import os
from tinyfacerec.model import EigenfacesModel
from tinyfacerec.model import FisherfacesModel
from tinyfacerec.distance import CosineDistance
import pickle
import time
import hashlib
import json

## genesis timestamp
genesis_ts = 1392697800000

def sha256_for_file(path, block_size=256*128, hr=False):
    sha256 = hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda: f.read(block_size), b''):
            sha256.update(chunk)
    if hr:
        return sha256.hexdigest()
    return sha256.digest()

def imgpreprocess(filepath):
    import cv2
    im = cv2.imread(filepath)
    im = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    im = cv2.resize(im,(128, 128), interpolation = cv2.INTER_CUBIC)
    im = cv2.equalizeHist(im)
    return im

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

if __name__ == '__main__':

    # need to maintain distributed [img, label] pairs
    # maintain a dict of { label:num, ... } where label can be hashed
    # train model based on [img, num[label]] pairs
    
    ## read images
    t = time.time()
    X,y = read_data("data/raw/")

    ## save to matrix data
    filename_temp = os.urandom(8).encode('hex')
    if not os.path.exists("data//processed"):
        os.makedirs("data//processed")
    with open('data//processed//%s.data'%filename_temp, 'wb') as output:
        pickle.dump({'X': X, 'y':y}, output, pickle.HIGHEST_PROTOCOL) ## X: image, y: label(integer)

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
    t = time.time()
    print "model hashing: %s took %.3f ms"%(sha256_for_file('data//model//model.bin',hr=True),(time.time()-t)*1000.)

    with open('data//model//model.bin', 'rb') as input:
        mmodel = pickle.load(input)

    # get a prediction for the first observation
    # predict based on global model/local model/O(N)-based model
    print "predicting (use 1st element)..."

    t = time.time()
    output_name, min_dist =  mmodel["eigen"].predict(xydata['X'][0],-.5)
    print "predicted (eigen)= %s (%f). took %.3f ms"%(str(output_name+genesis_ts), min_dist,(time.time()-t)*1000.)
    t = time.time()
    output_name, min_dist =  mmodel["fisher"].predict(xydata['X'][0],-.5)
    print "predicted (fisher)= %s (%f). took %.3f ms"%(str(output_name+genesis_ts), min_dist,(time.time()-t)*1000.)
