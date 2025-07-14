FROM docker-registry-remote.artifactory-espoo1.int.net.nokia.com/locustio/locust:latest

COPY locustfiles/ /mnt/locust

CMD ["-f", "/mnt/locust/", "--class-picker"]
