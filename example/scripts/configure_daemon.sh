#!/bin/bash
sudo cp /home/ec2-user/CodeInterviewSandbox/config/celery.service /etc/systemd/system/celery.service
sudo mkdir -p /etc/conf.d
sudo cp /home/ec2-user/CodeInterviewSandbox/config/celery /etc/conf.d/celery

sudo systemctl daemon-reload
sudo systemctl enable celery.service