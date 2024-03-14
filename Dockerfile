FROM jokeswar/base-ctl

RUN echo "Hello from Docker"

RUN apt update --fix-missing
RUN DEBIAN_FRONTEND=nonintearctive apt install -qy build-essential make python3
RUN DEBIAN_FRONTEND=nonintearctive apt install -qy sudo
RUN DEBIAN_FRONTEND=nonintearctive apt install -qy psmisc
RUN DEBIAN_FRONTEND=nonintearctive apt install -qy iproute2
RUN DEBIAN_FRONTEND=nonintearctive apt install -qy git
RUN DEBIAN_FRONTEND=nonintearctive apt install -qy mininet
RUN DEBIAN_FRONTEND=nonintearctive apt install -qy openvswitch-testcontroller
RUN DEBIAN_FRONTEND=nonintearctive apt install -qy python3-pip
RUN DEBIAN_FRONTEND=nonintearctive cp /usr/bin/ovs-testcontroller /usr/bin/ovs-controller
RUN DEBIAN_FRONTEND=nonintearctive pip3 install mininet
RUN DEBIAN_FRONTEND=nonintearctive pip3 install scapy
RUN DEBIAN_FRONTEND=nonintearctive pip3 install pathlib
RUN DEBIAN_FRONTEND=nonintearctive pip3 install git+https://github.com/mininet/mininet.git
RUN DEBIAN_FRONTEND=nonintearctive apt install -qy tshark
RUN DEBIAN_FRONTEND=nonintearctive apt install -qy tcpdump
