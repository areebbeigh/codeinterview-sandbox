#!/bin/bash

sudo yum update -y

# Install Docker
sudo amazon-linux-extras install docker
sudo service docker start
sudo usermod -a -G docker ec2-usermod

# Install gvisor
(
  set -e
  URL=https://storage.googleapis.com/gvisor/releases/release/latest
  wget ${URL}/runsc
  wget ${URL}/runsc.sha512
  sha512sum -c runsc.sha512
  rm -f runsc.sha512
  sudo mv runsc /usr/local/bin
  sudo chown root:root /usr/local/bin/runsc
  sudo chmod 0755 /usr/local/bin/runsc
)

sudo /usr/local/bin/runsc install

# sudo runsc install --runtime runsc-debug -- \
#   --debug \
#   --debug-log=/tmp/runsc-debug.log \
#   --strace \
#   --log-packets

sudo systemctl restart docker
sudo chmod 666 /var/run/docker.sock

# Install python3
sudo yum install python3 pip3 -y