# Raspberry Pi Production Deployment (`systemd`)

1. copy service file:
   `sudo cp fall-hub.service /etc/systemd/system/`

2. reload, enable, start:
   `sudo systemctl daemon-reload`
   `sudo systemctl enable fall-hub.service`
   `sudo systemctl start fall-hub.service`

3. status check:
   `sudo systemctl status fall-hub.service`