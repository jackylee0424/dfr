p2pID
===
[p2pID](http://p2pid.co) at Launch Hackathon 2014
      1. click new user
      2. type in your name
      3. enable camera for like 10 seconds
      4. go back home and login -> it should detect your ID


Build your own node
===
1. Launch face recog node
      Mac 10.9
      
      $ sudo port install opencv +python27
      
      $ python node.py

2. Launch chrome browser and go to http://localhost:8080
3. Webpage will ask for camera permission
4. The default is set to training mode. For a new node, you need to specify a label via input textbox. After collecting around 5+ images, you can reload the page and do another training.
5. Click on the "training mode" text to switch to "detection mode"
6. p2p setup: edit p2p/config.py for you and your peer's ip setting
